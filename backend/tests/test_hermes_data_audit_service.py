from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Base,
    ChatInboxMessage,
    HermesCorrectionAction,
    HermesDataAuditRun,
    MasterCodeAlias,
    RagDocument,
    RagSourceIngestion,
    User,
)
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
            ChatInboxMessage.__table__,
            HermesDataAuditRun.__table__,
            HermesCorrectionAction.__table__,
            MasterCodeAlias.__table__,
            RagDocument.__table__,
            RagSourceIngestion.__table__,
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


def _make_run(db: Session, *, run_key: str = 'run-1') -> HermesDataAuditRun:
    run = HermesDataAuditRun(
        run_key=run_key,
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


def _dingtalk_created_at(
    year: int = 2026,
    month: int = 6,
    day: int = 18,
    hour: int = 9,
    minute: int = 0,
) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone(timedelta(hours=8)))


def _add_dingtalk_text_message(
    db: Session,
    *,
    text: str,
    created_at: datetime,
    channel: str = 'dingtalk_group',
    group_id: str = 'ding-group-001',
    trace_id: str = 'trace-ding-text-001',
    sender_external_id: str = 'ding-user-001',
    source_payload: dict | None = None,
) -> ChatInboxMessage:
    message = ChatInboxMessage(
        channel=channel,
        group_id=group_id,
        sender_external_id=sender_external_id,
        text=text,
        agent_code='hermes',
        trace_id=trace_id,
        source_payload=source_payload or {},
        created_at=created_at,
    )
    db.add(message)
    db.flush()
    return message


def _add_dingtalk_file_document(
    db: Session,
    *,
    created_at: datetime,
    filename: str = '产量核对.xlsx',
    source_name: str = '钉钉群文件',
    source_type: str = 'dingtalk_file',
    source_ref: str = 'dingtalk://files/产量核对.xlsx?token=file-secret',
    document_status: str = 'active',
    ingestion_status: str = 'active',
    document_metadata: dict | None = None,
    ingestion_metadata: dict | None = None,
) -> tuple[RagDocument, RagSourceIngestion]:
    document = RagDocument(
        filename=filename,
        source_name=source_name,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        encoding='binary',
        status=document_status,
        file_size=2048,
        chunk_count=0,
        metadata_payload=document_metadata or {'source': 'dingtalk_file', 'channel': 'dingtalk_group'},
        created_at=created_at,
    )
    db.add(document)
    db.flush()
    ingestion = RagSourceIngestion(
        source_type=source_type,
        source_ref=source_ref,
        status=ingestion_status,
        document_id=document.id,
        metadata_payload=ingestion_metadata or {'channel': 'dingtalk_group'},
        created_at=created_at,
    )
    db.add(ingestion)
    db.flush()
    return document, ingestion


def _supported_action(
    idempotency_key: str,
    *,
    action_type: str = 'mapping_alias_upsert',
    risk_level: str = 'low',
    target_table: str | None = None,
) -> dict:
    resolved_target_table = target_table
    if resolved_target_table is None:
        resolved_target_table = {
            'mapping_alias_upsert': 'master_code_aliases',
            'mapping_field_rule_upsert': 'mapping_field_rules',
            'mapping_reconciliation_run': 'mapping_reconciliation_runs',
            'daily_report_recalculate': 'daily_report_runs',
        }.get(action_type, 'master_code_aliases')
    return {
        'idempotency_key': idempotency_key,
        'action_type': action_type,
        'risk_level': risk_level,
        'target_table': resolved_target_table,
        'target_key': 'cold-roll:2050',
        'field_name': 'workshop_output',
        'before_value': {'hub': 95.0},
        'after_value': {'hub': 100.0},
        'evidence': {'source': 'mes'},
        'rollback_payload': {'mode': 'manual', 'restore_before_value': {'hub': 95.0}},
    }


def _supported_action_with_machine_audit_fields(idempotency_key: str) -> dict:
    action = _supported_action(idempotency_key)
    action['evidence'] = {
        'source': 'mes',
        'reason': 'source-of-truth mismatch',
        'field': 'workshop_output',
        'field_name': 'workshop_output',
        'evidence_ref': 'report:2026-06-18',
        'values': {'before': 95.0, 'after': 100.0},
    }
    action['rollback_payload'] = {
        'mode': 'manual',
        'reason': 'restore previous hub value',
        'restore_before_value': {'hub': 95.0},
        'rollback_available': True,
        'rollback_unavailable_reason': '',
    }
    return action


def _mapping_alias_action(
    idempotency_key: str,
    *,
    after_value: dict | None = None,
    before_value: dict | None = None,
    evidence: dict | None = None,
    rollback_payload: dict | None = None,
    risk_level: str = 'low',
) -> dict:
    return {
        'idempotency_key': idempotency_key,
        'action_type': 'mapping_alias_upsert',
        'risk_level': risk_level,
        'target_table': 'master_code_aliases',
        'target_key': 'workshop:cold-roll-2050:2050',
        'field_name': 'alias_code',
        'before_value': before_value
        or {
            'entity_type': 'workshop',
            'canonical_code': 'cold-roll-2050',
            'alias_code': '2050',
            'source_type': 'hermes',
        },
        'after_value': after_value
        or {
            'entity_type': 'workshop',
            'canonical_code': 'cold-roll-2050',
            'alias_code': '2050',
            'alias_name': '冷轧2050',
            'source_type': 'hermes',
            'is_active': True,
        },
        'evidence': evidence
        or {
            'source': 'mes',
            'reason': 'alias reconciliation',
            'field': 'alias_code',
            'field_name': 'alias_code',
            'evidence_ref': 'alias:2026-06-18',
            'values': {'alias_code': '2050', 'canonical_code': 'cold-roll-2050'},
        },
        'rollback_payload': rollback_payload
        or {
            'mode': 'manual',
            'reason': 'restore alias before audit correction',
            'restore_before_value': {
                'entity_type': 'workshop',
                'alias_code': '2050',
                'source_type': 'hermes',
                'record_existed': False,
            },
            'rollback_available': True,
            'rollback_unavailable_reason': '',
        },
    }


def _large_raw_text() -> str:
    return ('RAW-ROW-' * 250) + ' token=secret-token password=top-secret'


def _action_with_large_audit_payload(idempotency_key: str) -> dict:
    large_text = _large_raw_text()
    action = _supported_action(idempotency_key)
    action['before_value'] = {
        'hub': 95.0,
        'rows': [{'raw': large_text, 'raw_text': large_text, 'value': 95.0}],
    }
    action['after_value'] = {
        'hub': 100.0,
        'content': large_text,
        'items': [{'raw_text': large_text, 'value': 100.0}],
    }
    action['evidence'] = {
        'source': 'mes',
        'field_name': 'workshop_output',
        'values': {
            'before': 95.0,
            'after': 100.0,
            'rows': [{'raw': large_text}],
            'raw_text': large_text,
        },
    }
    action['rollback_payload'] = {
        'mode': 'manual',
        'reason': 'restore previous hub value',
        'restore_before_value': {'hub': 95.0},
        'rows': [{'raw': large_text}],
        'content': large_text,
    }
    return action


def _action_with_large_top_level_evidence(idempotency_key: str) -> dict:
    action = _supported_action(idempotency_key)
    action['evidence'] = {
        'source': 'mes',
        'reason': 'source-of-truth mismatch',
        'field': 'workshop_output',
        'field_name': 'workshop_output',
        'evidence_ref': 'report:2026-06-18',
        'handler': 'audit-preview',
        'values': {
            'before': 95.0,
            'after': 100.0,
            'rows': [{'raw': _large_raw_text(), 'raw_text': _large_raw_text(), 'value': 100.0}],
            'content': _large_raw_text(),
        },
        'extra_1': 'alpha',
        'extra_2': 'beta',
        'extra_3': 'gamma',
    }
    return action


def _action_with_large_top_level_rollback_payload(idempotency_key: str) -> dict:
    action = _supported_action(idempotency_key)
    action['rollback_payload'] = {
        'mode': 'manual',
        'reason': 'restore previous hub value',
        'restore_before_value': {
            'hub': 95.0,
            'rows': [{'raw': _large_raw_text(), 'raw_text': _large_raw_text(), 'value': 95.0}],
            'content': _large_raw_text(),
            'note': 'restore snapshot',
        },
        'rollback_available': True,
        'rollback_unavailable_reason': '',
        'extra_1': 'alpha',
        'extra_2': 'beta',
        'extra_3': 'gamma',
        'extra_4': 'delta',
    }
    return action


def _large_top_level_before_after_value(value: float, *, source: str, reason: str) -> dict:
    return {
        'field': 'workshop_output',
        'field_name': 'workshop_output',
        'old_value': value - 1,
        'new_value': value,
        'unit': 'ton',
        'source': source,
        'reason': reason,
        'note': 'keep small fields',
        'extra_1': 'alpha',
        'rows': [{'raw': _large_raw_text(), 'raw_text': _large_raw_text(), 'value': value}],
        'raw_text': _large_raw_text(),
    }


def _action_with_large_top_level_before_after(idempotency_key: str) -> dict:
    action = _supported_action(idempotency_key)
    action['before_value'] = _large_top_level_before_after_value(95.0, source='hub', reason='previous snapshot')
    action['after_value'] = _large_top_level_before_after_value(100.0, source='mes', reason='mes source of truth')
    return action


def _assert_payload_slimmed(payload: dict) -> None:
    large_text = _large_raw_text()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert large_text not in serialized
    assert 'secret-token' not in serialized
    assert 'top-secret' not in serialized
    assert '<redacted>' in serialized


def _assert_text_summary(summary: dict) -> None:
    assert summary['summarized'] is True
    assert summary['truncated'] is True
    assert summary['length'] >= 2000
    assert summary['sha256']
    assert summary['sample']


def _assert_collection_summary(summary: dict) -> None:
    assert summary['summarized'] is True
    assert summary['count'] >= 1
    assert summary['sha256']
    assert summary['sample']


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


def test_create_run_ignores_same_date_png_when_txt_reference_exists(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    (root / '2026-06-18-日报.txt').write_text('车间总产量日合计100吨\n', encoding='utf-8')
    (root / '2026-06-18-截图.png').write_bytes(b'not-a-real-png')
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

        assert run.status == 'completed'
        assert run.source_status['output_skill'] == 'parsed'
        assert run.output_skill_snapshot['parsed'] == {'total_output': 100.0}
        assert 'output_skill' not in run.source_errors
    finally:
        db.close()


def test_create_run_marks_unsupported_only_output_skill_as_missing_source(tmp_path) -> None:
    root = tmp_path / 'output-skill'
    root.mkdir()
    (root / '2026-06-18-截图.png').write_bytes(b'not-a-real-png')
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

        assert run.status == 'completed_with_missing_source'
        assert run.source_status['output_skill'] in {'missing', 'unsupported'}
        assert run.output_skill_snapshot['parsed'] == {}
        assert run.source_errors in ({}, {'output_skill': 'output_skill_source_missing'})
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


def test_create_run_persists_dingtalk_read_only_evidence_summaries() -> None:
    db = _db_session()
    long_text = ('班组确认总产量100吨 ' * 20) + 'token=ding-secret password=ding-pass'
    created_at = _dingtalk_created_at()
    try:
        _add_dingtalk_text_message(
            db,
            text=long_text,
            created_at=created_at,
            source_payload={'sent_at': '2026-06-18T09:00:00+08:00'},
        )
        document, _ = _add_dingtalk_file_document(db, created_at=created_at)
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
            'issues': [],
        }

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        assert run.source_status['dingtalk_text'] == 'ok'
        assert run.source_status['dingtalk_file'] == 'ok'
        text_items = run.source_status['dingtalk_evidence']['dingtalk_text']['items']
        file_items = run.source_status['dingtalk_evidence']['dingtalk_file']['items']
        assert len(text_items) == 1
        assert len(file_items) == 1
        text_item = text_items[0]
        file_item = file_items[0]
        assert text_item['source'] == 'dingtalk_text'
        assert text_item['channel'] == 'dingtalk_group'
        assert text_item['group_id'] == 'ding-group-001'
        assert text_item['trace_id'] == 'trace-ding-text-001'
        assert text_item['sender_external_id'] == 'ding-user-001'
        assert text_item['sent_at'] == '2026-06-18T09:00:00+08:00'
        assert text_item['created_at'].startswith('2026-06-18T09:00:00')
        assert text_item['text_sample'] != long_text
        assert 'ding-secret' not in json.dumps(text_item, ensure_ascii=False)
        assert 'ding-pass' not in json.dumps(text_item, ensure_ascii=False)
        assert '<redacted>' in text_item['text_sample']
        assert text_item['text_hash']
        assert file_item['source'] == 'dingtalk_file'
        assert file_item['document_id'] == document.id
        assert file_item['filename'] == '产量核对.xlsx'
        assert file_item['source_name'] == '钉钉群文件'
        assert file_item['file_size'] == 2048
        assert file_item['created_at'].startswith('2026-06-18T09:00:00')
        assert file_item['source_ref'] == 'dingtalk://files/产量核对.xlsx?token=<redacted>'
        assert file_item['source_type'] == 'dingtalk_file'
        serialized_status = json.dumps(run.source_status, ensure_ascii=False)
        assert long_text not in serialized_status
        assert 'ding-secret' not in serialized_status
        assert 'ding-pass' not in serialized_status
    finally:
        db.close()


def test_create_run_keeps_original_completion_logic_when_no_dingtalk_evidence() -> None:
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
            'issues': [],
        }

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        assert run.status == 'completed'
        assert run.source_status['dingtalk_text'] == 'empty'
        assert run.source_status['dingtalk_file'] == 'empty'
        assert run.source_status['dingtalk_evidence']['dingtalk_text']['items'] == []
        assert run.source_status['dingtalk_evidence']['dingtalk_file']['items'] == []
    finally:
        db.close()


def test_create_run_records_dingtalk_read_failure_without_interrupting_comparison() -> None:
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
            'issues': [],
        }
        service._read_dingtalk_text_evidence = lambda **kwargs: ([], 'failed', 'token=ding-secret unavailable')
        service._read_dingtalk_file_evidence = lambda **kwargs: ([], 'empty', None)

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output'],
        )

        assert run.source_status['dingtalk_text'] == 'failed'
        assert run.source_status['dingtalk_file'] == 'empty'
        assert run.source_errors['dingtalk_text'] == 'token=<redacted> unavailable'
        assert float(run.match_rate) == pytest.approx(1.0)
        assert run.diffs['total_output']['status'] == 'matched'
        assert run.status == 'completed'
    finally:
        db.close()


def test_read_dingtalk_text_evidence_prefers_source_payload_business_time_over_created_at() -> None:
    db = _db_session()
    try:
        for offset in range(25):
            _add_dingtalk_text_message(
                db,
                text=f'不属于6月18业务日的晚到消息 {offset}',
                created_at=_dingtalk_created_at(day=19, hour=9, minute=offset),
                trace_id=f'trace-late-noise-{offset}',
                source_payload={'sent_at': f'2026-06-19T09:{offset:02d}:00+08:00'},
            )
        _add_dingtalk_text_message(
            db,
            text='6月18日夜班总产量100吨',
            created_at=_dingtalk_created_at(day=19, hour=9, minute=5),
            source_payload={'sent_at': '2026-06-18T20:00:00+08:00'},
        )
        service = HermesDataAuditService(db, output_skill_root=None)

        items, status, error = service._read_dingtalk_text_evidence(business_date=date(2026, 6, 18))

        assert error is None
        assert status == 'ok'
        assert len(items) == 1
        assert items[0]['sent_at'] == '2026-06-18T20:00:00+08:00'
        assert items[0]['created_at'].startswith('2026-06-19T09:05:00')
    finally:
        db.close()


def test_read_dingtalk_text_evidence_ignores_non_group_channel_and_uses_created_at_fallback() -> None:
    db = _db_session()
    try:
        _add_dingtalk_text_message(
            db,
            text='单聊消息不能进入群证据',
            channel='dingtalk_single',
            created_at=_dingtalk_created_at(day=18, hour=9),
            trace_id='trace-single-channel',
        )
        _add_dingtalk_text_message(
            db,
            text='6月18业务日内，无sent_at时用created_at兜底',
            created_at=_dingtalk_created_at(day=19, hour=7, minute=40),
            trace_id='trace-created-at-fallback-in-window',
        )
        _add_dingtalk_text_message(
            db,
            text='6月18业务日前十分钟，不应进入',
            created_at=_dingtalk_created_at(day=18, hour=7, minute=40),
            trace_id='trace-created-at-before-window',
        )
        service = HermesDataAuditService(db, output_skill_root=None)

        items, status, error = service._read_dingtalk_text_evidence(business_date=date(2026, 6, 18))

        assert error is None
        assert status == 'ok'
        assert [item['trace_id'] for item in items] == ['trace-created-at-fallback-in-window']
        assert items[0]['sent_at'].startswith('2026-06-19T07:40:00')
    finally:
        db.close()


def test_read_dingtalk_file_evidence_requires_active_dingtalk_ingestion_and_caps_results() -> None:
    db = _db_session()
    created_at = _dingtalk_created_at()
    try:
        inactive_document, _ = _add_dingtalk_file_document(
            db,
            created_at=created_at,
            filename='inactive.xlsx',
            ingestion_status='inactive',
        )
        metadata_only_document, _ = _add_dingtalk_file_document(
            db,
            created_at=_dingtalk_created_at(hour=9, minute=1),
            filename='metadata-only.xlsx',
            source_type='rag_upload',
            source_ref='upload://metadata-only.xlsx',
            document_metadata={'source': 'dingtalk_file', 'channel': 'dingtalk_group'},
            ingestion_metadata={'channel': 'manual_upload'},
        )
        for offset in range(12):
            _add_dingtalk_file_document(
                db,
                created_at=_dingtalk_created_at(hour=11, minute=offset),
                filename=f'manual-noise-{offset}.xlsx',
                source_type='rag_upload',
                source_ref=f'upload://manual-noise-{offset}.xlsx',
                document_metadata={'source': 'dingtalk_file', 'channel': 'dingtalk_group'},
                ingestion_metadata={'channel': 'manual_upload'},
            )
        valid_document_ids: list[int] = []
        for offset in range(6):
            document, _ = _add_dingtalk_file_document(
                db,
                created_at=_dingtalk_created_at(hour=10, minute=offset),
                filename=f'valid-{offset}.xlsx',
                source_ref=f'dingtalk://files/valid-{offset}.xlsx?token=file-secret-{offset}',
            )
            valid_document_ids.append(document.id)
        service = HermesDataAuditService(db, output_skill_root=None)

        items, status, error = service._read_dingtalk_file_evidence(business_date=date(2026, 6, 18))

        assert error is None
        assert status == 'ok'
        assert len(items) == 5
        returned_ids = {item['document_id'] for item in items}
        assert inactive_document.id not in returned_ids
        assert metadata_only_document.id not in returned_ids
        assert returned_ids.issubset(set(valid_document_ids))
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


def test_create_run_changes_run_key_when_dingtalk_evidence_changes() -> None:
    db = _db_session()
    created_at = _dingtalk_created_at()
    try:
        _add_dingtalk_text_message(
            db,
            text='第一条钉钉确认：总产量100吨',
            created_at=created_at,
        )
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
            'issues': [],
        }

        first = service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])
        _add_dingtalk_text_message(
            db,
            text='第二条钉钉确认：总产量101吨',
            created_at=created_at + timedelta(minutes=5),
            trace_id='trace-ding-text-002',
        )
        second = service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])

        assert first.id != second.id
        assert first.run_key != second.run_key
        assert db.query(HermesDataAuditRun).count() == 2
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


def test_create_run_does_not_use_dingtalk_evidence_in_match_rate_or_correction_actions() -> None:
    db = _db_session()
    created_at = _dingtalk_created_at()
    try:
        _add_dingtalk_text_message(
            db,
            text='钉钉里有人说产量是999吨，但这只是说明，不是事实',
            created_at=created_at,
        )
        _add_dingtalk_file_document(db, created_at=created_at)
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
                    'source_status': {'mes': 'ok', 'sources': {'summary': {'status': 'ok', 'count': 2}}},
                    'source_errors': {},
                }
            ),
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 95.0, 'yield_rate': 96.5},
        )
        service._read_output_skill_business_date = lambda business_date: {
            'status': 'parsed',
            'files': ['D:/output-skill/2026-06-18.txt'],
            'raw_text': '',
            'parsed': {'total_output': 100.0, 'yield_rate': 96.5},
            'issues': [],
        }

        run = service.create_run(
            business_date=date(2026, 6, 18),
            fields=['total_output', 'yield_rate'],
        )

        assert float(run.match_rate) == pytest.approx(0.5)
        assert set(run.diffs['total_output']['values']) == {'mes', 'hub', 'output_skill'}
        assert set(run.diffs['yield_rate']['values']) == {'mes', 'hub', 'output_skill'}
        assert run.suggested_actions == [
            {
                'idempotency_key': run.suggested_actions[0]['idempotency_key'],
                'action_type': 'mapping_reconciliation_run',
                'risk_level': 'low',
                'field_name': 'total_output',
                'target_table': 'data_hub_snapshot',
                'target_key': '2026-06-18:total_output',
                'before_value': {'hub': 95.0},
                'after_value': {'suggested_value': 100.0},
                'evidence': {'field_name': 'total_output', 'values': {'mes': 100.0, 'hub': 95.0, 'output_skill': 100.0}},
                'rollback_payload': {
                    'mode': 'manual',
                    'reason': 'hub_snapshot_reconciliation_requires_manual_restore',
                    'restore_before_value': {'hub': 95.0},
                },
            }
        ]
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


def test_create_run_requires_business_date_before_touching_sources() -> None:
    db = _db_session()
    call_counts = {'mes': 0, 'hub': 0, 'output': 0}
    try:
        mes_service = _MesReadServiceFake(_summary_payload())

        def _hub_reader(business_date, fields):
            call_counts['hub'] += 1
            raise AssertionError('hub reader should not be called')

        service = HermesDataAuditService(
            db,
            mes_read_service=mes_service,
            hub_snapshot_reader=_hub_reader,
        )

        def _fail_output_reader(business_date):
            call_counts['output'] += 1
            raise AssertionError('output reader should not be called')

        service._read_output_skill_business_date = _fail_output_reader

        with pytest.raises(ValueError, match='business_date'):
            service.create_run(
                business_date=None,
                fields=['total_output'],
            )

        call_counts['mes'] = len(mes_service.calls)
        assert call_counts == {'mes': 0, 'hub': 0, 'output': 0}
        assert db.query(HermesDataAuditRun).count() == 0
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


def test_create_run_creates_new_run_when_hub_status_changes_with_same_empty_snapshot() -> None:
    db = _db_session()
    try:
        first_service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload()),
            hub_snapshot_reader=lambda business_date, fields: {},
        )

        def _failed_hub_reader(business_date, fields):
            raise RuntimeError('token=hub-secret unavailable')

        second_service = HermesDataAuditService(
            db,
            mes_read_service=_MesReadServiceFake(_summary_payload()),
            hub_snapshot_reader=_failed_hub_reader,
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
        assert first.source_status['hub'] == 'empty'
        assert first.status == 'completed_with_missing_source'
        assert second.source_status['hub'] == 'failed'
        assert second.status == 'completed_with_source_error'
        assert second.source_errors['hub'] == 'token=<redacted> unavailable'
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


def test_create_run_marks_mes_empty_with_hub_and_output_data_as_missing_source() -> None:
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
            hub_snapshot_reader=lambda business_date, fields: {'total_output': 100.0},
        )
        service._read_output_skill_business_date = lambda business_date: {
            'status': 'parsed',
            'files': ['D:/output-skill/2026-06-18.txt'],
            'raw_text': '',
            'parsed': {'total_output': 100.0},
            'issues': [],
        }

        run = service.create_run(business_date=date(2026, 6, 18), fields=['total_output'])

        assert run.diffs['total_output']['status'] == 'mes_missing'
        assert run.status == 'completed_with_missing_source'
    finally:
        db.close()


def test_completed_run_status_keeps_mes_source_error_priority_over_empty_sources() -> None:
    status = HermesDataAuditService._completed_run_status(
        source_status={
            'mes': 'partial_failed',
            'hub': 'empty',
            'output_skill': 'parsed',
        },
        source_errors={'mes': {'stock_records': 'timeout'}},
    )

    assert status == 'completed_with_source_error'


def test_completed_run_status_ignores_dingtalk_source_errors() -> None:
    status = HermesDataAuditService._completed_run_status(
        source_status={
            'mes': 'ok',
            'hub': 'ok',
            'output_skill': 'parsed',
            'dingtalk_text': 'failed',
            'dingtalk_file': 'empty',
        },
        source_errors={'dingtalk_text': 'token=<redacted> unavailable'},
    )

    assert status == 'completed'


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


def test_apply_corrections_can_retry_same_blocked_action_after_apply_enabled_changes() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        action = _mapping_alias_action('retry-after-blocked')

        blocked_service = HermesDataAuditService(db, apply_enabled=False)
        first = blocked_service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=9,
        )

        blocked_row = db.query(HermesCorrectionAction).filter_by(idempotency_key='retry-after-blocked').one()
        blocked_row_id = blocked_row.id
        db.refresh(run)
        assert first['reason'] == 'apply_disabled'
        assert first['blocked_count'] == 1
        assert blocked_row.status == 'blocked'
        assert run.status == 'correction_blocked'

        retry_service = HermesDataAuditService(db, apply_enabled=True)
        second = retry_service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=9,
        )

        action_row = db.query(HermesCorrectionAction).filter_by(idempotency_key='retry-after-blocked').one()
        alias_rows = db.query(MasterCodeAlias).filter_by(entity_type='workshop', alias_code='2050', source_type='hermes').all()
        db.refresh(run)
        assert second['applied_count'] == 1
        assert second['blocked_count'] == 0
        assert second['created_count'] == 0
        assert second['action_statuses'] == [{'idempotency_key': 'retry-after-blocked', 'status': 'applied'}]
        assert action_row.id == blocked_row_id
        assert action_row.status == 'applied'
        assert len(alias_rows) == 1
        assert run.status == 'corrected'
        assert db.query(HermesCorrectionAction).count() == 1
    finally:
        db.close()


def test_apply_corrections_allows_dry_run_when_apply_flag_disabled() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=False)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('dry-run-flag-off')],
            dry_run=True,
            applied_by_id=9,
        )

        assert result['dry_run_count'] == 1
        assert result['blocked_count'] == 0
        assert result['action_statuses'] == [{'idempotency_key': 'dry-run-flag-off', 'status': 'dry_run'}]
        assert db.query(HermesCorrectionAction).count() == 0
    finally:
        db.close()


def test_apply_corrections_blocks_real_apply_for_corrected_run_without_side_effects() -> None:
    db = _db_session()
    executor_called = {'value': False}
    try:
        run = _make_run(db)
        run.status = 'corrected'
        db.commit()
        service = HermesDataAuditService(db, apply_enabled=True)

        def _unexpected_executor(action):
            executor_called['value'] = True
            return {'evidence': {'handler': 'should-not-run'}}

        service._execute_mapping_alias_upsert = _unexpected_executor
        action = _supported_action('corrected-real-apply-blocked')
        action['target_key'] = 'workshop:cold-roll-2050:corrected'
        action['before_value'] = {
            'entity_type': 'workshop',
            'canonical_code': 'cold-roll-2050',
            'alias_code': 'corrected',
            'source_type': 'hermes',
        }
        action['after_value'] = {
            'entity_type': 'workshop',
            'canonical_code': 'cold-roll-2050',
            'alias_code': 'corrected',
            'alias_name': '已修正别名',
            'source_type': 'hermes',
            'is_active': True,
        }
        action['evidence'] = {
            'source': 'mes',
            'reason': 'corrected run must rerun before real apply',
            'field': 'alias_code',
            'field_name': 'alias_code',
            'evidence_ref': 'corrected-run:2026-06-18',
            'values': {'alias_code': 'corrected', 'canonical_code': 'cold-roll-2050'},
        }
        action['rollback_payload'] = {
            'mode': 'manual',
            'reason': 'restore alias before audit correction',
            'restore_before_value': {
                'entity_type': 'workshop',
                'alias_code': 'corrected',
                'source_type': 'hermes',
                'record_existed': False,
            },
            'rollback_available': True,
            'rollback_unavailable_reason': '',
        }

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=9,
        )

        assert result['reason'] == 'rerun_audit_required'
        assert result['blocked_count'] == 1
        assert result['applied_count'] == 0
        assert result['dry_run_count'] == 0
        assert result['created_count'] == 0
        assert result['failed_count'] == 0
        assert result['skipped_count'] == 0
        assert result['action_statuses'] == [
            {
                'idempotency_key': 'corrected-real-apply-blocked',
                'status': 'blocked',
                'reason': 'rerun_audit_required',
            }
        ]
        assert executor_called['value'] is False
        assert db.query(HermesCorrectionAction).count() == 0
        assert (
            db.query(MasterCodeAlias)
            .filter_by(entity_type='workshop', alias_code='corrected', source_type='hermes')
            .count()
            == 0
        )
        db.refresh(run)
        assert run.status == 'corrected'
    finally:
        db.close()


def test_apply_corrections_allows_dry_run_preview_for_corrected_run() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        run.status = 'corrected'
        db.commit()
        service = HermesDataAuditService(db, apply_enabled=True)
        action = _supported_action('corrected-dry-run-preview')
        action['target_key'] = 'workshop:cold-roll-2050:corrected-preview'
        action['before_value'] = {
            'entity_type': 'workshop',
            'canonical_code': 'cold-roll-2050',
            'alias_code': 'corrected-preview',
            'source_type': 'hermes',
        }
        action['after_value'] = {
            'entity_type': 'workshop',
            'canonical_code': 'cold-roll-2050',
            'alias_code': 'corrected-preview',
            'alias_name': '已修正预览别名',
            'source_type': 'hermes',
            'is_active': True,
        }
        action['evidence'] = {
            'source': 'mes',
            'reason': 'corrected run dry-run preview remains available',
            'field': 'alias_code',
            'field_name': 'alias_code',
            'evidence_ref': 'corrected-preview:2026-06-18',
            'values': {'alias_code': 'corrected-preview', 'canonical_code': 'cold-roll-2050'},
        }
        action['rollback_payload'] = {
            'mode': 'manual',
            'reason': 'restore alias before audit correction',
            'restore_before_value': {
                'entity_type': 'workshop',
                'alias_code': 'corrected-preview',
                'source_type': 'hermes',
                'record_existed': False,
            },
            'rollback_available': True,
            'rollback_unavailable_reason': '',
        }

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=True,
            applied_by_id=9,
        )

        assert result['reason'] is None
        assert result['dry_run_count'] == 1
        assert result['blocked_count'] == 0
        assert result['action_statuses'] == [
            {'idempotency_key': 'corrected-dry-run-preview', 'status': 'dry_run'}
        ]
        assert db.query(HermesCorrectionAction).count() == 0
        assert (
            db.query(MasterCodeAlias)
            .filter_by(entity_type='workshop', alias_code='corrected-preview', source_type='hermes')
            .count()
            == 0
        )
        db.refresh(run)
        assert run.status == 'corrected'
    finally:
        db.close()


def test_apply_corrections_blocks_real_apply_for_partial_failed_run_without_side_effects() -> None:
    db = _db_session()
    executor_called = {'value': False}
    try:
        run = _make_run(db)
        run.status = 'correction_partial_failed'
        db.commit()
        service = HermesDataAuditService(db, apply_enabled=True)

        def _unexpected_executor(action):
            executor_called['value'] = True
            return {'evidence': {'handler': 'should-not-run'}}

        service._execute_mapping_alias_upsert = _unexpected_executor
        action = _supported_action('partial-failed-real-apply-blocked')
        action['target_key'] = 'workshop:cold-roll-2050:partial-failed'
        action['before_value'] = {
            'entity_type': 'workshop',
            'canonical_code': 'cold-roll-2050',
            'alias_code': 'partial-failed',
            'source_type': 'hermes',
        }
        action['after_value'] = {
            'entity_type': 'workshop',
            'canonical_code': 'cold-roll-2050',
            'alias_code': 'partial-failed',
            'alias_name': '部分失败别名',
            'source_type': 'hermes',
            'is_active': True,
        }
        action['evidence'] = {
            'source': 'mes',
            'reason': 'partial failed run must rerun before real apply',
            'field': 'alias_code',
            'field_name': 'alias_code',
            'evidence_ref': 'partial-failed-run:2026-06-18',
            'values': {'alias_code': 'partial-failed', 'canonical_code': 'cold-roll-2050'},
        }
        action['rollback_payload'] = {
            'mode': 'manual',
            'reason': 'restore alias before audit correction',
            'restore_before_value': {
                'entity_type': 'workshop',
                'alias_code': 'partial-failed',
                'source_type': 'hermes',
                'record_existed': False,
            },
            'rollback_available': True,
            'rollback_unavailable_reason': '',
        }

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=9,
        )

        assert result['reason'] == 'rerun_audit_required'
        assert result['blocked_count'] == 1
        assert result['applied_count'] == 0
        assert result['action_statuses'] == [
            {
                'idempotency_key': 'partial-failed-real-apply-blocked',
                'status': 'blocked',
                'reason': 'rerun_audit_required',
            }
        ]
        assert executor_called['value'] is False
        assert db.query(HermesCorrectionAction).count() == 0
        assert (
            db.query(MasterCodeAlias)
            .filter_by(entity_type='workshop', alias_code='partial-failed', source_type='hermes')
            .count()
            == 0
        )
        db.refresh(run)
        assert run.status == 'correction_partial_failed'
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


def test_apply_corrections_blocks_when_rollback_payload_is_empty() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True)
        action = _supported_action('empty-rollback-payload')
        action['rollback_payload'] = {}

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=3,
        )

        row = db.query(HermesCorrectionAction).one()
        assert result['blocked_count'] == 1
        assert row.status == 'blocked'
        assert row.evidence['blocked_reason'] == 'incomplete_correction_audit_payload'
    finally:
        db.close()


def test_apply_corrections_accepts_rollback_unavailable_reason_metadata() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True)
        action = _supported_action('rollback-unavailable', action_type='mapping_field_rule_upsert')
        action['rollback_payload'] = {
            'rollback_available': False,
            'rollback_unavailable_reason': 'external side effect',
        }

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=3,
        )

        row = db.query(HermesCorrectionAction).one()
        assert result['blocked_count'] == 1
        assert row.status == 'blocked'
        assert row.evidence['blocked_reason'] == 'executor_not_supported'
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


def test_apply_corrections_blocks_invalid_action_target_pair() -> None:
    db = _db_session()
    called = {'value': False}
    try:
        run = _make_run(db)

        def _handler(action):
            called['value'] = True
            return {'evidence': {'handler': 'ok'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)
        action = _supported_action('crossed-pair')
        action['target_table'] = 'daily_report_runs'

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
        assert row.evidence['blocked_reason'] == 'target_table_not_allowed_for_action'
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
        assert result['action_statuses'] == [{'idempotency_key': 'dry-run-no-row', 'status': 'dry_run'}]
        assert db.query(HermesCorrectionAction).count() == 0
        assert not db.new
        assert not db.dirty
    finally:
        db.close()


def test_apply_corrections_dry_run_previews_gate_failures_without_persisting_or_dirtying_session() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True)
        missing_metadata_action = _supported_action('dry-run-missing-metadata')
        missing_metadata_action.pop('rollback_payload')

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                _supported_action('dry-run-unsupported', action_type='review_field_mismatch'),
                _supported_action('dry-run-mes-target', target_table='mes_work_orders'),
                _supported_action('dry-run-high-risk', risk_level='high'),
                missing_metadata_action,
            ],
            dry_run=True,
            applied_by_id=9,
        )

        assert result['dry_run_count'] == 0
        assert result['blocked_count'] == 4
        assert result['action_statuses'] == [
            {
                'idempotency_key': 'dry-run-unsupported',
                'status': 'blocked',
                'reason': 'unsupported_action_type',
            },
            {
                'idempotency_key': 'dry-run-mes-target',
                'status': 'blocked',
                'reason': 'mes_target_read_only',
            },
            {
                'idempotency_key': 'dry-run-high-risk',
                'status': 'high_risk_blocked',
                'reason': 'high_risk',
            },
            {
                'idempotency_key': 'dry-run-missing-metadata',
                'status': 'blocked',
                'reason': 'incomplete_correction_audit_payload',
            },
        ]
        assert db.query(HermesCorrectionAction).count() == 0
        assert not db.new
        assert not db.dirty
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
            target_table='master_code_aliases',
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
        action = _mapping_alias_action('dry-then-apply')

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
        alias_row = db.query(MasterCodeAlias).filter_by(entity_type='workshop', alias_code='2050', source_type='hermes').one()
        assert preview['action_statuses'] == [{'idempotency_key': 'dry-then-apply', 'status': 'dry_run'}]
        assert applied['action_statuses'] == [{'idempotency_key': 'dry-then-apply', 'status': 'applied'}]
        assert len(handler_calls) == 0
        assert action_row.status == 'applied'
        assert alias_row.canonical_code == 'cold-roll-2050'
    finally:
        db.close()


def test_apply_corrections_does_not_reassign_pending_action_from_other_run() -> None:
    db = _db_session()
    try:
        run1 = _make_run(db, run_key='run-1')
        run2 = _make_run(db, run_key='run-2')
        existing = HermesCorrectionAction(
            audit_run_id=run1.id,
            idempotency_key='shared-key',
            action_type='mapping_alias_upsert',
            risk_level='low',
            target_table='master_code_aliases',
            target_key='run1-original-target',
            field_name='workshop_output',
            before_value={'hub': 95.0},
            after_value={'hub': 96.0},
            evidence={'source': 'mes', 'reason': 'run1 pending action'},
            rollback_payload={'mode': 'manual', 'restore_before_value': {'hub': 95.0}},
            status='pending',
            rollback_status='not_requested',
        )
        db.add(existing)
        db.commit()

        service = HermesDataAuditService(db, apply_enabled=True)
        result = service.apply_corrections(
            audit_run_id=run2.id,
            actions=[_mapping_alias_action('shared-key')],
            dry_run=False,
            applied_by_id=9,
        )

        db.refresh(existing)
        db.refresh(run2)
        assert result['applied_count'] == 0
        assert result['blocked_count'] == 1
        assert result['skipped_count'] == 0
        assert result['action_statuses'] == [
            {
                'idempotency_key': 'shared-key',
                'status': 'blocked_duplicate',
                'reason': 'duplicate_in_other_run_pending',
                'existing_audit_run_id': run1.id,
                'existing_action_status': 'pending',
            }
        ]
        assert existing.audit_run_id == run1.id
        assert existing.status == 'pending'
        assert existing.target_key == 'run1-original-target'
        assert existing.after_value == {'hub': 96.0}
        assert db.query(HermesCorrectionAction).count() == 1
        assert db.query(MasterCodeAlias).count() == 0
        assert run2.status == 'correction_blocked'
    finally:
        db.close()


def test_apply_corrections_blocks_repeat_real_apply_after_run_becomes_corrected() -> None:
    db = _db_session()
    handler_calls: list[dict] = []
    try:
        run = _make_run(db)

        def _handler(action):
            handler_calls.append(action)
            return {'evidence': {'handler': 'applied'}}

        _handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_handler)
        action = _mapping_alias_action('repeat-real-apply')

        first = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=9,
        )
        second = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=9,
        )

        action_row = db.query(HermesCorrectionAction).filter_by(idempotency_key='repeat-real-apply').one()
        alias_rows = db.query(MasterCodeAlias).filter_by(entity_type='workshop', alias_code='2050', source_type='hermes').all()
        assert first['action_statuses'] == [{'idempotency_key': 'repeat-real-apply', 'status': 'applied'}]
        assert second['reason'] == 'rerun_audit_required'
        assert second['action_statuses'] == [
            {
                'idempotency_key': 'repeat-real-apply',
                'status': 'blocked',
                'reason': 'rerun_audit_required',
            }
        ]
        assert second['applied_count'] == 0
        assert second['blocked_count'] == 1
        assert second['skipped_count'] == 0
        assert len(handler_calls) == 0
        assert action_row.status == 'applied'
        assert len(alias_rows) == 1
    finally:
        db.close()


def test_apply_corrections_historical_duplicate_does_not_block_new_action_in_same_batch() -> None:
    db = _db_session()
    try:
        run1 = _make_run(db, run_key='run-1')
        run2 = _make_run(db, run_key='run-2')
        historical = HermesCorrectionAction(
            audit_run_id=run1.id,
            idempotency_key='historical-applied',
            action_type='mapping_alias_upsert',
            risk_level='low',
            target_table='master_code_aliases',
            target_key='run1:2050',
            field_name='alias_code',
            before_value={'entity_type': 'workshop', 'alias_code': '2050-old'},
            after_value={'entity_type': 'workshop', 'canonical_code': 'cold-roll-2050', 'alias_code': '2050-old'},
            evidence={'source': 'mes', 'reason': 'historical apply'},
            rollback_payload={'mode': 'manual', 'restore_before_value': {'entity_type': 'workshop', 'alias_code': '2050-old'}},
            status='applied',
            rollback_status='not_requested',
            applied_by_id=3,
        )
        db.add(historical)
        db.commit()

        new_action = _mapping_alias_action('new-current-action')
        new_action['target_key'] = 'workshop:cold-roll-2050:2051'
        new_action['before_value']['alias_code'] = '2051'
        new_action['after_value']['alias_code'] = '2051'
        new_action['after_value']['alias_name'] = '冷轧2051'
        new_action['rollback_payload']['restore_before_value']['alias_code'] = '2051'
        new_action['evidence']['values']['alias_code'] = '2051'

        service = HermesDataAuditService(db, apply_enabled=True)
        result = service.apply_corrections(
            audit_run_id=run2.id,
            actions=[_mapping_alias_action('historical-applied'), new_action],
            dry_run=False,
            applied_by_id=9,
        )

        db.refresh(historical)
        new_row = db.query(HermesCorrectionAction).filter_by(idempotency_key='new-current-action').one()
        alias_row = db.query(MasterCodeAlias).filter_by(entity_type='workshop', alias_code='2051', source_type='hermes').one()
        assert result['applied_count'] == 1
        assert result['skipped_count'] == 1
        assert result['blocked_count'] == 0
        assert result['action_statuses'] == [
            {
                'idempotency_key': 'historical-applied',
                'status': 'skipped_duplicate',
                'reason': 'duplicate_in_other_run_terminal',
                'existing_audit_run_id': run1.id,
                'existing_action_status': 'applied',
            },
            {'idempotency_key': 'new-current-action', 'status': 'applied'},
        ]
        assert historical.audit_run_id == run1.id
        assert historical.status == 'applied'
        assert new_row.audit_run_id == run2.id
        assert new_row.status == 'applied'
        assert alias_row.canonical_code == 'cold-roll-2050'
    finally:
        db.close()


def test_apply_corrections_repeat_real_apply_reports_only_rerun_gate_status() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True)
        action = _mapping_alias_action('repeat-status-check')

        service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=9,
        )
        second = service.apply_corrections(
            audit_run_id=run.id,
            actions=[action],
            dry_run=False,
            applied_by_id=9,
        )

        assert second['reason'] == 'rerun_audit_required'
        statuses = [item['status'] for item in second['action_statuses'] if item['idempotency_key'] == 'repeat-status-check']
        assert statuses == ['blocked']
    finally:
        db.close()


def test_apply_corrections_current_batch_gate_only_uses_new_current_run_actions() -> None:
    db = _db_session()
    try:
        run1 = _make_run(db, run_key='run-1')
        run2 = _make_run(db, run_key='run-2')
        historical = HermesCorrectionAction(
            audit_run_id=run1.id,
            idempotency_key='historical-applied',
            action_type='mapping_alias_upsert',
            risk_level='low',
            target_table='master_code_aliases',
            target_key='run1:2050',
            field_name='alias_code',
            before_value={'entity_type': 'workshop', 'alias_code': '2050-old'},
            after_value={'entity_type': 'workshop', 'canonical_code': 'cold-roll-2050', 'alias_code': '2050-old'},
            evidence={'source': 'mes', 'reason': 'historical apply'},
            rollback_payload={'mode': 'manual', 'restore_before_value': {'entity_type': 'workshop', 'alias_code': '2050-old'}},
            status='applied',
            rollback_status='not_requested',
            applied_by_id=3,
        )
        db.add(historical)
        db.commit()

        valid_action = _mapping_alias_action('new-valid-action')
        valid_action['target_key'] = 'workshop:cold-roll-2050:2052'
        valid_action['before_value']['alias_code'] = '2052'
        valid_action['after_value']['alias_code'] = '2052'
        valid_action['after_value']['alias_name'] = '冷轧2052'
        valid_action['rollback_payload']['restore_before_value']['alias_code'] = '2052'
        valid_action['evidence']['values']['alias_code'] = '2052'

        service = HermesDataAuditService(db, apply_enabled=True)
        result = service.apply_corrections(
            audit_run_id=run2.id,
            actions=[
                _mapping_alias_action('historical-applied'),
                valid_action,
                _supported_action('unsupported-new-action', action_type='mapping_field_rule_upsert'),
            ],
            dry_run=False,
            applied_by_id=9,
        )

        rows = db.query(HermesCorrectionAction).order_by(HermesCorrectionAction.id).all()
        db.refresh(run2)
        assert result['applied_count'] == 0
        assert result['skipped_count'] == 1
        assert result['blocked_count'] == 2
        assert result['failed_count'] == 0
        assert result['action_statuses'] == [
            {
                'idempotency_key': 'historical-applied',
                'status': 'skipped_duplicate',
                'reason': 'duplicate_in_other_run_terminal',
                'existing_audit_run_id': run1.id,
                'existing_action_status': 'applied',
            },
            {
                'idempotency_key': 'unsupported-new-action',
                'status': 'blocked',
                'reason': 'executor_not_supported',
            },
            {
                'idempotency_key': 'new-valid-action',
                'status': 'blocked',
            },
        ]
        assert [row.idempotency_key for row in rows] == ['historical-applied', 'new-valid-action', 'unsupported-new-action']
        assert rows[0].audit_run_id == run1.id
        assert rows[0].status == 'applied'
        assert rows[1].audit_run_id == run2.id
        assert rows[1].status == 'blocked'
        assert rows[1].evidence['blocked_reason'] == 'batch_not_all_executable'
        assert rows[2].audit_run_id == run2.id
        assert rows[2].status == 'blocked'
        assert rows[2].evidence['blocked_reason'] == 'executor_not_supported'
        assert db.query(MasterCodeAlias).count() == 0
        assert run2.status == 'correction_blocked'
    finally:
        db.close()


def test_apply_corrections_ignores_external_controlled_handler_in_real_apply(tmp_path) -> None:
    db = _db_session()
    external_engine = create_engine(f"sqlite:///{tmp_path / 'external-handler.db'}", future=True)
    Base.metadata.create_all(bind=external_engine, tables=[User.__table__])
    external_db = Session(external_engine)
    called = {'value': 0}
    try:
        run = _make_run(db)

        def _controlled_handler(action):
            called['value'] += 1
            external_db.add(User(username='external-user', name='External User', password_hash='x'))
            external_db.commit()
            raise RuntimeError('should never run')

        _controlled_handler.hermes_controlled_transaction = True
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=_controlled_handler)
        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_mapping_alias_action('ignore-external-handler')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        alias_row = db.query(MasterCodeAlias).filter_by(entity_type='workshop', alias_code='2050', source_type='hermes').one()
        assert called['value'] == 0
        assert result['applied_count'] == 1
        assert action.status == 'applied'
        assert alias_row.canonical_code == 'cold-roll-2050'
        assert external_db.query(User).filter_by(username='external-user').count() == 0
        db.refresh(run)
        assert run.status == 'corrected'
    finally:
        external_db.close()
        db.close()


def test_apply_corrections_blocks_action_without_internal_executor() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True, correction_handler=None)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('action-without-executor', action_type='mapping_field_rule_upsert')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['blocked_count'] == 1
        assert action.status == 'blocked'
        assert action.evidence['blocked_reason'] == 'executor_not_supported'
    finally:
        db.close()


def test_apply_corrections_rolls_back_whole_batch_when_one_alias_upsert_fails() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                _mapping_alias_action('will-pass'),
                _mapping_alias_action(
                    'will-fail',
                    after_value={
                        'entity_type': 'workshop',
                        'canonical_code': 'cold-roll-2050',
                        'alias_name': '冷轧2050',
                        'source_type': 'hermes',
                        'is_active': True,
                    },
                ),
            ],
            dry_run=False,
            applied_by_id=3,
        )

        rows = db.query(HermesCorrectionAction).order_by(HermesCorrectionAction.id).all()
        assert result['applied_count'] == 0
        assert result['failed_count'] == 2
        assert [row.status for row in rows] == ['failed', 'failed']
        assert db.query(MasterCodeAlias).filter_by(entity_type='workshop', alias_code='2050', source_type='hermes').count() == 0
        db.refresh(run)
        assert run.status == 'correction_failed'
    finally:
        db.close()


def test_apply_corrections_can_retry_same_failed_action_with_fixed_payload() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True)
        broken_action = _mapping_alias_action(
            'retry-after-failed',
            after_value={
                'entity_type': 'workshop',
                'canonical_code': 'cold-roll-2050',
                'alias_name': '冷轧2050',
                'source_type': 'hermes',
                'is_active': True,
            },
        )

        first = service.apply_corrections(
            audit_run_id=run.id,
            actions=[broken_action],
            dry_run=False,
            applied_by_id=3,
        )

        failed_row = db.query(HermesCorrectionAction).filter_by(idempotency_key='retry-after-failed').one()
        failed_row_id = failed_row.id
        db.refresh(run)
        assert first['applied_count'] == 0
        assert first['failed_count'] == 1
        assert failed_row.status == 'failed'
        assert run.status == 'correction_failed'
        assert db.query(MasterCodeAlias).count() == 0

        second = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_mapping_alias_action('retry-after-failed')],
            dry_run=False,
            applied_by_id=3,
        )

        action_row = db.query(HermesCorrectionAction).filter_by(idempotency_key='retry-after-failed').one()
        alias_row = db.query(MasterCodeAlias).filter_by(entity_type='workshop', alias_code='2050', source_type='hermes').one()
        db.refresh(run)
        assert second['applied_count'] == 1
        assert second['failed_count'] == 0
        assert second['created_count'] == 0
        assert second['action_statuses'] == [{'idempotency_key': 'retry-after-failed', 'status': 'applied'}]
        assert action_row.id == failed_row_id
        assert action_row.status == 'applied'
        assert alias_row.canonical_code == 'cold-roll-2050'
        assert run.status == 'corrected'
        assert db.query(HermesCorrectionAction).count() == 1
    finally:
        db.close()


def test_apply_corrections_blocks_whole_batch_when_mixed_with_unsupported_executor_action() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[
                _mapping_alias_action('would-otherwise-apply'),
                _supported_action('will-block', action_type='mapping_field_rule_upsert'),
            ],
            dry_run=False,
            applied_by_id=3,
        )

        rows = db.query(HermesCorrectionAction).order_by(HermesCorrectionAction.id).all()
        assert result['applied_count'] == 0
        assert result['blocked_count'] == 2
        assert result['failed_count'] == 0
        assert [row.status for row in rows] == ['blocked', 'blocked']
        assert rows[0].evidence['blocked_reason'] == 'batch_not_all_executable'
        assert rows[1].evidence['blocked_reason'] == 'executor_not_supported'
        assert db.query(MasterCodeAlias).filter_by(entity_type='workshop', alias_code='2050', source_type='hermes').count() == 0
        db.refresh(run)
        assert run.status == 'correction_blocked'
        assert run.status != 'corrected'
    finally:
        db.close()


def test_apply_corrections_marks_applied_when_internal_alias_executor_succeeds() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=True)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_mapping_alias_action('applied-action')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        alias_row = db.query(MasterCodeAlias).filter_by(entity_type='workshop', alias_code='2050', source_type='hermes').one()
        assert result['applied_count'] == 1
        assert action.status == 'applied'
        assert action.before_value['entity_type'] == 'workshop'
        assert action.before_value['alias_code'] == '2050'
        assert action.before_value['record_existed'] is False
        assert action.after_value['entity_type'] == 'workshop'
        assert action.after_value['canonical_code'] == 'cold-roll-2050'
        assert action.after_value['alias_code'] == '2050'
        assert action.after_value['source_type'] == 'hermes'
        assert action.after_value['is_active'] is True
        assert action.evidence['source'] == 'mes'
        assert action.evidence['reason'] == 'alias reconciliation'
        assert action.evidence['field'] == 'alias_code'
        assert action.evidence['field_name'] == 'alias_code'
        assert action.evidence['evidence_ref'] == 'alias:2026-06-18'
        assert action.evidence['values'] == {'alias_code': '2050', 'canonical_code': 'cold-roll-2050'}
        assert action.evidence['executor'] == 'mapping_alias_upsert'
        assert action.rollback_payload['mode'] == 'manual'
        assert action.rollback_payload['reason'] == 'restore alias before audit correction'
        assert action.rollback_payload['restore_before_value']['record_existed'] is False
        assert action.rollback_payload['rollback_available'] is True
        assert action.rollback_payload['rollback_unavailable_reason'] == ''
        assert action.rollback_payload['executor'] == 'mapping_alias_upsert'
        assert alias_row.canonical_code == 'cold-roll-2050'
        assert alias_row.alias_name == '冷轧2050'
        db.refresh(run)
        assert run.status == 'corrected'
    finally:
        db.close()


def test_apply_corrections_slims_large_initial_audit_payloads_before_persisting() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=False)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_action_with_large_audit_payload('slim-initial-payload')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['blocked_count'] == 1
        assert action.before_value['hub'] == 95.0
        assert action.after_value['hub'] == 100.0
        assert action.evidence['source'] == 'mes'
        assert action.evidence['field_name'] == 'workshop_output'
        assert action.rollback_payload['mode'] == 'manual'
        assert action.rollback_payload['restore_before_value'] == {'hub': 95.0}
        _assert_collection_summary(action.before_value['rows'])
        _assert_text_summary(action.after_value['content'])
        _assert_collection_summary(action.after_value['items'])
        _assert_collection_summary(action.evidence['values']['rows'])
        _assert_text_summary(action.evidence['values']['raw_text'])
        _assert_collection_summary(action.rollback_payload['rows'])
        _assert_text_summary(action.rollback_payload['content'])
        _assert_payload_slimmed(action.before_value)
        _assert_payload_slimmed(action.after_value)
        _assert_payload_slimmed(action.evidence)
        _assert_payload_slimmed(action.rollback_payload)
    finally:
        db.close()


def test_apply_corrections_keeps_large_top_level_evidence_machine_fields() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=False)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_action_with_large_top_level_evidence('large-top-level-evidence')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['blocked_count'] == 1
        assert action.evidence['source'] == 'mes'
        assert action.evidence['reason'] == 'source-of-truth mismatch'
        assert action.evidence['field'] == 'workshop_output'
        assert action.evidence['field_name'] == 'workshop_output'
        assert action.evidence['evidence_ref'] == 'report:2026-06-18'
        assert action.evidence['handler'] == 'audit-preview'
        assert action.evidence['extra_1'] == 'alpha'
        assert action.evidence['values']['before'] == 95.0
        assert action.evidence['values']['after'] == 100.0
        _assert_collection_summary(action.evidence['values']['rows'])
        _assert_text_summary(action.evidence['values']['content'])
        _assert_payload_slimmed(action.evidence)
    finally:
        db.close()


def test_apply_corrections_keeps_large_top_level_rollback_machine_fields() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=False)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_action_with_large_top_level_rollback_payload('large-top-level-rollback')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['blocked_count'] == 1
        assert action.rollback_payload['mode'] == 'manual'
        assert action.rollback_payload['reason'] == 'restore previous hub value'
        assert action.rollback_payload['rollback_available'] is True
        assert action.rollback_payload['rollback_unavailable_reason'] == ''
        assert action.rollback_payload['extra_1'] == 'alpha'
        assert action.rollback_payload['restore_before_value']['hub'] == 95.0
        assert action.rollback_payload['restore_before_value']['note'] == 'restore snapshot'
        _assert_collection_summary(action.rollback_payload['restore_before_value']['rows'])
        _assert_text_summary(action.rollback_payload['restore_before_value']['content'])
        _assert_payload_slimmed(action.rollback_payload)
    finally:
        db.close()


def test_apply_corrections_keeps_large_top_level_before_after_machine_fields() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=False)

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_action_with_large_top_level_before_after('large-top-level-before-after')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['blocked_count'] == 1
        assert action.before_value['field'] == 'workshop_output'
        assert action.before_value['field_name'] == 'workshop_output'
        assert action.before_value['old_value'] == 94.0
        assert action.before_value['new_value'] == 95.0
        assert action.before_value['unit'] == 'ton'
        assert action.before_value['source'] == 'hub'
        assert action.before_value['reason'] == 'previous snapshot'
        assert action.before_value['note'] == 'keep small fields'
        assert action.before_value['extra_1'] == 'alpha'
        assert action.after_value['field'] == 'workshop_output'
        assert action.after_value['field_name'] == 'workshop_output'
        assert action.after_value['old_value'] == 99.0
        assert action.after_value['new_value'] == 100.0
        assert action.after_value['unit'] == 'ton'
        assert action.after_value['source'] == 'mes'
        assert action.after_value['reason'] == 'mes source of truth'
        assert action.after_value['note'] == 'keep small fields'
        assert action.after_value['extra_1'] == 'alpha'
        _assert_collection_summary(action.before_value['rows'])
        _assert_text_summary(action.before_value['raw_text'])
        _assert_collection_summary(action.after_value['rows'])
        _assert_text_summary(action.after_value['raw_text'])
        _assert_payload_slimmed(action.before_value)
        _assert_payload_slimmed(action.after_value)
    finally:
        db.close()


def test_apply_corrections_slims_large_executor_result_payloads_before_persisting() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _executor(action):
            return {
                'before_value': {
                    'hub': 95.0,
                    'rows': [{'raw': _large_raw_text(), 'raw_text': _large_raw_text(), 'value': 95.0}],
                },
                'after_value': {
                    'hub': 96.5,
                    'content': _large_raw_text(),
                },
                'evidence': {
                    'handler': 'ok',
                    'source': '',
                    'field_name': None,
                    'values': {
                        'rows': [{'raw': _large_raw_text()}],
                        'raw_text': _large_raw_text(),
                    },
                },
                'rollback_payload': {
                    'reason': '',
                    'restore_before_value': {
                        'rows': [{'raw': _large_raw_text(), 'raw_text': _large_raw_text(), 'value': 95.0}],
                        'content': _large_raw_text(),
                    },
                    'payload': {'raw_text': _large_raw_text()},
                },
            }

        service = HermesDataAuditService(db, apply_enabled=True)
        service._execute_mapping_alias_upsert = _executor

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action_with_machine_audit_fields('slim-handler-result')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['applied_count'] == 1
        assert action.status == 'applied'
        assert action.before_value['hub'] == 95.0
        assert action.after_value['hub'] == 96.5
        assert action.evidence['source'] == 'mes'
        assert action.evidence['reason'] == 'source-of-truth mismatch'
        assert action.evidence['field_name'] == 'workshop_output'
        assert action.evidence['values']['before'] == 95.0
        assert action.evidence['values']['after'] == 100.0
        assert action.rollback_payload['mode'] == 'manual'
        assert action.rollback_payload['reason'] == 'restore previous hub value'
        assert action.rollback_payload['restore_before_value']['hub'] == 95.0
        _assert_collection_summary(action.before_value['rows'])
        _assert_text_summary(action.after_value['content'])
        _assert_collection_summary(action.evidence['values']['rows'])
        _assert_text_summary(action.evidence['values']['raw_text'])
        _assert_collection_summary(action.rollback_payload['restore_before_value']['rows'])
        _assert_text_summary(action.rollback_payload['restore_before_value']['content'])
        _assert_collection_summary(action.rollback_payload['payload'])
        _assert_payload_slimmed(action.before_value)
        _assert_payload_slimmed(action.after_value)
        _assert_payload_slimmed(action.evidence)
        _assert_payload_slimmed(action.rollback_payload)
    finally:
        db.close()


def test_apply_corrections_merges_executor_rollback_payload_without_losing_machine_fields() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _executor(action):
            return {
                'before_value': {'hub': 95.0},
                'after_value': {'hub': 96.5},
                'evidence': {'handler': 'ok'},
                'rollback_payload': {'handler_ref': 'rollback:ok'},
            }

        service = HermesDataAuditService(db, apply_enabled=True)
        service._execute_mapping_alias_upsert = _executor

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action_with_machine_audit_fields('merge-handler-rollback')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['applied_count'] == 1
        assert action.status == 'applied'
        assert action.rollback_payload['mode'] == 'manual'
        assert action.rollback_payload['reason'] == 'restore previous hub value'
        assert action.rollback_payload['restore_before_value'] == {'hub': 95.0}
        assert action.rollback_payload['rollback_available'] is True
        assert action.rollback_payload['rollback_unavailable_reason'] == ''
        assert action.rollback_payload['handler_ref'] == 'rollback:ok'
    finally:
        db.close()


def test_apply_corrections_keeps_large_executor_result_before_after_machine_fields() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _executor(action):
            return {
                'before_value': _large_top_level_before_after_value(95.0, source='hub', reason='handler previous snapshot'),
                'after_value': _large_top_level_before_after_value(96.5, source='mes', reason='handler mes source of truth'),
                'evidence': {'handler': 'ok', 'source': 'mes'},
                'rollback_payload': {'mode': 'manual', 'restore_before_value': {'hub': 95.0}},
            }

        service = HermesDataAuditService(db, apply_enabled=True)
        service._execute_mapping_alias_upsert = _executor

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('large-handler-before-after')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['applied_count'] == 1
        assert action.status == 'applied'
        assert action.before_value['field'] == 'workshop_output'
        assert action.before_value['field_name'] == 'workshop_output'
        assert action.before_value['old_value'] == 94.0
        assert action.before_value['new_value'] == 95.0
        assert action.before_value['unit'] == 'ton'
        assert action.before_value['source'] == 'hub'
        assert action.before_value['reason'] == 'handler previous snapshot'
        assert action.before_value['note'] == 'keep small fields'
        assert action.before_value['extra_1'] == 'alpha'
        assert action.after_value['field'] == 'workshop_output'
        assert action.after_value['field_name'] == 'workshop_output'
        assert action.after_value['old_value'] == 95.5
        assert action.after_value['new_value'] == 96.5
        assert action.after_value['unit'] == 'ton'
        assert action.after_value['source'] == 'mes'
        assert action.after_value['reason'] == 'handler mes source of truth'
        assert action.after_value['note'] == 'keep small fields'
        assert action.after_value['extra_1'] == 'alpha'
        _assert_collection_summary(action.before_value['rows'])
        _assert_text_summary(action.before_value['raw_text'])
        _assert_collection_summary(action.after_value['rows'])
        _assert_text_summary(action.after_value['raw_text'])
        _assert_payload_slimmed(action.before_value)
        _assert_payload_slimmed(action.after_value)
    finally:
        db.close()


def test_apply_corrections_keeps_large_executor_result_audit_machine_fields() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _executor(action):
            return {
                'before_value': {'hub': 95.0},
                'after_value': {'hub': 96.5},
                'evidence': {
                    'source': 'mes',
                    'reason': 'handler verified mismatch',
                    'field': 'workshop_output',
                    'field_name': 'workshop_output',
                    'evidence_ref': 'handler:2026-06-18',
                    'handler': 'controlled-handler',
                    'values': {
                        'before': 95.0,
                        'after': 96.5,
                        'rows': [{'raw': _large_raw_text(), 'raw_text': _large_raw_text(), 'value': 96.5}],
                        'content': _large_raw_text(),
                    },
                    'extra_1': 'alpha',
                    'extra_2': 'beta',
                    'extra_3': 'gamma',
                },
                'rollback_payload': {
                    'mode': 'manual',
                    'reason': 'restore previous hub value',
                    'restore_before_value': {
                        'hub': 95.0,
                        'rows': [{'raw': _large_raw_text(), 'raw_text': _large_raw_text(), 'value': 95.0}],
                        'content': _large_raw_text(),
                        'note': 'restore snapshot',
                    },
                    'rollback_available': True,
                    'rollback_unavailable_reason': '',
                    'extra_1': 'alpha',
                    'extra_2': 'beta',
                    'extra_3': 'gamma',
                    'extra_4': 'delta',
                },
            }

        service = HermesDataAuditService(db, apply_enabled=True)
        service._execute_mapping_alias_upsert = _executor

        result = service.apply_corrections(
            audit_run_id=run.id,
            actions=[_supported_action('large-handler-metadata')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        assert result['applied_count'] == 1
        assert action.status == 'applied'
        assert action.evidence['source'] == 'mes'
        assert action.evidence['reason'] == 'handler verified mismatch'
        assert action.evidence['field'] == 'workshop_output'
        assert action.evidence['field_name'] == 'workshop_output'
        assert action.evidence['evidence_ref'] == 'handler:2026-06-18'
        assert action.evidence['handler'] == 'controlled-handler'
        assert action.evidence['extra_1'] == 'alpha'
        assert action.evidence['values']['before'] == 95.0
        assert action.evidence['values']['after'] == 96.5
        assert action.rollback_payload['mode'] == 'manual'
        assert action.rollback_payload['reason'] == 'restore previous hub value'
        assert action.rollback_payload['rollback_available'] is True
        assert action.rollback_payload['restore_before_value']['hub'] == 95.0
        assert action.rollback_payload['restore_before_value']['note'] == 'restore snapshot'
        _assert_collection_summary(action.evidence['values']['rows'])
        _assert_text_summary(action.evidence['values']['content'])
        _assert_collection_summary(action.rollback_payload['restore_before_value']['rows'])
        _assert_text_summary(action.rollback_payload['restore_before_value']['content'])
        _assert_payload_slimmed(action.evidence)
        _assert_payload_slimmed(action.rollback_payload)
    finally:
        db.close()


def test_apply_corrections_redacts_sensitive_text_inside_slim_summaries() -> None:
    db = _db_session()
    try:
        run = _make_run(db)
        service = HermesDataAuditService(db, apply_enabled=False)

        service.apply_corrections(
            audit_run_id=run.id,
            actions=[_action_with_large_audit_payload('redacted-summary')],
            dry_run=False,
            applied_by_id=3,
        )

        action = db.query(HermesCorrectionAction).one()
        rows_summary = action.before_value['rows']
        content_summary = action.after_value['content']
        raw_text_summary = action.evidence['values']['raw_text']
        rollback_content_summary = action.rollback_payload['content']
        for summary in (rows_summary, content_summary, raw_text_summary, rollback_content_summary):
            serialized = json.dumps(summary, ensure_ascii=False)
            assert 'secret-token' not in serialized
            assert 'top-secret' not in serialized
            assert '<redacted>' in serialized
    finally:
        db.close()


def test_apply_corrections_fails_when_executor_clears_evidence() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _executor(action):
            return {
                'before_value': {'hub': 95.0},
                'after_value': {'hub': 96.5},
                'evidence': {},
                'rollback_payload': {'mode': 'manual', 'restore_before_value': {'hub': 95.0}},
            }

        service = HermesDataAuditService(db, apply_enabled=True)
        service._execute_mapping_alias_upsert = _executor

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
        assert action.evidence['error'] in {'invalid_executor_audit_payload', 'incomplete_correction_audit_payload'}
        db.refresh(run)
        assert run.status == 'correction_failed'
    finally:
        db.close()


def test_apply_corrections_fails_when_executor_clears_rollback_payload() -> None:
    db = _db_session()
    try:
        run = _make_run(db)

        def _executor(action):
            return {
                'before_value': {'hub': 95.0},
                'after_value': {'hub': 96.5},
                'evidence': {'handler': 'ok', 'source': 'mes'},
                'rollback_payload': {},
            }

        service = HermesDataAuditService(db, apply_enabled=True)
        service._execute_mapping_alias_upsert = _executor

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
        assert action.evidence['error'] in {'invalid_executor_audit_payload', 'incomplete_correction_audit_payload'}
        db.refresh(run)
        assert run.status == 'correction_failed'
    finally:
        db.close()
