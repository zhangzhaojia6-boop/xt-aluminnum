from __future__ import annotations

from datetime import date, datetime, timezone
from importlib import import_module
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.rag import HermesLearningEvent, HermesShortTermMemory
from app.models.reports import (
    DailyFactBundleSnapshot,
    DailyReport,
    DailyReportHistoryRecord,
    OperationPeriodSnapshot,
)
from app.models.system import AuditLog, User
from app.services import audit_service
from app.services.hermes_day1_intent_service import HermesDay1Command


BUSINESS_DATE = date(2026, 6, 21)


def _service():
    return import_module('app.services.hermes_day1_orchestrator')


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _actor(db) -> User:
    user = User(
        username='root-owner',
        password_hash='hash',
        name='张兆嘉',
        role='admin',
        data_scope_type='factory',
    )
    db.add(user)
    db.flush()
    return user


def _command() -> HermesDay1Command:
    return HermesDay1Command(
        source_text='生成 2026-06-21 root_owner 完整版三段式日报',
        business_date=BUSINESS_DATE,
    )


def _sources() -> dict[str, Any]:
    return {
        'trace_id': 'trace-day1-001',
        'business_date': BUSINESS_DATE.isoformat(),
        'template_daily_report': {'status': 'ready', 'text': '模板日报正文'},
        'daily_fact_bundle': {
            'business_date': BUSINESS_DATE.isoformat(),
            'status': 'ready',
            'facts': {
                'total_output_daily': {'value': 366, 'source': 'root_owner_correction'},
                'total_cost_10k': {'value': 29.93, 'unit': '万元', 'source': 'energy_cost'},
            },
            'missing_fields': [],
            'missing': [],
            'conflicts': [],
            'correction_refs': [{'id': 1, 'field_name': 'total_output_daily'}],
            'dingtalk_refs': [{'id': 2, 'field_names': ['total_output_daily']}],
        },
        'mes_wms': {'source_status': {'mes': 'ok'}, 'records': {'summary': [{'field': 'total_output'}]}},
        'audit_run': {'status': 'completed', 'match_rate': 0.99, 'source_status': {'mes': 'ok', 'hub': 'ok'}},
        'dingtalk_evidence': [],
        'dingtalk_messages': [{'text': '现场补充：无异常'}],
        'historical_reports': [{'report_date': '2026-06-20', 'status': 'published'}],
        'rag': {'answer': '日报路线说明', 'citations': [{'source_ref': 'doc#1'}, {'source_ref': 'doc#2'}]},
        'output_skill_alignment': {
            'status': 'passed',
            'file_name': '2026-06-21_日报正文.txt',
            'field_match_rate': 98.5,
            'matched_fields': 20,
            'expected_fields': 20,
            'difference_count': 0,
            'differences': [],
            'char_match_rate': 99.1,
            'exact_match': False,
            'threshold': 95.0,
        },
    }


def _ready_product() -> dict[str, Any]:
    return {
        'status': 'ready',
        'text': '工厂大脑判断单\n正式日报正文\n各车间明细',
        'formal_text': '6月21日正式日报正文',
        'brain_judgment': {'summary': '可以发布', 'risks': []},
        'workshop_details': [{'title': '2050车间', 'lines': ['日产量：80吨。']}],
        'dingtalk_answer': '第一条回复\n\n第二条回复',
        'dingtalk_messages': ['第一条回复', '第二条回复'],
        'missing_fields': [],
        'conflicts': [],
    }


def _blocked_product() -> dict[str, Any]:
    return {
        'status': 'blocked',
        'text': '缺字段，未生成正式日报正文',
        'formal_text': '',
        'brain_judgment': {'summary': '缺字段，需要复核', 'risks': ['缺失 total_output']},
        'workshop_details': [],
        'dingtalk_answer': '缺字段，日报未定稿',
        'dingtalk_messages': ['缺字段，日报未定稿'],
        'missing_fields': ['total_output'],
        'conflicts': [{'field': 'total_output', 'message': '缺失'}],
    }


def _patch_pipeline(monkeypatch, service, *, sources: dict[str, Any] | None = None, product: dict[str, Any] | None = None):
    calls: dict[str, Any] = {}
    source_payload = sources or _sources()
    product_payload = product or _ready_product()

    def _collect(db_arg, **kwargs):
        calls['collect'] = {'db': db_arg, **kwargs}
        return source_payload

    def _build(**kwargs):
        calls['build'] = kwargs
        return product_payload

    monkeypatch.setattr(service, 'collect_day1_sources', _collect)
    monkeypatch.setattr(service, 'build_day1_three_part_report', _build)
    return calls


def _patch_audit(monkeypatch, service):
    calls: list[dict[str, Any]] = []

    def _log_action(db_arg, *args, **kwargs):
        calls.append(dict(kwargs))
        return audit_service.log_action(db_arg, *args, **kwargs)

    monkeypatch.setattr(service, 'log_action', _log_action)
    return calls


def test_ready_run_persists_report_agent_memory_learning_audit_and_returns_result(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    command = _command()
    calls = _patch_pipeline(monkeypatch, service)
    audit_calls = _patch_audit(monkeypatch, service)

    try:
        result = service.run_day1_super_brain(
            db,
            command=command,
            actor=actor,
            trace_id='trace-day1-001',
        )

        report = db.get(DailyReport, result.report_id)
        run = db.get(AgentRun, result.agent_run_id)
        memory = db.query(HermesShortTermMemory).one()
        event = db.query(HermesLearningEvent).one()
        audit_log = db.query(AuditLog).one()

        assert result.trace_id == 'trace-day1-001'
        assert result.status == 'ready'
        assert result.answer == '第一条回复\n\n第二条回复'
        assert result.reply_messages == ['第一条回复', '第二条回复']
        assert report.status == 'generated'
        assert run.status == 'answered'
        assert memory.conversation_key == f'user:{actor.id}'
        assert memory.memory_key == 'last_day1_super_brain_report'
        assert memory.memory_value['report_id'] == report.id
        assert event.status == 'candidate'
        assert event.question == command.source_text
        assert event.tools_called == service.DAY1_TOOLS_CALLED
        assert event.sources
        assert audit_log.action == 'hermes_day1_super_brain_report'
        assert audit_calls[0]['auto_commit'] is False
        assert calls['collect'] == {
            'db': db,
            'business_date': BUSINESS_DATE,
            'actor': actor,
            'trace_id': 'trace-day1-001',
        }
        assert calls['build']['business_date'] == BUSINESS_DATE
        assert calls['build']['sources']['template_daily_report'] == _sources()['template_daily_report']
        assert calls['build']['sources']['daily_fact_bundle']['status'] == 'ready'
    finally:
        db.close()


def test_ready_run_writes_final_fields_and_delivery_ready(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    _patch_pipeline(monkeypatch, service, product=_ready_product())
    _patch_audit(monkeypatch, service)

    try:
        result = service.run_day1_super_brain(
            db,
            command=_command(),
            actor=actor,
            trace_id='trace-day1-002',
        )

        report = db.get(DailyReport, result.report_id)
        hermes_payload = report.report_data['hermes_day1_super_brain']
        assert report.final_text_summary == '6月21日正式日报正文'
        assert report.final_confirmed_by == actor.id
        assert report.final_confirmed_at is not None
        assert report.is_final_version is True
        assert report.delivery_ready is True
        assert report.quality_gate_status == 'passed'
        assert report.quality_gate_summary == 'Hermes Day-1 三段式日报已生成'
        assert hermes_payload['status'] == 'ready'
        assert hermes_payload['three_part_text'] == '工厂大脑判断单\n正式日报正文\n各车间明细'
        assert hermes_payload['source_status'] == {'mes': 'ok', 'hub': 'ok'}
    finally:
        db.close()


def test_ready_run_archives_formal_snapshot_history_and_period_rollups(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    _patch_pipeline(monkeypatch, service, product=_ready_product())
    _patch_audit(monkeypatch, service)

    try:
        result = service.run_day1_super_brain(
            db,
            command=_command(),
            actor=actor,
            trace_id='trace-day1-archive',
        )

        snapshot = db.query(DailyFactBundleSnapshot).one()
        history = db.query(DailyReportHistoryRecord).one()
        period_snapshots = db.query(OperationPeriodSnapshot).order_by(OperationPeriodSnapshot.period_type.asc()).all()
        report = db.get(DailyReport, result.report_id)
        run = db.get(AgentRun, result.agent_run_id)

        assert snapshot.snapshot_reason == 'formal_daily_report'
        assert snapshot.business_date == BUSINESS_DATE
        assert snapshot.trace_id == 'trace-day1-archive'
        assert snapshot.facts['total_output_daily']['value'] == 366
        assert history.source_snapshot_id == snapshot.id
        assert history.source_run_id == snapshot.run_id
        assert history.business_date == BUSINESS_DATE
        assert history.report_text == '6月21日正式日报正文'
        assert history.report_payload['facts']['total_output_daily']['value'] == 366
        assert history.report_payload['facts']['total_cost_10k']['value'] == 29.93
        assert {item.period_type for item in period_snapshots} == {'month', 'year'}
        assert all(history.id in item.source_daily_report_ids for item in period_snapshots)
        assert all(snapshot.id in item.source_snapshot_ids for item in period_snapshots)
        assert all(item.cumulative_metrics['verified_cost_total']['value'] == 299300.0 for item in period_snapshots)
        assert report.report_data['hermes_day1_super_brain']['history_record_id'] == history.id
        assert report.report_data['hermes_day1_super_brain']['source_snapshot_id'] == snapshot.id
        assert run.result_payload['hermes_day1']['sources']['daily_fact_bundle']['formal_snapshot_id'] == snapshot.id
    finally:
        db.close()


def test_blocked_run_updates_report_without_final_or_delivery_and_marks_agent_blocked(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    _patch_pipeline(monkeypatch, service, product=_blocked_product())
    _patch_audit(monkeypatch, service)

    try:
        result = service.run_day1_super_brain(
            db,
            command=_command(),
            actor=actor,
            trace_id='trace-day1-blocked',
        )

        report = db.get(DailyReport, result.report_id)
        run = db.get(AgentRun, result.agent_run_id)
        assert result.status == 'blocked'
        assert report.status == 'draft'
        assert report.quality_gate_status == 'blocked'
        assert '缺字段' in report.quality_gate_summary
        assert report.final_text_summary is None
        assert report.final_confirmed_by is None
        assert report.final_confirmed_at is None
        assert report.is_final_version is False
        assert report.delivery_ready is False
        assert run.status == 'blocked'
        assert run.status_color == 'yellow'
        assert run.answer == '缺字段，日报未定稿'
        assert db.query(DailyReportHistoryRecord).count() == 0
        assert db.query(OperationPeriodSnapshot).count() == 0
    finally:
        db.close()


def test_blocked_rerun_clears_existing_review_publish_and_final_fields(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    existing = DailyReport(
        report_date=BUSINESS_DATE,
        report_type='production',
        text_summary='旧正式日报',
        status='published',
        reviewed_by=actor.id,
        reviewed_at=datetime(2026, 6, 21, 9, 0, tzinfo=timezone.utc),
        published_by=actor.id,
        published_at=datetime(2026, 6, 21, 10, 0, tzinfo=timezone.utc),
        final_text_summary='旧最终正文',
        final_confirmed_by=actor.id,
        final_confirmed_at=datetime(2026, 6, 21, 8, 30, tzinfo=timezone.utc),
        is_final_version=True,
        delivery_ready=True,
        quality_gate_status='passed',
    )
    db.add(existing)
    db.flush()
    _patch_pipeline(monkeypatch, service, product=_blocked_product())
    _patch_audit(monkeypatch, service)

    try:
        result = service.run_day1_super_brain(
            db,
            command=_command(),
            actor=actor,
            trace_id='trace-day1-blocked-rerun',
        )

        report = db.get(DailyReport, result.report_id)
        assert report.status == 'draft'
        assert report.quality_gate_status == 'blocked'
        assert report.reviewed_by is None
        assert report.reviewed_at is None
        assert report.published_by is None
        assert report.published_at is None
        assert report.final_text_summary is None
        assert report.final_confirmed_by is None
        assert report.final_confirmed_at is None
        assert report.is_final_version is False
        assert report.delivery_ready is False
    finally:
        db.close()


def test_existing_daily_report_is_updated_instead_of_duplicated(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    existing = DailyReport(
        report_date=BUSINESS_DATE,
        report_type='production',
        report_data={'existing_key': {'keep': True}},
        text_summary='旧日报',
        status='draft',
    )
    db.add(existing)
    db.flush()
    existing_id = existing.id
    _patch_pipeline(monkeypatch, service)
    _patch_audit(monkeypatch, service)

    try:
        result = service.run_day1_super_brain(
            db,
            command=_command(),
            actor=actor,
            trace_id='trace-day1-upsert',
        )

        assert result.report_id == existing_id
        assert db.query(DailyReport).filter(DailyReport.report_type == 'production').count() == 1
        report = db.get(DailyReport, existing_id)
        assert report.report_data['existing_key'] == {'keep': True}
        assert report.report_data['hermes_day1_super_brain']['status'] == 'ready'
        assert report.text_summary == '工厂大脑判断单\n正式日报正文\n各车间明细'
    finally:
        db.close()


def test_chat_inbox_rag_count_command_summary_and_reply_metadata_are_recorded(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    chat = ChatInboxMessage(
        channel='dingtalk_group',
        group_id='cid-root',
        sender_external_id='dt-root',
        text='生成 2026-06-21 日报',
        agent_code='xt-factory-controller',
        trace_id='trace-day1-chat',
        source_payload={'business_date': BUSINESS_DATE.isoformat()},
    )
    db.add(chat)
    db.flush()
    _patch_pipeline(monkeypatch, service)
    _patch_audit(monkeypatch, service)

    try:
        result = service.run_day1_super_brain(
            db,
            command=_command(),
            actor=actor,
            trace_id='trace-day1-chat',
            chat_inbox=chat,
        )

        run = db.get(AgentRun, result.agent_run_id)
        payload = run.result_payload['hermes_day1']
        command_summary = payload['command']
        reply = payload['dingtalk_reply']
        assert run.chat_inbox_id == chat.id
        assert run.rag_citation_count == 2
        assert command_summary['raw_text'] == '生成 2026-06-21 root_owner 完整版三段式日报'
        assert command_summary['business_date'] == BUSINESS_DATE.isoformat()
        assert command_summary['audience'] == 'root_owner'
        assert command_summary['output_style'] == 'three_part'
        assert reply['message_count'] == 2
        assert reply['first_message_chars'] == len('第一条回复')
        assert payload['sources']['trace_id'] == 'trace-day1-001'
        assert payload['sources']['template_daily_report']['status'] == 'ready'
        daily_fact_summary = payload['sources']['daily_fact_bundle']
        assert daily_fact_summary['status'] == 'ready'
        assert daily_fact_summary['missing_count'] == 0
        assert daily_fact_summary['conflict_count'] == 0
        assert daily_fact_summary['fact_count'] == 2
        assert daily_fact_summary['correction_ref_count'] == 1
        assert daily_fact_summary['dingtalk_ref_count'] == 1
        assert daily_fact_summary['formal_snapshot_id'] is not None
        assert daily_fact_summary['formal_history_record_id'] is not None
        assert payload['sources']['mes_wms']['record_groups'] == 1
        assert payload['sources']['audit_run']['match_rate'] == 0.99
        assert payload['sources']['rag']['citation_count'] == 2
        assert payload['sources']['output_skill_alignment']['field_match_rate'] == 98.5
        assert payload['output_skill_alignment']['status'] == 'passed'
        assert payload['harness']['summary']['passed'] is True
        assert payload['harness']['summary']['total_count'] >= 6
        assert payload['report_id'] == result.report_id
    finally:
        db.close()


def test_agent_run_source_summary_excludes_raw_dingtalk_text(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    long_evidence_text = '现场原始图片识别文字' * 80
    long_chat_text = '钉钉群原始长消息' * 80
    sources = _sources()
    sources['dingtalk_evidence'] = [
        {
            'id': 11,
            'file_uri': 'dingtalk://media/abc',
            'recognized_text': long_evidence_text,
            'payload': {'hash': 'evidence-hash-1', 'business_date': BUSINESS_DATE.isoformat()},
        }
    ]
    sources['dingtalk_messages'] = [
        {
            'id': 22,
            'trace_id': 'trace-day1-raw',
            'text': long_chat_text,
            'source_payload': {'hash': 'message-hash-1'},
        }
    ]
    sources['output_skill_alignment'] = {
        'status': 'review_needed',
        'file_name': '2026-06-21_日报正文.txt',
        'field_match_rate': 82.0,
        'matched_fields': 18,
        'expected_fields': 22,
        'difference_count': 1,
        'differences': [{'field': 'total_output_daily', 'actual': 366, 'expected': 360}],
        'char_match_rate': 90.1,
        'exact_match': False,
        'threshold': 95.0,
    }
    _patch_pipeline(monkeypatch, service, sources=sources)
    _patch_audit(monkeypatch, service)

    try:
        result = service.run_day1_super_brain(
            db,
            command=_command(),
            actor=actor,
            trace_id='trace-day1-summary',
        )

        run = db.get(AgentRun, result.agent_run_id)
        payload_text = str(run.result_payload)
        summary = run.result_payload['hermes_day1']['sources']
        hermes_payload = run.result_payload['hermes_day1']
        assert long_evidence_text not in payload_text
        assert long_chat_text not in payload_text
        assert summary['trace_id'] == 'trace-day1-001'
        assert summary['business_date'] == BUSINESS_DATE.isoformat()
        daily_fact_summary = summary['daily_fact_bundle']
        assert daily_fact_summary['status'] == 'ready'
        assert daily_fact_summary['missing_count'] == 0
        assert daily_fact_summary['conflict_count'] == 0
        assert daily_fact_summary['fact_count'] == 2
        assert daily_fact_summary['correction_ref_count'] == 1
        assert daily_fact_summary['dingtalk_ref_count'] == 1
        assert daily_fact_summary['formal_snapshot_id'] is not None
        assert daily_fact_summary['formal_history_record_id'] is not None
        assert summary['dingtalk_evidence']['count'] == 1
        assert summary['dingtalk_evidence']['items'] == [{'id': 11, 'file_uri': 'dingtalk://media/abc', 'hash': 'evidence-hash-1'}]
        assert summary['dingtalk_messages']['count'] == 1
        assert summary['dingtalk_messages']['items'] == [{'id': 22, 'hash': 'message-hash-1'}]
        assert summary['rag']['citation_count'] == 2
        assert summary['output_skill_alignment'] == {
            'status': 'review_needed',
            'file_name': '2026-06-21_日报正文.txt',
            'field_match_rate': 82.0,
            'matched_fields': 18,
            'expected_fields': 22,
            'difference_count': 1,
            'char_match_rate': 90.1,
            'exact_match': False,
            'threshold': 95.0,
        }
        assert hermes_payload['output_skill_alignment']['differences'] == [
            {'field': 'total_output_daily', 'actual': 366, 'expected': 360}
        ]
        assert '现场补充：无异常' not in payload_text
        assert '日报路线说明' not in payload_text
    finally:
        db.close()


def test_low_output_skill_match_rate_blocks_final_release_even_with_formal_text(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    low_match_sources = _sources()
    low_match_sources['output_skill_alignment'] = {
        'status': 'review_needed',
        'file_name': '2026-06-21_日报正文.txt',
        'field_match_rate': 94.9,
        'matched_fields': 19,
        'expected_fields': 20,
        'difference_count': 2,
        'differences': [
            {'field': 'total_output_daily', 'actual': 366, 'expected': 360},
            {'field': 'cost_per_ton', 'actual': 1044, 'expected': 999},
        ],
        'char_match_rate': 95.2,
        'exact_match': False,
        'threshold': 95.0,
    }
    _patch_audit(monkeypatch, service)

    def _collect(db_arg, **kwargs):
        return low_match_sources

    monkeypatch.setattr(service, 'collect_day1_sources', _collect)

    try:
        result = service.run_day1_super_brain(
            db,
            command=_command(),
            actor=actor,
            trace_id='trace-day1-low-match',
        )

        report = db.get(DailyReport, result.report_id)
        run = db.get(AgentRun, result.agent_run_id)
        assert result.status == 'blocked'
        assert report.quality_gate_status == 'blocked'
        assert report.final_text_summary is None
        assert report.is_final_version is False
        assert report.delivery_ready is False
        assert run.status == 'blocked'
        assert run.status_color == 'yellow'
        assert run.result_payload['hermes_day1']['output_skill_alignment']['field_match_rate'] == 94.9
    finally:
        db.close()


def test_missing_output_skill_alignment_blocks_final_release_even_if_audit_match_rate_is_perfect(monkeypatch) -> None:
    service = _service()
    db = _db_session()
    actor = _actor(db)
    missing_alignment_sources = _sources()
    missing_alignment_sources['audit_run'] = {
        'status': 'completed',
        'match_rate': 1.0,
        'source_status': {'mes': 'ok', 'hub': 'ok', 'output_skill': 'missing'},
    }
    missing_alignment_sources['output_skill_alignment'] = {
        'status': 'missing',
        'file_name': None,
        'field_match_rate': None,
        'matched_fields': None,
        'expected_fields': None,
        'difference_count': None,
        'differences': [],
        'char_match_rate': None,
        'exact_match': False,
        'threshold': 95.0,
    }
    _patch_audit(monkeypatch, service)

    def _collect(db_arg, **kwargs):
        return missing_alignment_sources

    monkeypatch.setattr(service, 'collect_day1_sources', _collect)

    try:
        result = service.run_day1_super_brain(
            db,
            command=_command(),
            actor=actor,
            trace_id='trace-day1-missing-alignment',
        )

        report = db.get(DailyReport, result.report_id)
        run = db.get(AgentRun, result.agent_run_id)
        assert result.status == 'blocked'
        assert report.quality_gate_status == 'blocked'
        assert report.final_text_summary is None
        assert report.delivery_ready is False
        assert run.status == 'blocked'
        assert '状态：已对齐' not in run.answer
    finally:
        db.close()
