from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, HermesCorrectionAction, HermesDataAuditRun, User
from app.services.hermes_data_audit_service import (
    HermesDataAuditService,
    NoComparableDataError,
    OutputSkillPathViolationError,
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
        assert '入库成品日合计' in payload['raw_text']
        assert '日成品率' in payload['raw_text']
    finally:
        db.close()


def test_create_run_persists_match_rate_diffs_source_status_and_errors(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    (root / '2026-06-18-日报.txt').write_text(
        '车间总产量日合计100吨\n日成品率 96.5%\n',
        encoding='utf-8',
    )
    mes_service = _MesReadServiceFake(
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
    )

    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=mes_service,
            output_skill_root=root,
            hub_snapshot_reader=lambda business_date, fields: {
                'total_output': 95.0,
                'yield_rate': 96.5,
            },
        )

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output', 'yield_rate'],
            created_by_id=7,
        )

        db.refresh(run)

        assert mes_service.calls[0]['business_date'] == date(2026, 6, 18)
        assert run.status == 'completed_with_source_error'
        assert float(run.match_rate) == pytest.approx(0.5)
        assert run.source_status == {
            'mes': 'partial_failed',
            'hub': 'ok',
            'output_skill': 'parsed',
            'mes_sources': {
                'summary': {'status': 'ok', 'count': 2},
                'stock_records': {'status': 'failed', 'count': 0},
            },
        }
        assert run.source_errors == {
            'mes': {'stock_records': 'driver exploded password=<redacted>'},
        }
        assert run.diffs['total_output'] == {
            'status': 'mismatched',
            'values': {
                'mes': 100.0,
                'hub': 95.0,
                'output_skill': 100.0,
            },
        }
        assert run.diffs['yield_rate'] == {
            'status': 'matched',
            'values': {
                'mes': 96.5,
                'hub': 96.5,
                'output_skill': 96.5,
            },
        }
        assert run.suggested_actions == [
            {
                'action_type': 'review_field_mismatch',
                'idempotency_key': run.suggested_actions[0]['idempotency_key'],
                'risk_level': 'low',
                'field_name': 'total_output',
                'target_table': 'data_hub_snapshot',
                'target_key': '2026-06-18:total_output',
                'before_value': {'hub': 95.0},
                'after_value': {'suggested_value': 100.0},
                'evidence': {
                    'field_name': 'total_output',
                    'values': {
                        'mes': 100.0,
                        'hub': 95.0,
                        'output_skill': 100.0,
                    },
                },
            }
        ]
        saved = db.query(HermesDataAuditRun).filter(HermesDataAuditRun.id == run.id).one()
        assert saved.created_by_id == 7
    finally:
        db.close()


def test_create_run_persists_safe_snapshot_summaries_only(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    (root / '2026-06-18-日报.txt').write_text(
        '车间总产量日合计100吨 token=abc123\n',
        encoding='utf-8',
    )
    mes_service = _MesReadServiceFake(
        {
            'business_date': '2026-06-18',
            'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
            'records': {
                'summary': [
                    {'field': 'total_output', 'value': 100.0, 'debug_note': 'token=abc123'},
                ]
            },
            'source_status': {
                'mes': 'ok',
                'sources': {
                    'summary': {'status': 'ok', 'count': 1},
                },
            },
            'source_errors': {},
        }
    )

    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=mes_service,
            output_skill_root=root,
            hub_snapshot_reader=lambda business_date, fields: {
                'total_output': 100.0,
                'debug_note': 'token=abc123',
            },
        )

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        mes_snapshot_text = str(run.mes_snapshot)
        hub_snapshot_text = str(run.hub_snapshot)
        output_snapshot_text = str(run.output_skill_snapshot)
        assert 'abc123' not in mes_snapshot_text
        assert 'abc123' not in hub_snapshot_text
        assert 'abc123' not in output_snapshot_text
        assert 'records' not in run.mes_snapshot
        assert 'raw_text' not in run.output_skill_snapshot
        assert run.mes_snapshot['records_count_by_source'] == {'summary': 1}
        assert run.output_skill_snapshot['parsed'] == {'total_output': 100.0}
        assert 'payload_hash' in run.output_skill_snapshot
    finally:
        db.close()


def test_create_run_persists_output_skill_issues_into_source_errors() -> None:
    mes_service = _MesReadServiceFake(
        {
            'business_date': '2026-06-18',
            'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
            'records': {
                'summary': [
                    {'field': 'total_output', 'value': 100.0},
                ]
            },
            'source_status': {
                'mes': 'ok',
                'sources': {
                    'summary': {'status': 'ok', 'count': 1},
                },
            },
            'source_errors': {},
        }
    )

    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=mes_service,
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

        db.refresh(run)
        assert run.source_errors['output_skill'] == [
            {'code': 'conflicting_field_value', 'field_name': 'total_output'},
            {'message': 'token=<redacted> should be redacted'},
        ]
    finally:
        db.close()


def test_create_run_redacts_mes_source_errors_before_persisting() -> None:
    mes_service = _MesReadServiceFake(
        {
            'business_date': '2026-06-18',
            'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
            'records': {
                'summary': [
                    {'field': 'total_output', 'value': 100.0},
                ]
            },
            'source_status': {
                'mes': 'partial_failed',
                'sources': {
                    'summary': {'status': 'ok', 'count': 1},
                    'stock_records': {'status': 'failed', 'count': 0},
                },
            },
            'source_errors': {'stock_records': 'password=abc token=123'},
        }
    )

    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=mes_service,
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


def test_create_run_returns_existing_run_for_same_input_without_unique_error() -> None:
    mes_payload = {
        'business_date': '2026-06-18',
        'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
        'records': {
            'summary': [
                {'field': 'total_output', 'value': 100.0},
            ]
        },
        'source_status': {
            'mes': 'ok',
            'sources': {
                'summary': {'status': 'ok', 'count': 1},
            },
        },
        'source_errors': {},
    }
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(mes_payload),
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


def test_create_run_changes_run_key_when_output_skill_content_changes(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    report = root / '2026-06-18-日报.txt'
    report.write_text('车间总产量日合计100吨\n', encoding='utf-8')
    mes_payload = {
        'business_date': '2026-06-18',
        'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
        'records': {
            'summary': [
                {'field': 'total_output', 'value': 100.0},
            ]
        },
        'source_status': {
            'mes': 'ok',
            'sources': {
                'summary': {'status': 'ok', 'count': 1},
            },
        },
        'source_errors': {},
    }
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(mes_payload),
            output_skill_root=root,
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )

        first = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )
        report.write_text('车间总产量日合计100吨\ntoken=changed\n', encoding='utf-8')
        second = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        assert first.id != second.id
        assert first.run_key != second.run_key
    finally:
        db.close()


def test_create_run_writes_failed_run_before_raising_when_no_field_is_comparable(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    (root / '2026-06-18-日报.txt').write_text('无可比字段\n', encoding='utf-8')
    mes_service = _MesReadServiceFake(
        {
            'business_date': '2026-06-18',
            'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
            'records': {},
            'source_status': {'mes': 'empty', 'sources': {}},
            'source_errors': {},
        }
    )

    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=mes_service,
            output_skill_root=root,
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )

        with pytest.raises(NoComparableDataError):
            service.create_run(
                business_date=date(2026, 6, 18),
                fields=['total_output'],
            )

        saved = db.query(HermesDataAuditRun).one()
        assert saved.status == 'failed'
        assert saved.match_rate is None
        assert saved.diffs == {
            'total_output': {
                'status': 'not_comparable',
                'values': {
                    'hub': 100.0,
                },
            }
        }
        assert saved.source_status['mes'] == 'empty'
        assert saved.source_status['output_skill'] == 'empty'
    finally:
        db.close()


def test_apply_corrections_blocks_non_dry_run_when_apply_flag_disabled() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=False)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                {
                    'idempotency_key': 'action-1',
                    'action_type': 'hub_update',
                    'risk_level': 'low',
                    'target_table': 'daily_stats',
                    'target_key': '2026-06-18:total_output',
                    'field_name': 'total_output',
                    'before_value': {'hub': 95.0},
                    'after_value': {'hub': 100.0},
                    'evidence': {'source': 'mes'},
                }
            ],
            dry_run=False,
            applied_by_id=9,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['reason'] == 'apply_disabled'
        assert result['blocked_count'] == 1
        assert result['action_statuses'] == [{'idempotency_key': 'action-1', 'status': 'blocked'}]
        assert action.status == 'blocked'
        assert action.rollback_status == 'not_requested'
    finally:
        db.close()


def test_apply_corrections_skips_duplicate_idempotency_keys() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True)
        action = {
            'idempotency_key': 'duplicate-key',
            'action_type': 'hub_update',
            'risk_level': 'low',
            'target_table': 'daily_stats',
            'target_key': '2026-06-18:yield_rate',
            'field_name': 'yield_rate',
            'before_value': {'hub': 95.0},
            'after_value': {'hub': 96.5},
            'evidence': {'source': 'output_skill'},
        }

        first = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=True,
            applied_by_id=9,
        )
        second = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=True,
            applied_by_id=9,
        )

        assert first['created_count'] == 1
        assert second['skipped_count'] == 1
        assert second['action_statuses'] == [{'idempotency_key': 'duplicate-key', 'status': 'skipped_duplicate'}]
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

        service = HermesDataAuditService(
            db,
            apply_enabled=True,
            correction_handler=_handler,
        )
        action = {
            'idempotency_key': 'dry-then-apply',
            'action_type': 'hub_update',
            'risk_level': 'low',
            'target_table': 'daily_stats',
            'target_key': '2026-06-18:yield_rate',
            'field_name': 'yield_rate',
            'before_value': {'hub': 95.0},
            'after_value': {'hub': 96.5},
            'evidence': {'source': 'mes'},
        }

        preview = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=True,
            applied_by_id=9,
        )
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


def test_apply_corrections_does_not_mark_applied_when_handler_missing() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=None)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                {
                    'idempotency_key': 'action-without-handler',
                    'action_type': 'hub_update',
                    'risk_level': 'low',
                    'target_table': 'daily_stats',
                    'target_key': '2026-06-18:yield_rate',
                    'field_name': 'yield_rate',
                    'before_value': {'hub': 95.0},
                    'after_value': {'hub': 96.5},
                    'evidence': {'source': 'mes'},
                }
            ],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['applied_count'] == 0
        assert result['blocked_count'] == 1
        assert result['action_statuses'] == [{'idempotency_key': 'action-without-handler', 'status': 'blocked'}]
        assert action.status == 'blocked'
        assert action.applied_at is None
        assert action.evidence['blocked_reason'] == 'handler_missing'
    finally:
        db.close()


def test_apply_corrections_rolls_back_handler_side_effects_when_handler_fails() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _handler(action):
            db.add(User(username='temp-user', name='Temp User', password_hash='x'))
            raise RuntimeError('boom after write')

        service = HermesDataAuditService(
            db,
            apply_enabled=True,
            correction_handler=_handler,
        )

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                {
                    'idempotency_key': 'handler-rollback',
                    'action_type': 'hub_update',
                    'risk_level': 'low',
                    'target_table': 'daily_stats',
                    'target_key': '2026-06-18:yield_rate',
                    'field_name': 'yield_rate',
                    'before_value': {'hub': 95.0},
                    'after_value': {'hub': 96.5},
                    'evidence': {'source': 'mes'},
                }
            ],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).filter_by(idempotency_key='handler-rollback').one()
        assert result['failed_count'] == 1
        assert action.status == 'failed'
        assert db.query(User).filter_by(username='temp-user').count() == 0
    finally:
        db.close()


def test_apply_corrections_marks_run_as_partial_failure_when_batch_mixes_success_and_failure() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _handler(action):
            if action['idempotency_key'] == 'will-fail':
                raise RuntimeError('boom')
            return {'evidence': {'handler': 'ok'}}

        service = HermesDataAuditService(
            db,
            apply_enabled=True,
            correction_handler=_handler,
        )

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                {
                    'idempotency_key': 'will-pass',
                    'action_type': 'hub_update',
                    'risk_level': 'low',
                    'target_table': 'daily_stats',
                    'target_key': '2026-06-18:yield_rate',
                    'field_name': 'yield_rate',
                    'before_value': {'hub': 95.0},
                    'after_value': {'hub': 96.5},
                    'evidence': {'source': 'mes'},
                },
                {
                    'idempotency_key': 'will-fail',
                    'action_type': 'hub_update',
                    'risk_level': 'low',
                    'target_table': 'daily_stats',
                    'target_key': '2026-06-18:total_output',
                    'field_name': 'total_output',
                    'before_value': {'hub': 95.0},
                    'after_value': {'hub': 100.0},
                    'evidence': {'source': 'mes'},
                },
            ],
            dry_run=False,
            applied_by_id=3,
        )

        db.refresh(run)
        assert result['applied_count'] == 1
        assert result['failed_count'] == 1
        assert run.status == 'correction_partial_failed'
    finally:
        db.close()


def test_apply_corrections_marks_applied_when_handler_succeeds() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(
            db,
            apply_enabled=True,
            correction_handler=lambda action: {
                'before_value': {'hub': 95.0},
                'after_value': {'hub': 96.5},
                'evidence': {'handler': 'ok'},
                'rollback_payload': {'mode': 'manual'},
            },
        )

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                {
                    'idempotency_key': 'applied-action',
                    'action_type': 'hub_update',
                    'risk_level': 'low',
                    'target_table': 'daily_stats',
                    'target_key': '2026-06-18:yield_rate',
                    'field_name': 'yield_rate',
                    'before_value': {'hub': Decimal('95.0')},
                    'after_value': {'hub': Decimal('96.5')},
                    'evidence': {'source': 'mes'},
                }
            ],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['applied_count'] == 1
        assert result['action_statuses'] == [{'idempotency_key': 'applied-action', 'status': 'applied'}]
        assert action.status == 'applied'
        assert action.before_value == {'hub': 95.0}
        assert action.after_value == {'hub': 96.5}
        assert action.evidence == {'handler': 'ok'}
        assert action.rollback_payload == {'mode': 'manual'}
    finally:
        db.close()


def test_create_run_uses_stable_run_key_for_same_inputs() -> None:
    mes_payload = {
        'business_date': '2026-06-18',
        'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
        'records': {
            'summary': [
                {'field': 'total_output', 'value': 100.0},
            ]
        },
        'source_status': {
            'mes': 'ok',
            'sources': {
                'summary': {'status': 'ok', 'count': 1},
            },
        },
        'source_errors': {},
    }
    db1 = _db_session()
    db2 = _db_session()
    try:
        service1 = HermesDataAuditService(
            db1,
            mes_read_service=_MesReadServiceFake(mes_payload),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )
        service2 = HermesDataAuditService(
            db2,
            mes_read_service=_MesReadServiceFake(mes_payload),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )
        stable_snapshot = {
            'status': 'parsed',
            'files': ['D:/output-skill/2026-06-18.txt'],
            'raw_text': '',
            'parsed': {'total_output': 100.0},
            'issues': [],
        }
        service1._read_output_skill_business_date = lambda business_date: stable_snapshot
        service2._read_output_skill_business_date = lambda business_date: stable_snapshot

        run1 = service1.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
            mes_query_keys=['stock_records', 'workshop_process_records'],
        )
        run2 = service2.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
            mes_query_keys=['workshop_process_records', 'stock_records'],
        )

        assert run1.run_key == run2.run_key
    finally:
        db1.close()
        db2.close()


def test_create_run_uses_degraded_status_when_sources_have_errors_but_data_is_comparable() -> None:
    mes_service = _MesReadServiceFake(
        {
            'business_date': '2026-06-18',
            'window': {'start_at': '2026-06-18T07:50:00+08:00', 'end_at': '2026-06-19T07:50:00+08:00'},
            'records': {
                'summary': [
                    {'field': 'total_output', 'value': 100.0},
                ]
            },
            'source_status': {
                'mes': 'partial_failed',
                'sources': {
                    'summary': {'status': 'ok', 'count': 1},
                    'stock_records': {'status': 'failed', 'count': 0},
                },
            },
            'source_errors': {'stock_records': 'password=abc token=123'},
        }
    )
    db = _db_session()
    try:
        service = HermesDataAuditService(
            db,
            mes_read_service=mes_service,
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

        assert run.status == 'completed_with_source_error'
        assert 'output_skill' not in run.source_errors
        assert 'mes' in run.source_errors
    finally:
        db.close()
