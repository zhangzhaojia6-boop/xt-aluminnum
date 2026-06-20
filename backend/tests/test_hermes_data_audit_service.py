from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, HermesCorrectionAction, HermesDataAuditRun, User
from app.services.hermes_data_audit_service import (
    DEFAULT_AUDIT_FIELDS,
    HermesDataAuditService,
    NoComparableDataError,
    OutputSkillPathViolationError,
    SUPPORTED_ACTION_TYPES,
)


def _db_session() -> Session:
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            HermesDataAuditRun.__table__,
            HermesCorrectionAction.__table__,
        ],
    )
    return Session(engine)


class _MesReadServiceFake:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def read_sources(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload


def _make_run(db: Session) -> HermesDataAuditRun:
    run = HermesDataAuditRun(
        run_key='run-1',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'parsed'},
        source_errors={},
        mes_snapshot={},
        hub_snapshot={},
        output_skill_snapshot={},
        diffs={},
        suggested_actions=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _summary_payload(value: float = 100.0, *, mes_status: str = 'ok', errors: dict | None = None) -> dict:
    return {
        'business_date': '2026-06-18',
        'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
        'records': {'summary': [{'field': 'total_output', 'value': value}]},
        'source_status': {
            'mes': mes_status,
            'sources': {
                'summary': {'status': 'ok', 'count': 1},
                **({'stock_records': {'status': 'failed', 'count': 0}} if mes_status == 'partial_failed' else {}),
            },
        },
        'source_errors': errors or {},
    }


def _supported_action(idempotency_key: str, *, action_type: str = 'mapping_alias_upsert', risk_level: str = 'low') -> dict:
    return {
        'idempotency_key': idempotency_key,
        'action_type': action_type,
        'risk_level': risk_level,
        'target_table': 'mapping_alias_rules',
        'target_key': 'cold-roll:2050',
        'field_name': 'workshop_output',
        'before_value': {'hub': 95.0},
        'after_value': {'hub': 100.0},
        'evidence': {'source': 'mes'},
        'rollback_payload': {'mode': 'manual', 'restore_before_value': {'hub': 95.0}},
    }


def test_read_output_skill_business_date_returns_missing_when_root_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv('OUTPUT_SKILL_ROOT', raising=False)
    db = _db_session()
    try:
        service = HermesDataAuditService(db, output_skill_root=None)
        payload = service._read_output_skill_business_date(date(2026, 6, 18))
        assert payload['status'] == 'missing'
        assert payload['files'] == []
        assert payload['parsed'] == {}
    finally:
        db.close()


def test_read_output_skill_file_blocks_path_escape(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    db = _db_session()
    try:
        service = HermesDataAuditService(db, output_skill_root=root)
        with pytest.raises(OutputSkillPathViolationError):
            service._read_output_skill_file('../escaped.txt')
    finally:
        db.close()


def test_read_output_skill_file_extracts_chinese_alias_fields(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    report = root / '2026-06-18-日报.txt'
    report.write_text('入库成品日合计 123.4 吨\n日成品率 96.5%\n', encoding='utf-8')
    db = _db_session()
    try:
        service = HermesDataAuditService(db, output_skill_root=root)
        payload = service._read_output_skill_file(report.name)
        assert payload['status'] == 'parsed'
        assert payload['parsed']['inbound_total'] == 123.4
        assert payload['parsed']['yield_rate'] == 96.5
    finally:
        db.close()


def test_read_output_skill_file_accepts_csv(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    report = root / '2026-06-18-日报.csv'
    report.write_text('日期,产量(吨),成品率\n2026-06-18,100,96.5%\n', encoding='utf-8')
    db = _db_session()
    try:
        service = HermesDataAuditService(db, output_skill_root=root)
        payload = service._read_output_skill_file(report.name)
        assert payload['status'] == 'parsed'
        assert payload['parsed']['total_output'] == 100.0
        assert payload['parsed']['yield_rate'] == 96.5
        assert payload['issues'] == []
    finally:
        db.close()


def test_create_run_uses_default_fields_when_fields_missing() -> None:
    db = _db_session()
    try:
        mes_records = {
            'summary': [{'field': field_name, 'value': float(index + 1)} for index, field_name in enumerate(DEFAULT_AUDIT_FIELDS)]
        }
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(
                {
                    'business_date': '2026-06-18',
                    'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
                    'records': mes_records,
                    'source_status': {'mes': 'ok', 'sources': {'summary': {'status': 'ok', 'count': len(DEFAULT_AUDIT_FIELDS)}}},
                    'source_errors': {},
                }
            ),
            hub_snapshot_reader=lambda business_date, fields: {
                field_name: float(index + 1) for index, field_name in enumerate(fields)
            },
        )
        service._read_output_skill_business_date = lambda business_date: {
            'status': 'parsed',
            'files': ['D:/output-skill/2026-06-18.txt'],
            'raw_text': '',
            'parsed': {field_name: float(index + 1) for index, field_name in enumerate(DEFAULT_AUDIT_FIELDS)},
            'issues': [],
        }

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=None,
        )

        assert set(run.diffs.keys()) == set(DEFAULT_AUDIT_FIELDS)
    finally:
        db.close()


def test_create_run_persists_safe_snapshot_summaries_only(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    (root / '2026-06-18-日报.txt').write_text('车间总产量日合计100吨 token=abc123\n', encoding='utf-8')
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(
                {
                    'business_date': '2026-06-18',
                    'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
                    'records': {'summary': [{'field': 'total_output', 'value': 100.0, 'debug_note': 'token=abc123'}]},
                    'source_status': {'mes': 'ok', 'sources': {'summary': {'status': 'ok', 'count': 1}}},
                    'source_errors': {},
                }
            ),
            output_skill_root=root,
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0, 'debug_note': 'token=abc123'},
        )

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        assert 'abc123' not in str(run.mes_snapshot)
        assert 'abc123' not in str(run.hub_snapshot)
        assert 'abc123' not in str(run.output_skill_snapshot)
        assert 'records' not in run.mes_snapshot
        assert 'raw_text' not in run.output_skill_snapshot
        assert run.mes_snapshot['records_count_by_source'] == {'summary': 1}
        assert run.output_skill_snapshot['parsed'] == {'total_output': 100.0}
    finally:
        db.close()


def test_create_run_persists_output_skill_issues_into_source_errors() -> None:
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload()),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )
        service._read_output_skill_business_date = lambda business_date: {
            'status': 'parsed',
            'files': ['D:/output-skill/2026-06-18.txt'],
            'raw_text': '',
            'parsed': {'total_output': 100.0},
            'issues': [
                {'code': 'conflicting_field_value', 'field_name': 'total_output'},
                {'message': 'token=abc123 should be redacted'},
            ],
        }

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        assert run.source_errors['output_skill'] == [
            {'code': 'conflicting_field_value', 'field_name': 'total_output'},
            {'message': 'token=<redacted> should be redacted'},
        ]
    finally:
        db.close()


def test_create_run_redacts_mes_source_errors_before_persisting() -> None:
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload(mes_status='partial_failed', errors={'stock_records': 'password=abc token=123'})),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )
        service._read_output_skill_business_date = lambda business_date: {
            'status': 'parsed',
            'files': ['D:/output-skill/2026-06-18.txt'],
            'raw_text': '',
            'parsed': {'total_output': 100.0},
            'issues': [],
        }

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        persisted = run.source_errors['mes']['stock_records']
        assert 'abc' not in persisted
        assert '123' not in persisted
        assert '<redacted>' in persisted
    finally:
        db.close()


def test_create_run_records_output_skill_parse_failure_instead_of_crashing(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    (root / '2026-06-18-bad.json').write_text('{"broken": ', encoding='utf-8')
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload()),
            output_skill_root=root,
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        assert run.status == 'completed_with_source_error'
        assert run.source_status['output_skill'] == 'failed'
        assert 'output_skill' in run.source_errors
        assert 'abc123' not in str(run.source_errors['output_skill'])
    finally:
        db.close()


def test_create_run_classifies_hub_mismatch_and_generates_supported_suggestion(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    (root / '2026-06-18-日报.txt').write_text('车间总产量日合计100吨\n日成品率 96.5%\n', encoding='utf-8')
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(
                {
                    'business_date': '2026-06-18',
                    'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
                    'records': {
                        'summary': [
                            {'field': 'total_output', 'value': 100.0},
                            {'field': 'yield_rate', 'value': 96.5},
                        ]
                    },
                    'source_status': {
                        'mes': 'partial_failed',
                        'sources': {
                            'summary': {'status': 'ok', 'count': 2},
                            'stock_records': {'status': 'failed', 'count': 0},
                        },
                    },
                    'source_errors': {'stock_records': 'driver exploded password=<redacted>'},
                }
            ),
            output_skill_root=root,
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 95.0, 'yield_rate': 96.5},
        )

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output', 'yield_rate'],
            created_by_id=7,
        )

        assert run.status == 'completed_with_source_error'
        assert float(run.match_rate) == pytest.approx(0.5)
        assert run.diffs['total_output']['status'] == 'hub_mismatch'
        assert run.diffs['yield_rate']['status'] == 'matched'
        assert run.suggested_actions[0]['action_type'] in SUPPORTED_ACTION_TYPES
    finally:
        db.close()


def test_create_run_returns_existing_run_for_same_input_without_unique_error() -> None:
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload()),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )
        stable_snapshot = {
            'status': 'parsed',
            'files': ['D:/output-skill/2026-06-18.txt'],
            'raw_text': '',
            'parsed': {'total_output': 100.0},
            'issues': [],
        }
        service._read_output_skill_business_date = lambda business_date: stable_snapshot

        first = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )
        second = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        assert first.id == second.id
        assert db.query(HermesDataAuditRun).count() == 1
    finally:
        db.close()


def test_create_run_creates_new_run_when_mes_snapshot_changes() -> None:
    db = _db_session()
    try:
        first_service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload(100.0)),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )
        second_service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload(101.0)),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )
        stable_snapshot = {
            'status': 'parsed',
            'files': ['D:/output-skill/2026-06-18.txt'],
            'raw_text': '',
            'parsed': {'total_output': 100.0},
            'issues': [],
        }
        first_service._read_output_skill_business_date = lambda business_date: stable_snapshot
        second_service._read_output_skill_business_date = lambda business_date: stable_snapshot

        first = first_service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])
        second = second_service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])

        assert first.id != second.id
        assert first.run_key != second.run_key
    finally:
        db.close()


def test_create_run_creates_new_run_when_hub_snapshot_changes() -> None:
    db = _db_session()
    try:
        first_service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload()),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )
        second_service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload()),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 101.0},
        )
        stable_snapshot = {
            'status': 'parsed',
            'files': ['D:/output-skill/2026-06-18.txt'],
            'raw_text': '',
            'parsed': {'total_output': 100.0},
            'issues': [],
        }
        first_service._read_output_skill_business_date = lambda business_date: stable_snapshot
        second_service._read_output_skill_business_date = lambda business_date: stable_snapshot

        first = first_service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])
        second = second_service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])

        assert first.id != second.id
        assert first.run_key != second.run_key
    finally:
        db.close()


def test_create_run_changes_run_key_when_output_skill_content_changes(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    report = root / '2026-06-18-日报.txt'
    report.write_text('车间总产量日合计100吨\n', encoding='utf-8')
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload()),
            output_skill_root=root,
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )

        first = service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])
        report.write_text('车间总产量日合计100吨\ntoken=changed\n', encoding='utf-8')
        second = service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])

        assert first.id != second.id
        assert first.run_key != second.run_key
    finally:
        db.close()


def test_create_run_uses_missing_source_status_when_output_skill_root_is_missing() -> None:
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload()),
            output_skill_root='Z:/definitely-missing-output-skill-root',
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )

        run = service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])
        assert run.status == 'completed_with_missing_source'
    finally:
        db.close()


def test_create_run_real_source_failure_outranks_missing_source() -> None:
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload(mes_status='partial_failed', errors={'stock_records': 'timeout'})),
            output_skill_root='Z:/definitely-missing-output-skill-root',
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )

        run = service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])
        assert run.status == 'completed_with_source_error'
    finally:
        db.close()


def test_create_run_writes_failed_run_before_raising_when_no_field_is_comparable(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    (root / '2026-06-18-日报.txt').write_text('无可比字段\n', encoding='utf-8')
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(
                {
                    'business_date': '2026-06-18',
                    'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
                    'records': {},
                    'source_status': {'mes': 'empty', 'sources': {}},
                    'source_errors': {},
                }
            ),
            output_skill_root=root,
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )

        with pytest.raises(NoComparableDataError):
                service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])

        saved = db.query(HermesDataAuditRun).one()
        assert saved.status == 'failed'
        assert saved.match_rate is None
        assert saved.diffs['total_output']['status'] in {'mes_missing', 'cannot_decide'}
    finally:
        db.close()


def test_apply_corrections_blocks_non_dry_run_when_apply_flag_disabled() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=False)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('action-1')],
            dry_run=False,
            applied_by_id=9,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['reason'] == 'apply_disabled'
        assert result['blocked_count'] == 1
        assert action.status == 'blocked'
        db.refresh(run)
        assert run.status == 'correction_blocked'
    finally:
        db.close()


def test_apply_corrections_blocks_unsupported_action_type() -> None:
    db = _db_session()
    called = {'value': False}
    try:
        run = _make_run(db)

        def _handler(action):
            called['value'] = True
            return {'evidence': {'handler': 'ok'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('unsupported', action_type='review_field_mismatch')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert called['value'] is False
        assert result['blocked_count'] == 1
        assert action.status == 'blocked'
        assert action.evidence['blocked_reason'] == 'unsupported_action_type'
    finally:
        db.close()


def test_apply_corrections_blocks_when_rollback_metadata_is_missing() -> None:
    db = _db_session()
    called = {'value': False}
    try:
        run = _make_run(db)

        def _handler(action):
            called['value'] = True
            return {'evidence': {'handler': 'ok'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)
        action = _supported_action('missing-rollback')
        action.pop('rollback_payload')

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=3,
        )

        row = db.query(HermesCorrectionAction).one()
        assert called['value'] is False
        assert result['blocked_count'] == 1
        assert row.status == 'blocked'
        assert row.evidence['blocked_reason'] == 'incomplete_correction_audit_payload'
    finally:
        db.close()


def test_apply_corrections_blocks_when_evidence_is_empty() -> None:
    db = _db_session()
    called = {'value': False}
    try:
        run = _make_run(db)

        def _handler(action):
            called['value'] = True
            return {'evidence': {'handler': 'ok'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)
        action = _supported_action('missing-evidence')
        action['evidence'] = {}

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=3,
        )

        row = db.query(HermesCorrectionAction).one()
        assert called['value'] is False
        assert result['blocked_count'] == 1
        assert row.status == 'blocked'
        assert row.evidence['blocked_reason'] in {'missing_correction_evidence', 'incomplete_correction_audit_payload'}
    finally:
        db.close()


def test_apply_corrections_blocks_when_risk_level_is_missing() -> None:
    db = _db_session()
    called = {'value': False}
    try:
        run = _make_run(db)

        def _handler(action):
            called['value'] = True
            return {'evidence': {'handler': 'ok'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)
        action = _supported_action('missing-risk-level')
        action.pop('risk_level')

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=3,
        )

        row = db.query(HermesCorrectionAction).one()
        assert called['value'] is False
        assert result['blocked_count'] == 1
        assert row.status == 'blocked'
        assert row.evidence['blocked_reason'] in {'missing_risk_level', 'incomplete_correction_audit_payload'}
    finally:
        db.close()


def test_apply_corrections_blocks_mes_target_tables() -> None:
    db = _db_session()
    called = {'value': False}
    try:
        run = _make_run(db)

        def _handler(action):
            called['value'] = True
            return {'evidence': {'handler': 'ok'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)
        action = _supported_action('mes-target')
        action['target_table'] = 'mes_stock_records'

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=3,
        )

        row = db.query(HermesCorrectionAction).one()
        assert called['value'] is False
        assert result['blocked_count'] == 1
        assert row.status == 'blocked'
        assert row.evidence['blocked_reason'] in {'mes_target_read_only', 'target_table_not_allowed'}
    finally:
        db.close()


def test_apply_corrections_dry_run_does_not_create_action_rows_or_call_handler() -> None:
    db = _db_session()
    called = {'value': False}
    try:
        run = _make_run(db)

        def _handler(action):
            called['value'] = True
            return {'evidence': {'handler': 'ok'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('dry-run-no-row')],
            dry_run=True,
            applied_by_id=9,
        )

        assert called['value'] is False
        assert result['dry_run_count'] == 1
        assert db.query(HermesCorrectionAction).count() == 0
    finally:
        db.close()


def test_apply_corrections_dry_run_keeps_existing_pending_action_unchanged() -> None:
    db = _db_session()
    called = {'value': False}
    try:
        run = _make_run(db)
        existing = HermesCorrectionAction(
            audit_run_id=run.id,
            idempotency_key='pending-action',
            action_type='mapping_alias_upsert',
            risk_level='low',
            target_table='mapping_alias_rules',
            target_key='cold-roll:2050',
            field_name='workshop_output',
            before_value={'hub': 95.0},
            after_value={'hub': 100.0},
            evidence={'source': 'mes'},
            rollback_payload={'mode': 'manual', 'restore_before_value': {'hub': 95.0}},
            status='pending',
            rollback_status='not_requested',
        )
        db.add(existing)
        db.commit()

        def _handler(action):
            called['value'] = True
            return {'evidence': {'handler': 'ok'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('pending-action')],
            dry_run=True,
            applied_by_id=9,
        )

        db.commit()
        db.refresh(existing)
        assert called['value'] is False
        assert result['dry_run_count'] == 1
        assert existing.status == 'pending'
        assert existing.before_value == {'hub': 95.0}
        assert existing.after_value == {'hub': 100.0}
        assert existing.evidence == {'source': 'mes'}
        assert existing.rollback_payload == {'mode': 'manual', 'restore_before_value': {'hub': 95.0}}
        assert db.query(HermesCorrectionAction).count() == 1
    finally:
        db.close()


def test_apply_corrections_allows_real_apply_after_dry_run() -> None:
    db = _db_session()
    handler_calls: list[dict] = []
    try:
        run = _make_run(db)

        def _handler(action):
            handler_calls.append(action)
            return {'evidence': {'handler': 'applied'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)
        action = _supported_action('dry-then-apply')

        preview = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=True,
            applied_by_id=9,
        )
        assert db.query(HermesCorrectionAction).count() == 0
        applied = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=9,
        )

        action_row = db.query(HermesCorrectionAction).filter_by(idempotency_key='dry-then-apply').one()
        assert preview['action_statuses'] == [{'idempotency_key': 'dry-then-apply', 'status': 'dry_run'}]
        assert applied['action_statuses'] == [{'idempotency_key': 'dry-then-apply', 'status': 'applied'}]
        assert len(handler_calls) == 1
        assert action_row.status == 'applied'
    finally:
        db.close()


def test_apply_corrections_blocks_uncontrolled_handler_without_calling_it(tmp_path) -> None:
    db = _db_session()
    external_engine = create_engine(f"sqlite:///{tmp_path / 'external-handler.db'}", future=True)
    Base.metadata.create_all(bind=external_engine, tables=[User.__table__])
    external_db = Session(external_engine)
    called = {'value': False}
    try:
        run = _make_run(db)

        def _uncontrolled_handler(action):
            called['value'] = True
            external_db.add(User(username='external-user', name='External User', password_hash='x'))
            external_db.commit()
            raise RuntimeError('should never run')

        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_uncontrolled_handler)
        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('uncontrolled-handler')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert called['value'] is False
        assert result['blocked_count'] == 1
        assert action.status == 'blocked'
        assert action.evidence['blocked_reason'] == 'handler_not_controlled'
        assert external_db.query(User).filter_by(username='external-user').count() == 0
        db.refresh(run)
        assert run.status == 'correction_blocked'
    finally:
        external_db.close()
        db.close()


def test_apply_corrections_marks_blocked_when_handler_missing() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=None)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('action-without-handler')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['blocked_count'] == 1
        assert action.status == 'blocked'
        assert action.evidence['blocked_reason'] == 'handler_missing'
    finally:
        db.close()


def test_apply_corrections_rolls_back_whole_batch_when_one_controlled_write_fails() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _handler(action):
            if action['idempotency_key'] == 'will-pass':
                db.add(User(username='batch-user-1', name='Batch User 1', password_hash='x'))
                return {'evidence': {'handler': 'ok'}}
            db.add(User(username='batch-user-2', name='Batch User 2', password_hash='x'))
            raise RuntimeError('boom')

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                _supported_action('will-pass'),
                _supported_action('will-fail', action_type='mapping_field_rule_upsert'),
            ],
            dry_run=False,
            applied_by_id=3,
        )

        rows = db.query(HermesCorrectionAction).order_by(HermesCorrectionAction.id).all()
        assert result['applied_count'] == 0
        assert result['failed_count'] == 2
        assert [row.status for row in rows] == ['failed', 'failed']
        assert db.query(User).filter(User.username.in_(['batch-user-1', 'batch-user-2'])).count() == 0
        db.refresh(run)
        assert run.status == 'correction_failed'
    finally:
        db.close()


def test_apply_corrections_marks_partial_failure_for_mixed_blocked_and_failed() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _handler(action):
            raise RuntimeError('boom')

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                _supported_action('will-block', risk_level='high'),
                _supported_action('will-fail'),
            ],
            dry_run=False,
            applied_by_id=3,
        )

        assert result['blocked_count'] == 1
        assert result['failed_count'] == 1
        db.refresh(run)
        assert run.status == 'correction_partial_failed'
    finally:
        db.close()


def test_apply_corrections_marks_applied_when_controlled_handler_succeeds() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _handler(action):
            return {
                'before_value': {'hub': 95.0},
                'after_value': {'hub': 96.5},
                'evidence': {'handler': 'ok'},
                'rollback_payload': {'mode': 'manual', 'restore_before_value': {'hub': 95.0}},
            }

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('applied-action')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['applied_count'] == 1
        assert action.status == 'applied'
        assert action.before_value == {'hub': 95.0}
        assert action.after_value == {'hub': 96.5}
        assert action.evidence == {'handler': 'ok'}
        db.refresh(run)
        assert run.status == 'corrected'
    finally:
        db.close()


def test_apply_corrections_fails_when_handler_clears_evidence() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _handler(action):
            return {
                'before_value': {'hub': 95.0},
                'after_value': {'hub': 96.5},
                'evidence': {},
                'rollback_payload': {'mode': 'manual', 'restore_before_value': {'hub': 95.0}},
            }

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('handler-clears-evidence')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['applied_count'] == 0
        assert result['failed_count'] == 1
        assert action.status == 'failed'
        assert action.evidence['error'] in {'invalid_handler_audit_payload', 'incomplete_correction_audit_payload'}
        db.refresh(run)
        assert run.status == 'correction_failed'
    finally:
        db.close()


def test_apply_corrections_fails_when_handler_clears_rollback_payload() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _handler(action):
            return {
                'before_value': {'hub': 95.0},
                'after_value': {'hub': 96.5},
                'evidence': {'handler': 'ok', 'source': 'mes'},
                'rollback_payload': {},
            }

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('handler-clears-rollback')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['applied_count'] == 0
        assert result['failed_count'] == 1
        assert action.status == 'failed'
        assert action.evidence['error'] in {'invalid_handler_audit_payload', 'incomplete_correction_audit_payload'}
        db.refresh(run)
        assert run.status == 'correction_failed'
    finally:
        db.close()
