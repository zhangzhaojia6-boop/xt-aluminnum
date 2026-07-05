from __future__ import annotations

from datetime import date, datetime, timezone
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import ChatInboxMessage, MultimodalEvidence
from app.models.hermes_data_audit import HermesDataAuditRun
from app.models.reports import DailyReport


def _source_service():
    return import_module('app.services.hermes_day1_source_service')


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _daily_fact_bundle_payload(
    business_date: date,
    *,
    output_skill_alignment: dict | None = None,
) -> dict:
    return {
        'business_date': business_date.isoformat(),
        'status': 'ready',
        'facts': {'total_output_daily': {'value': 366, 'source': 'root_owner_correction'}},
        'missing_fields': [],
        'missing': [],
        'conflicts': [],
        'correction_refs': [],
        'dingtalk_refs': [],
        'output_skill_alignment': output_skill_alignment
        if output_skill_alignment is not None
        else {'status': 'passed', 'field_match_rate': 100.0},
    }


def test_collect_day1_sources_returns_expected_shape_and_calls_existing_services(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)
    actor = SimpleNamespace(id=23)
    calls: dict[str, Any] = {}

    template_payload = {
        'status': 'ready',
        'facts': {'values': {'total_output': 100.0}},
    }
    mes_payload = {
        'business_date': '2026-06-21',
        'records': {'stock_records': []},
        'source_status': {'mes': 'empty', 'sources': {}},
        'source_errors': {},
    }
    daily_fact_payload = _daily_fact_bundle_payload(business_date)

    class _MesReaderFake:
        def __init__(self, adapter) -> None:
            calls['mes_adapter'] = adapter

        def read_sources(self, **kwargs):
            calls['mes_read_sources'] = kwargs
            return mes_payload

    class _AuditServiceFake:
        def __init__(self, db_arg, **kwargs) -> None:
            calls['audit_init'] = {'db': db_arg, **kwargs}

        def create_run(self, **kwargs):
            calls['audit_create_run'] = kwargs
            return SimpleNamespace(
                id=7,
                status='completed',
                match_rate=0.5,
                source_status={'mes': 'empty', 'hub': 'ok', 'output_skill': 'missing'},
                source_errors={},
                diffs={'total_output': {'status': 'matched'}},
                suggested_actions=[],
                output_skill_snapshot={'status': 'missing', 'raw_payload_truncated': True},
            )

    def _build_template(db_arg, *, target_date):
        calls['template'] = {'db': db_arg, 'target_date': target_date}
        return template_payload

    def _query_knowledge(db_arg, **kwargs):
        calls['rag'] = {'db': db_arg, **kwargs}
        return {'answer': 'ok', 'citations': [{'source_ref': 'doc#1'}], 'items': [{'debug': 'drop'}]}

    def _build_daily_fact_bundle(db_arg, **kwargs):
        calls['daily_fact_bundle'] = {'db': db_arg, **kwargs}
        return daily_fact_payload

    monkeypatch.setattr(service.template_daily_report, 'build_template_daily_report_payload', _build_template)
    monkeypatch.setattr(service, 'build_daily_fact_bundle', _build_daily_fact_bundle)
    monkeypatch.setattr(service, 'get_mes_adapter', lambda: 'adapter')
    monkeypatch.setattr(service, 'HermesMesReadService', _MesReaderFake)
    monkeypatch.setattr(service, 'HermesDataAuditService', _AuditServiceFake)
    monkeypatch.setattr(service, 'query_knowledge', _query_knowledge)
    monkeypatch.setattr(
        service,
        'build_output_skill_alignment',
        lambda *args, **kwargs: {'status': 'fallback_should_not_run'},
    )

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=actor,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    assert set(payload) == {
        'trace_id',
        'business_date',
        'template_daily_report',
        'daily_fact_bundle',
        'source_map',
        'mes_wms',
        'audit_run',
        'dingtalk_evidence',
        'dingtalk_messages',
        'historical_reports',
        'rag',
        'output_skill_alignment',
    }
    assert payload['trace_id'] == 'trace-day1-001'
    assert payload['business_date'] == '2026-06-21'
    assert payload['template_daily_report'] == template_payload
    assert payload['daily_fact_bundle'] == daily_fact_payload
    assert payload['source_map'] == {
        'status': 'ok',
        'source': 'fact_source_map',
        'metric_keys': ['total_output_daily'],
        'facts': [
            {
                'metric_key': 'total_output_daily',
                'display_name': '车间总产量日合计',
                'summary': '车间总产量日合计：优先级 dingtalk_group_content > MES/WMS readonly > data_hub_projection > DailyFactBundle。涉及服务：DailyFactBundle、Hermes、template_daily_report、hermes_langchain_tools。风险：包装量、入库量、车间最终日报产量不是同一个数',
                'delete_protection': 'protect',
                'api_routes': ['/api/v1/reports/template-daily/preview', '/api/v1/dashboard/daily-production'],
                'frontend_pages': ['/manage/today', '/manage/production'],
            }
        ],
        'source_explanations': [
            '车间总产量日合计：优先级 dingtalk_group_content > MES/WMS readonly > data_hub_projection > DailyFactBundle。涉及服务：DailyFactBundle、Hermes、template_daily_report、hermes_langchain_tools。风险：包装量、入库量、车间最终日报产量不是同一个数'
        ],
    }
    assert payload['mes_wms'] == mes_payload
    assert payload['audit_run']['id'] == 7
    assert payload['rag'] == {'answer': 'ok', 'citations': [{'source_ref': 'doc#1'}]}
    assert payload['output_skill_alignment'] == {'status': 'passed', 'field_match_rate': 100.0}

    assert service.DAY1_MES_QUERY_KEYS == (
        'workshop_process_records',
        'stock_records',
        'finished_inbound_records',
        'delivery_records',
        'material_records',
        'yield_records',
        'wip_totals',
    )
    assert calls['template'] == {'db': db, 'target_date': business_date}
    assert calls['daily_fact_bundle'] == {
        'db': db,
        'business_date': business_date,
        'requested_by': actor,
        'trace_id': 'trace-day1-001',
        'persist_run': True,
        'snapshot_reason': None,
    }
    assert calls['mes_adapter'] == 'adapter'
    assert calls['mes_read_sources'] == {
        'business_date': business_date,
        'query_keys': service.DAY1_MES_QUERY_KEYS,
    }
    assert calls['audit_init']['db'] is db
    audit_mes_reader = calls['audit_init']['mes_read_service']
    assert audit_mes_reader.read_sources(
        business_date=business_date,
        query_keys=service.DAY1_MES_QUERY_KEYS,
    ) == mes_payload
    assert calls['audit_create_run'] == {
        'business_date': business_date,
        'fields': service.DEFAULT_AUDIT_FIELDS,
        'mes_query_keys': service.DAY1_MES_QUERY_KEYS,
        'created_by_id': 23,
    }
    assert calls['rag'] == {
        'db': db,
        'query': '2026-06-21 日报 模板 WMS_InStock MES 路线 数据来源',
        'limit': 5,
        'user': actor,
    }


def test_collect_day1_sources_includes_daily_fact_bundle(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)
    _patch_collect_dependencies(monkeypatch, service)
    monkeypatch.setattr(
        service,
        'build_output_skill_alignment',
        lambda *args, **kwargs: {'status': 'fallback_missing'},
    )

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    assert payload['daily_fact_bundle'] == _daily_fact_bundle_payload(business_date)
    assert payload['output_skill_alignment'] == {'status': 'passed', 'field_match_rate': 100.0}


def test_collect_day1_sources_includes_source_map_explanations_for_mapped_metrics(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)
    _patch_collect_dependencies(monkeypatch, service)

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    source_map = payload['source_map']
    assert source_map['status'] == 'ok'
    assert source_map['source'] == 'fact_source_map'
    assert source_map['metric_keys'] == ['total_output_daily']
    assert source_map['facts'][0]['metric_key'] == 'total_output_daily'
    assert source_map['facts'][0]['delete_protection'] == 'protect'
    assert source_map['facts'][0]['frontend_pages'] == ['/manage/today', '/manage/production']
    assert source_map['source_explanations']
    assert '车间总产量日合计' in source_map['source_explanations'][0]


def test_collect_day1_sources_reads_mes_once_when_audit_reads_sources(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)
    mes_calls: list[dict] = []

    class _MesReaderFake:
        def __init__(self, adapter) -> None:
            self.adapter = adapter

        def read_sources(self, **kwargs):
            mes_calls.append(kwargs)
            return {
                'business_date': kwargs['business_date'].isoformat(),
                'records': {'summary': [{'field': 'total_output', 'value': 100.0}]},
                'source_status': {'mes': 'ok', 'sources': {'summary': {'status': 'ok', 'count': 1}}},
                'source_errors': {},
            }

    class _AuditServiceFake:
        def __init__(self, db_arg, **kwargs) -> None:
            self.mes_read_service = kwargs['mes_read_service']

        def create_run(self, **kwargs):
            audit_mes_payload = self.mes_read_service.read_sources(
                business_date=kwargs['business_date'],
                query_keys=kwargs['mes_query_keys'],
            )
            assert audit_mes_payload['records']['summary'][0]['value'] == 100.0
            return SimpleNamespace(
                id=7,
                status='completed',
                match_rate=1,
                source_status={'mes': 'ok'},
                source_errors={},
                diffs={},
                suggested_actions=[],
                output_skill_snapshot={'status': 'missing'},
            )

    monkeypatch.setattr(
        service.template_daily_report,
        'build_template_daily_report_payload',
        lambda db, *, target_date: {'status': 'ready', 'facts': {'values': {'total_output': 100.0}}},
    )
    monkeypatch.setattr(service, 'get_mes_adapter', lambda: 'adapter')
    monkeypatch.setattr(service, 'HermesMesReadService', _MesReaderFake)
    monkeypatch.setattr(service, 'HermesDataAuditService', _AuditServiceFake)
    monkeypatch.setattr(service, 'query_knowledge', lambda *args, **kwargs: {'answer': 'ok', 'citations': []})

    try:
        service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    assert mes_calls == [
        {
            'business_date': business_date,
            'query_keys': service.DAY1_MES_QUERY_KEYS,
        }
    ]


def test_preloaded_mes_read_service_rejects_mismatched_request() -> None:
    service = _source_service()
    reader = service._PreloadedMesReadService(
        {'records': {'stock_records': []}},
        business_date=date(2026, 6, 21),
        query_keys=service.DAY1_MES_QUERY_KEYS,
    )

    try:
        reader.read_sources(
            business_date=date(2026, 6, 20),
            query_keys=service.DAY1_MES_QUERY_KEYS,
        )
        wrong_date_error = None
    except ValueError as exc:
        wrong_date_error = str(exc)

    try:
        reader.read_sources(
            business_date=date(2026, 6, 21),
            query_keys=('stock_records',),
        )
        wrong_keys_error = None
    except ValueError as exc:
        wrong_keys_error = str(exc)

    assert wrong_date_error == 'preloaded_mes_payload_mismatch'
    assert wrong_keys_error == 'preloaded_mes_payload_mismatch'


def test_collect_day1_sources_filters_dingtalk_evidence_for_target_daily_sample(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)
    _patch_collect_dependencies(monkeypatch, service)
    db.add_all(
        [
            MultimodalEvidence(
                evidence_type='text',
                recognized_text='目标日报产量 32 吨',
                file_uri='dingtalk://media/target',
                payload={'business_date': '2026-06-21', 'include_in_daily_sample': True},
            ),
            MultimodalEvidence(
                evidence_type='text',
                recognized_text='同日噪声',
                payload={'business_date': '2026-06-21', 'include_in_daily_sample': False},
            ),
            MultimodalEvidence(
                evidence_type='text',
                recognized_text='其他日期',
                payload={'business_date': '2026-06-20', 'include_in_daily_sample': True},
            ),
        ]
    )
    db.commit()

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    assert payload['dingtalk_evidence'] == [
        {
            'id': 1,
            'evidence_type': 'text',
            'recognized_text': '目标日报产量 32 吨',
            'file_uri': 'dingtalk://media/target',
            'payload': {'business_date': '2026-06-21', 'include_in_daily_sample': True},
        }
    ]


def test_collect_day1_sources_returns_latest_seven_production_reports(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)
    _patch_collect_dependencies(monkeypatch, service)
    for day in range(1, 11):
        db.add(
            DailyReport(
                report_date=date(2026, 6, day),
                report_type='production',
                status='published',
                quality_gate_status='passed',
                final_text_summary='日报正文' if day % 2 else None,
                delivery_ready=day % 2 == 1,
            )
        )
    db.add(
        DailyReport(
            report_date=date(2026, 6, 21),
            report_type='energy',
            status='published',
        )
    )
    db.commit()

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    reports = payload['historical_reports']
    assert [item['report_date'] for item in reports] == [
        '2026-06-10',
        '2026-06-09',
        '2026-06-08',
        '2026-06-07',
        '2026-06-06',
        '2026-06-05',
        '2026-06-04',
    ]
    assert len(reports) == 7
    assert reports[0]['status'] == 'published'
    assert reports[0]['quality_gate_status'] == 'passed'
    assert reports[0]['has_final_text'] is False
    assert reports[1]['has_final_text'] is True
    assert reports[1]['delivery_ready'] is True


def test_collect_day1_sources_returns_failed_audit_payload_with_redacted_error(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()

    class _AuditServiceFake:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def create_run(self, **kwargs):
            raise RuntimeError('audit failed password=plain-pass token=plain-token')

    _patch_collect_dependencies(monkeypatch, service)
    monkeypatch.setattr(service, 'HermesDataAuditService', _AuditServiceFake)

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=date(2026, 6, 21),
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    audit_payload = payload['audit_run']
    assert audit_payload['status'] == 'failed'
    assert audit_payload['source_status'] == {'audit': 'failed'}
    assert 'plain-pass' not in str(audit_payload)
    assert 'plain-token' not in str(audit_payload)
    assert audit_payload['source_errors']['audit'] == 'audit failed password=<redacted> token=<redacted>'


def test_collect_day1_sources_preserves_failed_audit_run_for_no_comparable_data(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)

    class _AuditServiceFake:
        def __init__(self, db_arg, **kwargs) -> None:
            self.db = db_arg

        def create_run(self, **kwargs):
            run = HermesDataAuditRun(
                run_key='run-no-comparable',
                business_date=business_date,
                status='failed',
                source_status={'mes': 'empty', 'hub': 'ok', 'output_skill': 'missing'},
                source_errors={'output_skill': 'output_skill_source_missing'},
                mes_snapshot={},
                hub_snapshot={},
                output_skill_snapshot={'status': 'missing', 'raw_payload_truncated': True},
                diffs={'total_output': {'status': 'mes_missing'}},
                suggested_actions=[],
            )
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
            raise service.NoComparableDataError(f'No comparable data for audit run {run.id}')

    _patch_collect_dependencies(monkeypatch, service)
    monkeypatch.setattr(service, 'HermesDataAuditService', _AuditServiceFake)

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    audit_payload = payload['audit_run']
    assert audit_payload['id'] == 1
    assert audit_payload['status'] == 'failed'
    assert audit_payload['source_status'] == {'mes': 'empty', 'hub': 'ok', 'output_skill': 'missing'}
    assert audit_payload['diffs'] == {'total_output': {'status': 'mes_missing'}}
    assert audit_payload['output_skill_snapshot'] == {
        'status': 'missing',
        'raw_payload_truncated': True,
    }


def test_collect_day1_sources_does_not_guess_failed_audit_run_without_error_run_id(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)
    existing_run = HermesDataAuditRun(
        run_key='unrelated-run',
        business_date=business_date,
        status='failed',
        source_status={'mes': 'failed'},
        source_errors={'mes': 'unrelated'},
        mes_snapshot={},
        hub_snapshot={},
        output_skill_snapshot={'status': 'missing'},
        diffs={'unrelated': {'status': 'failed'}},
        suggested_actions=[],
    )
    db.add(existing_run)
    db.commit()

    class _AuditServiceFake:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def create_run(self, **kwargs):
            raise service.NoComparableDataError('No comparable data')

    _patch_collect_dependencies(monkeypatch, service)
    monkeypatch.setattr(service, 'HermesDataAuditService', _AuditServiceFake)

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    audit_payload = payload['audit_run']
    assert audit_payload['id'] is None
    assert audit_payload['status'] == 'failed'
    assert audit_payload['source_status'] == {'audit': 'failed'}
    assert audit_payload['diffs'] == {}


def test_collect_day1_sources_returns_failed_rag_payload_with_redacted_error(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    _patch_collect_dependencies(monkeypatch, service)

    def _query_knowledge(*args, **kwargs):
        raise RuntimeError('rag failed password=plain-pass token=plain-token')

    monkeypatch.setattr(service, 'query_knowledge', _query_knowledge)

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=date(2026, 6, 21),
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    assert payload['rag'] == {
        'answer': None,
        'citations': [],
        'status': 'failed',
        'source_errors': {'rag': 'rag failed password=<redacted> token=<redacted>'},
    }
    assert 'plain-pass' not in str(payload)
    assert 'plain-token' not in str(payload)


def test_collect_day1_sources_lists_relevant_chat_messages_with_cap(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)
    _patch_collect_dependencies(monkeypatch, service)
    for index in range(25):
        db.add(
            ChatInboxMessage(
                channel='dingtalk',
                group_id='group-001',
                sender_external_id=f'user-{index}',
                text=f'目标日期消息 {index}',
                trace_id=f'trace-other-{index}',
                source_payload={'business_date': '2026-06-21'},
                created_at=datetime(2026, 6, 21, 8, index, tzinfo=timezone.utc),
            )
        )
    db.add(
        ChatInboxMessage(
            channel='dingtalk',
            group_id='group-002',
            sender_external_id='noise',
            text='其他日期消息',
            trace_id='trace-noise',
            source_payload={'business_date': '2026-06-20'},
            created_at=datetime(2026, 6, 21, 9, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    messages = payload['dingtalk_messages']
    assert len(messages) == 20
    assert all(item['text'].startswith('目标日期消息') for item in messages)
    assert set(messages[0]) == {
        'id',
        'channel',
        'group_id',
        'sender_external_id',
        'text',
        'trace_id',
        'created_at',
    }


def test_collect_day1_sources_accepts_realistic_dingtalk_channels_only(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 21)
    _patch_collect_dependencies(monkeypatch, service)
    db.add_all(
        [
            ChatInboxMessage(
                channel='dingtalk_private',
                group_id=None,
                sender_external_id='private-user',
                text='私聊日报信息',
                trace_id='trace-private',
                source_payload={'business_date': '2026-06-21'},
                created_at=datetime(2026, 6, 21, 8, 1, tzinfo=timezone.utc),
            ),
            ChatInboxMessage(
                channel='dingtalk_group',
                group_id='group-001',
                sender_external_id='group-user',
                text='群日报信息',
                trace_id='trace-group',
                source_payload={'business_date': '2026-06-21'},
                created_at=datetime(2026, 6, 21, 8, 2, tzinfo=timezone.utc),
            ),
            ChatInboxMessage(
                channel='private',
                group_id='private-group',
                sender_external_id='private-noise',
                text='非钉钉通道不能返回',
                trace_id='trace-private-noise',
                source_payload={'business_date': '2026-06-21'},
                created_at=datetime(2026, 6, 21, 8, 3, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-missing',
        )
    finally:
        db.close()

    messages = payload['dingtalk_messages']
    assert {item['channel'] for item in messages} == {'dingtalk_private', 'dingtalk_group'}
    assert {item['text'] for item in messages} == {'私聊日报信息', '群日报信息'}


def test_collect_day1_sources_does_not_return_unmatched_recent_chat_messages(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    _patch_collect_dependencies(monkeypatch, service)
    db.add_all(
        [
            ChatInboxMessage(
                channel='private',
                group_id='private-group',
                sender_external_id='private-user',
                text='私聊消息不能泄漏',
                trace_id='trace-private',
                source_payload={'business_date': '2026-06-20'},
            ),
            ChatInboxMessage(
                channel='dingtalk',
                group_id='other-group',
                sender_external_id='other-user',
                text='无关钉钉消息也不能泄漏',
                trace_id='trace-other',
                source_payload={'business_date': '2026-06-20'},
            ),
        ]
    )
    db.commit()

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=date(2026, 6, 21),
            actor=None,
            trace_id='trace-missing',
        )
    finally:
        db.close()

    assert payload['dingtalk_messages'] == []


def test_collect_day1_sources_excludes_raw_output_skill_text_and_redacts_snapshot(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()

    class _AuditServiceFake:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def create_run(self, **kwargs):
            return SimpleNamespace(
                id=8,
                status='completed',
                match_rate=1,
                source_status={'output_skill': 'parsed'},
                source_errors={},
                diffs={},
                suggested_actions=[],
                output_skill_snapshot={
                    'status': 'parsed',
                    'files': ['D:/output/2026-06-21.txt'],
                    'raw_text': 'secret raw output password=plain-pass token=plain-token',
                    'parsed': {'total_output': 100},
                    'issues': [{'message': 'token=plain-token'}],
                    'payload_hash': 'hash-1',
                    'raw_payload_truncated': True,
                },
            )

    _patch_collect_dependencies(monkeypatch, service)
    monkeypatch.setattr(service, 'HermesDataAuditService', _AuditServiceFake)

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=date(2026, 6, 21),
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    snapshot = payload['audit_run']['output_skill_snapshot']
    assert 'raw_text' not in snapshot
    assert snapshot['status'] == 'parsed'
    assert snapshot['parsed'] == {'total_output': 100}
    assert 'plain-pass' not in str(payload['audit_run'])
    assert 'plain-token' not in str(payload['audit_run'])


def test_collect_day1_sources_returns_output_skill_alignment_when_reference_root_configured(monkeypatch) -> None:
    service = _source_service()
    db = _db_session()
    business_date = date(2026, 6, 16)
    fixture_dir = Path(__file__).resolve().parent / 'fixtures' / 'output_skill_daily_reports'
    fixture_text = (fixture_dir / '2026-6-16_日报正文.txt').read_text(encoding='utf-8')

    _patch_collect_dependencies(monkeypatch, service)
    monkeypatch.setenv('OUTPUT_SKILL_REFERENCE_ROOT', str(fixture_dir))
    monkeypatch.delenv('OUTPUT_SKILL_ROOT', raising=False)
    monkeypatch.setattr(
        service,
        'build_daily_fact_bundle',
        lambda db, *, business_date, requested_by=None, trace_id=None, persist_run=False, snapshot_reason=None: (
            _daily_fact_bundle_payload(business_date, output_skill_alignment={})
        ),
    )
    monkeypatch.setattr(
        service.template_daily_report,
        'build_template_daily_report_payload',
        lambda db, *, target_date: {'status': 'ready', 'text': fixture_text, 'facts': {'values': {}}},
    )

    try:
        payload = service.collect_day1_sources(
            db,
            business_date=business_date,
            actor=None,
            trace_id='trace-day1-001',
        )
    finally:
        db.close()

    assert payload['output_skill_alignment'] == {
        'status': 'passed',
        'file_name': '2026-6-16_日报正文.txt',
        'field_match_rate': 100.0,
        'matched_fields': 130,
        'expected_fields': 130,
        'numeric_tolerance': 20.0,
        'tolerance_matched_fields': 0,
        'difference_count': 0,
        'differences': [],
        'char_match_rate': 100.0,
        'exact_match': True,
        'threshold': 95.0,
    }


def _patch_collect_dependencies(monkeypatch, service) -> None:
    class _MesReaderFake:
        def __init__(self, adapter) -> None:
            self.adapter = adapter

        def read_sources(self, **kwargs):
            return {
                'business_date': kwargs['business_date'].isoformat(),
                'records': {},
                'source_status': {'mes': 'empty', 'sources': {}},
                'source_errors': {},
            }

    class _AuditServiceFake:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def create_run(self, **kwargs):
            return SimpleNamespace(
                id=7,
                status='completed',
                match_rate=None,
                source_status={'mes': 'empty', 'hub': 'empty', 'output_skill': 'missing'},
                source_errors={},
                diffs={},
                suggested_actions=[],
                output_skill_snapshot={'status': 'missing', 'raw_payload_truncated': True},
            )

    monkeypatch.setattr(
        service.template_daily_report,
        'build_template_daily_report_payload',
        lambda db, *, target_date: {'status': 'ready', 'facts': {'values': {}}},
    )
    monkeypatch.setattr(
        service,
        'build_daily_fact_bundle',
        lambda db, *, business_date, requested_by=None, trace_id=None, persist_run=False, snapshot_reason=None: (
            _daily_fact_bundle_payload(business_date)
        ),
    )
    monkeypatch.setattr(service, 'get_mes_adapter', lambda: 'adapter')
    monkeypatch.setattr(service, 'HermesMesReadService', _MesReaderFake)
    monkeypatch.setattr(service, 'HermesDataAuditService', _AuditServiceFake)
    monkeypatch.setattr(service, 'query_knowledge', lambda *args, **kwargs: {'answer': 'ok', 'citations': []})
