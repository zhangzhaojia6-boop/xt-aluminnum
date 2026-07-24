from __future__ import annotations

from datetime import datetime, timezone
import json
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_engine, get_sessionmaker
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.master import Workshop
from app.models.mes import MesSyncRunLog
from app.models.rag import (
    HermesApprovedLesson,
    HermesLearningEvent,
    HermesShortTermMemory,
    RagChunk,
    RagDocument,
    RagEmbedding,
    RagQueryLog,
    RagSourceIngestion,
)
from app.models.reports import DailyReport
from app.models.system import User
from app.services.rag_service import create_document_from_bytes
from scripts import agent_cli


TABLES = [
    User.__table__,
    Workshop.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    RagEmbedding.__table__,
    RagSourceIngestion.__table__,
    HermesLearningEvent.__table__,
    HermesShortTermMemory.__table__,
    HermesApprovedLesson.__table__,
    DailyReport.__table__,
    ChatInboxMessage.__table__,
    AgentRun.__table__,
    MesSyncRunLog.__table__,
]


def _install_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'agent-cli.db'}"
    monkeypatch.setattr('app.config.settings.DATABASE_URL', db_url, raising=False)
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    return Session(engine)


def _run_cli(args, capsys):
    code = agent_cli.main(args)
    output = capsys.readouterr().out.strip()
    return code, json.loads(output)


def test_agent_cli_rag_query_outputs_json(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        db.add(User(id=1, username='zzj', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()
        create_document_from_bytes(
            db,
            filename='日报口径.md',
            content='日报 7:30 输出前一个业务日，包装产量来自 WMS_InStock。'.encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        db.commit()

        code, payload = _run_cli([
            'rag-query',
            '--query',
            '日报 7:30 包装产量',
            '--dingtalk-user-id',
            'dt-owner',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'rag-query'
        assert 'WMS_InStock' in payload['reply']
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_agent_cli_rejects_free_sql_as_json(capsys) -> None:
    code, payload = _run_cli(['select'], capsys)
    assert code == 1
    assert payload['ok'] is False
    assert payload['error'] == 'free_sql_not_allowed'


def test_agent_cli_allowed_user_cannot_run_owner_command(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_ALLOWED_DINGTALK_USER_IDS', 'dt-allowed')
    try:
        db.add(User(id=2, username='allowed', password_hash='x', name='授权用户', role='manager', is_active=True, dingtalk_user_id='dt-allowed'))
        db.commit()
        code, payload = _run_cli([
            'rag-rebuild-index',
            '--dingtalk-user-id',
            'dt-allowed',
        ], capsys)

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'owner_required'
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_agent_cli_keeps_name_owner_fallback_for_existing_commands(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.delenv('HERMES_OWNER_DINGTALK_USER_IDS', raising=False)
    monkeypatch.delenv('HERMES_ALLOWED_DINGTALK_USER_IDS', raising=False)
    monkeypatch.setattr(agent_cli.settings, 'APP_ENV', 'production', raising=False)
    try:
        db.add(
            User(
                id=30,
                username='name-owner',
                password_hash='x',
                name='张兆嘉',
                role='admin',
                is_active=True,
                dingtalk_user_id='dt-name-owner',
            )
        )
        db.commit()

        code, payload = _run_cli(
            [
                'rag-rebuild-index',
                '--dingtalk-user-id',
                'dt-name-owner',
            ],
            capsys,
        )

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'rag-rebuild-index'
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_agent_cli_ingests_safe_system_understanding_copy(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    source = tmp_path / 'system-understanding.md'
    output = tmp_path / 'system-understanding.rag-safe.md'
    source.write_text(
        '智能大脑规则：数字来自数据中枢 CLI。\n'
        'DINGTALK_CLIENT_SECRET=real-secret-value-1234567890\n'
        '日报口径：7:30 生成前一个业务日。',
        encoding='utf-8',
    )
    try:
        db.add(User(id=3, username='zzj2', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'rag-ingest-system-understanding',
            '--path',
            str(source),
            '--output',
            str(output),
            '--dingtalk-user-id',
            'dt-owner',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'rag-ingest-system-understanding'
        assert payload['data']['status'] == 'active'
        assert output.exists()
        assert 'real-secret-value' not in output.read_text(encoding='utf-8')
        assert db.query(RagSourceIngestion).one().source_type == 'internal_system_understanding'
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_daily_report_outputs_finished_text(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')

    def fake_build_daily_report_product(*_args, **_kwargs):
        return {
            'status': 'ready',
            'business_date': '2026-06-17',
            'report_id': 88,
            'text': '6月17日，车间总产量日合计303吨（外加工0吨）。',
            'missing_fields': [],
            'conflicts': [],
            'scheduled_at': '10:00',
        }

    monkeypatch.setattr(agent_cli.daily_report_task, 'build_daily_report_product', fake_build_daily_report_product)
    try:
        db.add(User(id=4, username='zzj3', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '/日报',
            '--dingtalk-user-id',
            'dt-owner',
            '--group-id',
            'hermes-test',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'daily-report'
        assert payload['reply'].startswith('6月17日，车间总产量日合计303吨')
        assert payload['data']['business_date'] == '2026-06-17'
        assert payload['data']['report_id'] == 88
        assert payload['data']['status'] == 'ready'
        assert payload['data']['sent'] is False
        assert payload['data']['scheduled_at'] == '10:00'
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_slash_daily_report_with_date_stays_on_legacy_path(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    seen: dict[str, str] = {}

    def fake_build_daily_report_product(*_args, **_kwargs):
        seen['legacy_path'] = 'yes'
        return {
            'status': 'ready',
            'business_date': '2026-06-19',
            'report_id': 99,
            'text': '6月19日，车间总产量日合计305吨。',
            'missing_fields': [],
            'conflicts': [],
            'scheduled_at': '10:00',
        }

    def fail_day1_report(*_args, **_kwargs):
        raise AssertionError('slash /日报 不应该走 day1-report')

    monkeypatch.setattr(agent_cli.daily_report_task, 'build_daily_report_product', fake_build_daily_report_product)
    monkeypatch.setattr(agent_cli, '_cmd_day1_report', fail_day1_report)
    try:
        db.add(User(id=42, username='zzj-legacy-report', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '/日报 2026-06-19',
            '--dingtalk-user-id',
            'dt-owner',
            '--group-id',
            'hermes-test',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'daily-report'
        assert payload['data']['business_date'] == '2026-06-19'
        assert seen['legacy_path'] == 'yes'
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_command_natural_language_day1_routes_to_day1_report(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    seen: dict[str, str] = {}

    def fake_day1_report(_db, args, auth, **_kwargs):
        seen['text'] = args.text
        seen['user'] = auth.user.dingtalk_user_id
        return {
            'action': 'day1-report',
            'reply': '6月19日正式日报正文',
            'trace_id': 'trace-day1-route-001',
            'data': {
                'status': 'ready',
                'agent_run_id': 21,
                'report_id': 11,
                'chat_inbox_id': 7,
                'message_count': 2,
            },
        }

    monkeypatch.setattr(agent_cli, '_cmd_day1_report', fake_day1_report)
    try:
        db.add(User(id=41, username='zzj-day1', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '生成 6月19日正式日报',
            '--dingtalk-user-id',
            'dt-owner',
            '--trace-id',
            'trace-day1-route-001',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'day1-report'
        assert payload['reply'] == '6月19日正式日报正文'
        assert payload['data']['status'] == 'ready'
        assert seen == {'text': '生成 6月19日正式日报', 'user': 'dt-owner'}
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_command_flexible_final_report_text_routes_to_day1(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    monkeypatch.setenv('HERMES_DAY1_ENABLED', 'true')
    seen: dict[str, str] = {}

    def fake_day1_report(_db, args, auth, **kwargs):
        parsed_command = kwargs['parsed_command']
        seen['text'] = args.text
        seen['user'] = auth.user.dingtalk_user_id
        seen['business_date'] = parsed_command.business_date.isoformat()
        return {
            'action': 'day1-report',
            'reply': 'flexible day1 ok',
            'trace_id': 'trace-flexible-day1',
            'data': {'business_date': '2026-06-19'},
        }

    monkeypatch.setattr(agent_cli, '_cmd_day1_report', fake_day1_report)
    try:
        db.add(User(id=983, username='zzj-flexible-day1', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '6月19日按最终口径重新来一版',
            '--dingtalk-user-id',
            'dt-owner',
            '--trace-id',
            'trace-flexible-day1',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'day1-report'
        assert payload['data']['business_date'] == '2026-06-19'
        assert seen == {
            'text': '6月19日按最终口径重新来一版',
            'user': 'dt-owner',
            'business_date': '2026-06-19',
        }
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_command_flexible_final_report_invalid_date_has_actionable_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')

    def fail_agent_command(*_args, **_kwargs):
        raise AssertionError('flexible Day-1 invalid date should not reach normal Agent')

    monkeypatch.setattr(agent_cli, 'handle_agent_command', fail_agent_command)
    try:
        db.add(User(id=984, username='zzj-flexible-invalid-date', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '6月32日按最终口径重新来一版',
            '--dingtalk-user-id',
            'dt-owner',
            '--trace-id',
            'trace-flexible-invalid-date',
        ], capsys)

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'invalid_date'
        assert payload['detail']['trace_id'] == 'trace-flexible-invalid-date'
        assert payload['detail']['cause']
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_command_flexible_final_report_missing_date_has_actionable_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')

    def fail_agent_command(*_args, **_kwargs):
        raise AssertionError('flexible Day-1 missing date should not reach normal Agent')

    monkeypatch.setattr(agent_cli, 'handle_agent_command', fail_agent_command)
    try:
        db.add(User(id=985, username='zzj-flexible-missing-date', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '按最终口径重新来一版',
            '--dingtalk-user-id',
            'dt-owner',
            '--trace-id',
            'trace-flexible-missing-date',
        ], capsys)

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'day1_command_unrecognized'
        assert payload['detail']['trace_id'] == 'trace-flexible-missing-date'
        assert payload['detail']['fix']
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_command_records_unrelated_group_chat_without_reply(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        db.add(User(id=5, username='zzj4', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '收到，辛苦了',
            '--dingtalk-user-id',
            'dt-owner',
            '--group-id',
            'cid-production',
            '--trace-id',
            'msg-ordinary-001',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'dingtalk-message-recorded'
        assert payload['data']['should_reply'] is False
        assert payload['reply'] == ''
        assert db.query(ChatInboxMessage).count() == 1
        assert db.query(AgentRun).count() == 0
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_command_dedupes_same_message_trace_id(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        db.add(User(id=6, username='zzj5', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()
        args = [
            'dingtalk-command',
            '--text',
            '普通群消息',
            '--dingtalk-user-id',
            'dt-owner',
            '--group-id',
            'cid-production',
            '--trace-id',
            'ding-msg-duplicate-001',
        ]

        assert _run_cli(args, capsys)[1]['action'] == 'dingtalk-message-recorded'
        code, payload = _run_cli(args, capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'dingtalk-duplicate'
        assert payload['data']['should_reply'] is False
        assert db.query(ChatInboxMessage).count() == 1
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_command_auto_recognizes_clear_production_question(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    seen: dict[str, str] = {}

    def fake_handle_agent_command(*_args, **kwargs):
        seen['text'] = kwargs['text']
        return SimpleNamespace(
            answer='包装产量 303.03 吨',
            intent='production_today',
            status_color='green',
            facts={'data_source': 'test'},
            rag={'citations': []},
            chat_inbox_id=10,
            agent_run_id=20,
            outbox_message_id=None,
            trace_id=kwargs['trace_id'],
        )

    monkeypatch.setattr(agent_cli, 'handle_agent_command', fake_handle_agent_command)
    try:
        db.add(User(id=7, username='zzj6', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '今天包装产量多少',
            '--dingtalk-user-id',
            'dt-owner',
            '--group-id',
            'cid-production',
            '--trace-id',
            'trace-auto-production-001',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'agent-ask'
        assert payload['reply'] == '包装产量 303.03 吨'
        assert seen['text'] == '今天包装产量多少'
        event = db.query(HermesLearningEvent).one()
        assert event.trace_id == 'trace-auto-production-001'
        assert event.question == '今天包装产量多少'
        assert event.status == 'candidate'
        assert db.query(HermesApprovedLesson).count() == 0
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_mes_status_slash_reports_configured_readonly_link(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    monkeypatch.setattr(agent_cli.settings, 'MES_ADAPTER', 'sqlserver', raising=False)
    try:
        db.add(User(id=10, username='zzj-mes-status', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.add(
            MesSyncRunLog(
                cursor_key='coil_snapshots',
                started_at=datetime(2026, 6, 29, 19, 44, tzinfo=timezone.utc),
                finished_at=datetime(2026, 6, 29, 19, 45, tzinfo=timezone.utc),
                status='success',
                fetched_count=50,
                upserted_count=50,
                lag_seconds=0,
            )
        )
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '/MES状态',
            '--dingtalk-user-id',
            'dt-owner',
            '--group-id',
            'cid-production',
            '--trace-id',
            'trace-mes-status-001',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'mes-status'
        assert '不是未接入' in payload['reply']
        assert payload['data']['configured'] is True
        assert payload['data']['latest']['status'] == 'success'
        inbox = db.query(ChatInboxMessage).one()
        assert inbox.source_payload['handling'] == 'mes_status'
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_access_warning_routes_to_mes_status_instead_of_llm(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    monkeypatch.setattr(agent_cli.settings, 'MES_ADAPTER', 'sqlserver', raising=False)

    def fail_agent_command(*_args, **_kwargs):
        raise AssertionError('MES 接入状态不应该交给普通 Agent 猜')

    monkeypatch.setattr(agent_cli, 'handle_agent_command', fail_agent_command)
    try:
        db.add(User(id=11, username='zzj-access-warning', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '提示没有接入？',
            '--dingtalk-user-id',
            'dt-owner',
            '--group-id',
            'cid-production',
            '--trace-id',
            'trace-access-warning-001',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'mes-status'
        assert payload['data']['configured'] is True
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_rag_query_auto_promotes_stable_knowledge(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        db.add(User(id=8, username='zzj7', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner'))
        db.commit()
        create_document_from_bytes(
            db,
            filename='日报口径.md',
            content='日报口径：日报 7:30 输出前一个业务日。'.encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        db.commit()

        code, payload = _run_cli([
            'dingtalk-command',
            '--text',
            '/查知识 日报口径',
            '--dingtalk-user-id',
            'dt-owner',
            '--group-id',
            'cid-production',
            '--trace-id',
            'trace-rag-learning-001',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'rag-query'
        event = db.query(HermesLearningEvent).one()
        assert event.trace_id == 'trace-rag-learning-001'
        assert event.question == '日报口径'
        assert event.status == 'approved'
        assert db.query(HermesApprovedLesson).count() == 1
        assert not any((document.metadata_payload or {}).get('source_type') == 'approved_lesson' for document in db.query(RagDocument).all())
        inbox = db.query(ChatInboxMessage).one()
        assert inbox.trace_id == 'trace-rag-learning-001'
        assert inbox.text == '/查知识 日报口径'
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_learning_approve_cli_promotes_candidate_to_long_term_rag(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        user = User(id=9, username='zzj8', password_hash='x', name='张兆嘉', role='admin', is_active=True, dingtalk_user_id='dt-owner')
        db.add(user)
        db.flush()
        event = HermesLearningEvent(
            trace_id='trace-learn-approve-001',
            question='园区精整归哪里',
            answer='园区精整归园区剪切。',
            human_correction='园区精整在数据中枢归为园区剪切。',
            status='candidate',
            actor_user_id=user.id,
        )
        db.add(event)
        db.commit()

        code, payload = _run_cli([
            'learning-approve',
            '--learning-event-id',
            str(event.id),
            '--dingtalk-user-id',
            'dt-owner',
        ], capsys)

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'learning-approve'
        db.expire_all()
        assert db.get(HermesLearningEvent, event.id).status == 'approved'
        assert db.query(HermesApprovedLesson).count() == 1
        documents = db.query(RagDocument).all()
        assert any((document.metadata_payload or {}).get('source_type') == 'approved_lesson' for document in documents)
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()
