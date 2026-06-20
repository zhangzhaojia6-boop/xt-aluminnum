from __future__ import annotations

from datetime import date
from decimal import Decimal
import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'run_hermes_data_audit_backfill.py'


def _load_script_module():
    spec = importlib.util.spec_from_file_location('run_hermes_data_audit_backfill', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSessionFactory:
    def __call__(self):
        return _FakeSession()


class _FakeService:
    def __init__(self, plan_by_date: dict[date, object]) -> None:
        self.plan_by_date = plan_by_date
        self.create_calls: list[dict] = []
        self.apply_calls: list[dict] = []

    def create_run(self, *, business_date: date, fields, mes_query_keys=None, created_by_id=None):
        self.create_calls.append(
            {
                'business_date': business_date,
                'fields': list(fields or []),
                'mes_query_keys': list(mes_query_keys or []),
                'created_by_id': created_by_id,
            }
        )
        planned = self.plan_by_date[business_date]
        if isinstance(planned, Exception):
            raise planned
        return planned

    def apply_corrections(self, *, audit_run_id: int, actions, dry_run=True, applied_by_id=None):
        self.apply_calls.append(
            {
                'audit_run_id': audit_run_id,
                'actions': list(actions),
                'dry_run': dry_run,
                'applied_by_id': applied_by_id,
            }
        )
        return {
            'audit_run_id': audit_run_id,
            'apply_enabled': True,
            'reason': None,
            'created_count': len(actions),
            'dry_run_count': 0,
            'applied_count': len(actions),
            'blocked_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'action_statuses': [],
        }


def _make_run(
    *,
    run_id: int = 1,
    business_date: date = date(2026, 6, 18),
    status: str = 'completed',
    match_rate: Decimal | None = Decimal('0.8700'),
    source_status: dict | None = None,
    source_errors: dict | None = None,
    diffs: dict | None = None,
    suggested_actions: list[dict] | None = None,
):
    return SimpleNamespace(
        id=run_id,
        business_date=business_date,
        status=status,
        match_rate=match_rate,
        source_status=source_status or {'mes': 'ok', 'hub': 'ok', 'output_skill': 'parsed'},
        source_errors=source_errors or {},
        diffs=diffs
        or {
            'total_output': {'status': 'matched', 'values': {'mes': 10, 'hub': 10, 'output_skill': 10}},
            'yield_rate': {'status': 'hub_mismatch', 'values': {'mes': 96.5, 'hub': 95.0, 'output_skill': 96.5}},
        },
        suggested_actions=suggested_actions
        or [
            {
                'idempotency_key': 'alias:1',
                'action_type': 'mapping_alias_upsert',
                'risk_level': 'low',
                'target_table': 'master_code_aliases',
                'target_key': 'workshop:精整',
            }
        ],
    )


def test_date_range_includes_end_date() -> None:
    module = _load_script_module()

    days = module._date_range(date(2026, 6, 16), date(2026, 6, 18))

    assert days == [date(2026, 6, 16), date(2026, 6, 17), date(2026, 6, 18)]


def test_parse_csv_list_trims_and_splits_values() -> None:
    module = _load_script_module()

    values = module._parse_csv_list(' total_output, inbound_total ,yield_rate ')

    assert values == ['total_output', 'inbound_total', 'yield_rate']


def test_format_backfill_row_contains_table_values_and_redacts_sensitive_text() -> None:
    module = _load_script_module()
    summary = {
        'date': '2026-06-16',
        'status': 'completed_with_source_error',
        'apply': 'no',
        'match': 0.0,
        'mes': 'ok',
        'hub': 'ok',
        'outskill': 'missing',
        'diffs': 9,
        'next': 'mount_output_skill_reference_and_rerun',
        'detail': 'line1\npassword=abc\tpostgresql://user:secret@db.example.com/app',
    }

    row = module.format_backfill_row(summary)

    assert '2026-06-16' in row
    assert 'completed_with_source_error' in row
    assert 'mount_output_skill_reference_and_rerun' in row
    assert row.count('\n') == 0
    assert '\t' not in row
    assert 'password=abc' not in row
    assert 'secret' not in row
    assert 'postgresql://user:secret@db.example.com/app' not in row
    assert 'postgresql://' not in row
    assert 'db.example.com/app' not in row
    assert '<redacted-connection-uri>' in row
    assert '<redacted>' in row


def test_run_backfill_continues_after_day_errors() -> None:
    module = _load_script_module()
    comparable_error = module.NoComparableDataError('No comparable data for audit run 3')
    failed_error = RuntimeError(
        'mes source failed password=abc token=123 postgresql://user:secretpass@db.example.com/app'
    )
    ok_run = _make_run(
        business_date=date(2026, 6, 18),
        status='completed_with_missing_source',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'missing'},
        source_errors={'output_skill': 'output_skill_source_missing'},
        suggested_actions=[],
        diffs={'total_output': {'status': 'output_skill_missing', 'values': {'mes': 10, 'hub': 10}}},
    )
    service = _FakeService(
        {
            date(2026, 6, 16): comparable_error,
            date(2026, 6, 17): failed_error,
            date(2026, 6, 18): ok_run,
        }
    )

    summaries = module.run_backfill(
        start_date=date(2026, 6, 16),
        end_date=date(2026, 6, 18),
        fields=['total_output'],
        sessionmaker_factory=lambda: _FakeSessionFactory(),
        service_factory=lambda _db, apply_enabled: service,
    )

    assert [item['status'] for item in summaries] == ['no_comparable_data', 'failed', 'completed_with_missing_source']
    assert summaries[0]['next'].startswith('expand_fields_or_fix_sources')
    assert summaries[1]['next'].startswith('fix_source_health_and_rerun')
    assert 'password=abc' not in summaries[1]['detail']
    assert 'token=123' not in summaries[1]['detail']
    assert 'secretpass' not in summaries[1]['detail']
    assert 'postgresql://user:secretpass@db.example.com/app' not in summaries[1]['detail']
    assert 'postgresql://' not in summaries[1]['detail']
    assert 'db.example.com/app' not in summaries[1]['detail']
    assert '<redacted-connection-uri>' in summaries[1]['detail']
    assert summaries[2]['outskill'] == 'missing'
    assert len(service.create_calls) == 3


def test_run_backfill_default_dry_run_does_not_apply_corrections() -> None:
    module = _load_script_module()
    service = _FakeService({date(2026, 6, 18): _make_run()})

    summaries = module.run_backfill(
        start_date=date(2026, 6, 18),
        end_date=date(2026, 6, 18),
        fields=None,
        sessionmaker_factory=lambda: _FakeSessionFactory(),
        service_factory=lambda _db, apply_enabled: service,
    )

    assert service.create_calls[0]['fields'] == list(module.DEFAULT_BACKFILL_FIELDS)
    assert service.apply_calls == []
    assert summaries[0]['apply'] == 'no'


def test_run_backfill_passes_mes_query_keys_to_create_run() -> None:
    module = _load_script_module()
    service = _FakeService({date(2026, 6, 18): _make_run()})

    module.run_backfill(
        start_date=date(2026, 6, 18),
        end_date=date(2026, 6, 18),
        fields=['total_output'],
        mes_query_keys=['stock_records', 'yield_records'],
        sessionmaker_factory=lambda: _FakeSessionFactory(),
        service_factory=lambda _db, apply_enabled: service,
    )

    assert service.create_calls[0]['mes_query_keys'] == ['stock_records', 'yield_records']


def test_run_backfill_apply_corrections_calls_real_apply_once() -> None:
    module = _load_script_module()
    run = _make_run(run_id=9)
    service = _FakeService({date(2026, 6, 18): run})

    summaries = module.run_backfill(
        start_date=date(2026, 6, 18),
        end_date=date(2026, 6, 18),
        fields=['total_output'],
        dry_run=False,
        apply_corrections=True,
        sessionmaker_factory=lambda: _FakeSessionFactory(),
        service_factory=lambda _db, apply_enabled: service,
    )

    assert len(service.apply_calls) == 1
    assert service.apply_calls[0]['audit_run_id'] == 9
    assert service.apply_calls[0]['actions'] == run.suggested_actions
    assert service.apply_calls[0]['dry_run'] is False
    assert summaries[0]['apply'] == 'yes'
    assert summaries[0]['next'] == 'rerun_audit_to_verify'


def test_main_dry_run_prints_header_and_rows(monkeypatch) -> None:
    module = _load_script_module()
    captured = StringIO()

    monkeypatch.setattr(
        module,
        'run_backfill',
        lambda **kwargs: [
            {
                'date': '2026-06-16',
                'status': 'completed_with_missing_source',
                'apply': 'no',
                'match': 0.0,
                'mes': 'ok',
                'hub': 'ok',
                'outskill': 'missing',
                'diffs': 9,
                'next': 'mount_output_skill_reference_and_rerun',
                'detail': '',
            }
        ],
    )
    monkeypatch.setattr(module.sys, 'stdout', captured)

    exit_code = module.main(['--start-date', '2026-06-16', '--end-date', '2026-06-18', '--dry-run'])

    output = captured.getvalue()
    assert exit_code == 0
    assert 'DATE' in output
    assert 'STATUS' in output
    assert '2026-06-16' in output
    assert 'mount_output_skill_reference_and_rerun' in output
