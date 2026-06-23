from __future__ import annotations

import json
from datetime import date
from importlib import import_module

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_engine, get_sessionmaker
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.master import Workshop
from app.models.rag import HermesLearningEvent, HermesShortTermMemory
from app.models.reports import DailyFactCorrection, DailyReport
from app.models.system import AuditLog, User
from scripts import agent_cli


TABLES = [
    User.__table__,
    Workshop.__table__,
    DailyReport.__table__,
    DailyFactCorrection.__table__,
    ChatInboxMessage.__table__,
    AgentRun.__table__,
    HermesLearningEvent.__table__,
    HermesShortTermMemory.__table__,
    AuditLog.__table__,
]


@pytest.fixture(autouse=True)
def _clear_day1_env(monkeypatch) -> None:
    for name in (
        'HERMES_DAY1_ENABLED',
        'HERMES_OWNER_DINGTALK_USER_IDS',
        'HERMES_ALLOWED_DINGTALK_USER_IDS',
        'HERMES_ALLOWED_GROUP_IDS',
        'OUTPUT_SKILL_ROOT',
        'OUTPUT_SKILL_REFERENCE_ROOT',
    ):
        monkeypatch.delenv(name, raising=False)


def _install_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'day1-cli.db'}"
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


def _patch_day1_orchestrator_pipeline(monkeypatch) -> None:
    service = import_module('app.services.hermes_day1_orchestrator')
    monkeypatch.setattr(
        service,
        'collect_day1_sources',
        lambda *_args, **_kwargs: {
            'trace_id': 'trace-day1-cli-source-001',
            'business_date': '2026-06-19',
            'template_daily_report': {'status': 'ready', 'text': '模板日报正文'},
            'mes_wms': {'source_status': {'mes': 'ok'}, 'records': {'summary': [{'field': 'total_output'}]}},
            'audit_run': {'status': 'completed', 'match_rate': 0.98, 'source_status': {'mes': 'ok', 'hub': 'ok'}},
            'dingtalk_evidence': [],
            'dingtalk_messages': [],
            'historical_reports': [],
            'rag': {'answer': '日报口径', 'citations': [{'source_ref': 'doc#1'}]},
        },
    )
    monkeypatch.setattr(
        service,
        'build_day1_three_part_report',
        lambda **_kwargs: {
            'status': 'ready',
            'text': '工厂大脑判断单\n正式日报正文\n各车间明细',
            'formal_text': '6月19日正式日报正文',
            'brain_judgment': {'summary': '可以发布', 'risks': []},
            'workshop_details': [{'title': '2050车间', 'lines': ['日产量：80吨。']}],
            'dingtalk_answer': '工厂大脑判断单\n正式日报正文',
            'dingtalk_messages': ['工厂大脑判断单', '正式日报正文'],
            'missing_fields': [],
            'conflicts': [],
        },
    )


def _add_user(db: Session, *, user_id: int, name: str, dingtalk_user_id: str) -> None:
    db.add(
        User(
            id=user_id,
            username=f'user-{user_id}',
            password_hash='x',
            name=name,
            role='admin',
            is_active=True,
            dingtalk_user_id=dingtalk_user_id,
        )
    )
    db.commit()


def test_day1_report_doctor_returns_checks_without_writing_reports(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    output_skill_root = tmp_path / 'output-skill'
    output_skill_root.mkdir()
    monkeypatch.setenv('HERMES_DAY1_ENABLED', 'true')
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    monkeypatch.setenv('OUTPUT_SKILL_ROOT', str(output_skill_root))
    try:
        _add_user(db, user_id=1, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'day1-report',
                '--doctor',
                '--text',
                '生成 6月19日 root_owner 完整版三段式日报',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-day1-doctor-001',
            ],
            capsys,
        )

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'day1-report-doctor'
        assert payload['trace_id'] == 'trace-day1-doctor-001'
        assert payload['data']['checks']['feature_flag'] == 'ok'
        assert payload['data']['checks']['root_owner_identity'] == 'ok'
        assert payload['data']['checks']['command_parse'] == 'ok'
        assert payload['data']['checks']['output_skill_source'] == 'ok'
        assert db.query(DailyReport).count() == 0
        assert db.query(AgentRun).count() == 0
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_report_missing_dingtalk_identity_has_actionable_detail(capsys) -> None:
    code, payload = _run_cli(
        [
            'day1-report',
            '--doctor',
            '--text',
            '生成 6月19日正式日报',
            '--trace-id',
            'trace-missing-identity-001',
        ],
        capsys,
    )

    assert code == 1
    assert payload['ok'] is False
    assert payload['error'] == 'dingtalk_identity_required'
    assert payload['detail']['trace_id'] == 'trace-missing-identity-001'
    assert '钉钉' in payload['detail']['cause']
    assert '--dingtalk-user-id' in payload['detail']['fix']


def test_day1_report_unbound_user_has_actionable_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        code, payload = _run_cli(
            [
                'day1-report',
                '--doctor',
                '--text',
                '生成 6月19日正式日报',
                '--dingtalk-user-id',
                'dt-missing',
                '--trace-id',
                'trace-unbound-user-001',
            ],
            capsys,
        )

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'dingtalk_user_not_bound'
        assert payload['detail']['trace_id'] == 'trace-unbound-user-001'
        assert '未绑定' in payload['detail']['cause']
        assert '用户管理' in payload['detail']['fix']
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_report_unrecognized_command_has_actionable_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        _add_user(db, user_id=6, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'day1-report',
                '--doctor',
                '--text',
                '今天辛苦了',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-command-unrecognized-001',
            ],
            capsys,
        )

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'day1_command_unrecognized'
        assert payload['detail']['trace_id'] == 'trace-command-unrecognized-001'
        assert '日报' in payload['detail']['cause']
        assert '生成 6月19日正式日报' in payload['detail']['fix']
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_report_invalid_date_has_actionable_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        _add_user(db, user_id=7, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'day1-report',
                '--doctor',
                '--text',
                '生成 6月32日正式日报',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-invalid-date-001',
            ],
            capsys,
        )

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'invalid_date'
        assert payload['detail']['trace_id'] == 'trace-invalid-date-001'
        assert '日期非法' in payload['detail']['cause']
        assert '2026-06-19' in payload['detail']['fix']
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_report_invalid_target_date_has_actionable_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        _add_user(db, user_id=9, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'day1-report',
                '--doctor',
                '--target-date',
                '2026-99-99',
                '--text',
                '生成 6月19日正式日报',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-invalid-target-date-001',
            ],
            capsys,
        )

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'invalid_date'
        assert payload['detail']['trace_id'] == 'trace-invalid-target-date-001'
        assert '日期非法' in payload['detail']['cause']
        assert '2026-06-19' in payload['detail']['fix']
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_report_chinese_date_uses_business_date_year(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    output_skill_root = tmp_path / 'output-skill'
    output_skill_root.mkdir()
    monkeypatch.setenv('HERMES_DAY1_ENABLED', 'true')
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    monkeypatch.setenv('OUTPUT_SKILL_ROOT', str(output_skill_root))
    monkeypatch.setattr(agent_cli, 'last_completed_production_business_date', lambda: date(2025, 12, 31))
    try:
        _add_user(db, user_id=8, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'day1-report',
                '--doctor',
                '--text',
                '生成 6月19日正式日报',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-business-year-001',
            ],
            capsys,
        )

        assert code == 0
        assert payload['ok'] is True
        assert payload['data']['business_date'] == '2025-06-19'
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_report_allowed_user_gets_owner_required_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    monkeypatch.setenv('HERMES_ALLOWED_DINGTALK_USER_IDS', 'dt-allowed')
    try:
        _add_user(db, user_id=2, name='授权用户', dingtalk_user_id='dt-allowed')

        code, payload = _run_cli(
            [
                'day1-report',
                '--doctor',
                '--text',
                '生成 6月19日正式日报',
                '--dingtalk-user-id',
                'dt-allowed',
                '--trace-id',
                'trace-owner-required-001',
            ],
            capsys,
        )

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'owner_required'
        assert payload['detail']['trace_id'] == 'trace-owner-required-001'
        assert 'root_owner' in payload['detail']['cause']
        assert 'HERMES_OWNER_DINGTALK_USER_IDS' in payload['detail']['fix']
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_report_disabled_has_actionable_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_DAY1_ENABLED', 'false')
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        _add_user(db, user_id=3, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'day1-report',
                '--text',
                '生成 6月19日正式日报',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-disabled-001',
            ],
            capsys,
        )

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'hermes_day1_disabled'
        assert payload['detail']['trace_id'] == 'trace-disabled-001'
        assert 'HERMES_DAY1_ENABLED=false' in payload['detail']['cause']
        assert 'HERMES_DAY1_ENABLED=true' in payload['detail']['fix']
        assert db.query(DailyReport).count() == 0
        assert db.query(AgentRun).count() == 0
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_dingtalk_command_natural_day1_disabled_has_actionable_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_DAY1_ENABLED', 'false')
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    try:
        _add_user(db, user_id=31, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'dingtalk-command',
                '--text',
                '生成 6月19日正式日报',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-dingtalk-day1-disabled-001',
            ],
            capsys,
        )

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'hermes_day1_disabled'
        assert payload['detail']['trace_id'] == 'trace-dingtalk-day1-disabled-001'
        assert 'HERMES_DAY1_ENABLED=false' in payload['detail']['cause']
        assert 'HERMES_DAY1_ENABLED=true' in payload['detail']['fix']
        assert db.query(DailyReport).count() == 0
        assert db.query(AgentRun).count() == 0
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_report_missing_output_skill_source_has_actionable_detail(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_DAY1_ENABLED', 'true')
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    monkeypatch.delenv('OUTPUT_SKILL_ROOT', raising=False)
    try:
        _add_user(db, user_id=4, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'day1-report',
                '--text',
                '生成 6月19日正式日报',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-output-skill-missing-001',
            ],
            capsys,
        )

        assert code == 1
        assert payload['ok'] is False
        assert payload['error'] == 'output_skill_source_missing'
        assert payload['detail']['trace_id'] == 'trace-output-skill-missing-001'
        assert 'OUTPUT_SKILL_ROOT' in payload['detail']['cause']
        assert 'D:\\输出skill' in payload['detail']['fix']
        assert db.query(DailyReport).count() == 0
        assert db.query(AgentRun).count() == 0
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_direct_root_owner_correction_is_persisted_before_run(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    output_skill_root = tmp_path / 'output-skill'
    output_skill_root.mkdir()
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    monkeypatch.setenv('HERMES_DAY1_ENABLED', 'true')
    monkeypatch.setenv('OUTPUT_SKILL_ROOT', str(output_skill_root))

    def fake_run_day1(_db, *, command, actor, trace_id, chat_inbox=None):
        from app.services.hermes_day1_orchestrator import HermesDay1Result

        return HermesDay1Result(
            trace_id=trace_id,
            status='ready',
            answer='ok',
            reply_messages=['ok'],
            agent_run_id=1,
            report_id=1,
            payload={},
        )

    monkeypatch.setattr(agent_cli, 'run_day1_super_brain', fake_run_day1)
    try:
        _add_user(db, user_id=983, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'day1-report',
                '--text',
                '6月19日车间总产量改成366吨，直接按这个发。',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-direct-correction',
            ],
            capsys,
        )

        assert code == 0
        assert payload['ok'] is True
        row = db.query(DailyFactCorrection).one()
        assert row.business_date == date(2026, 6, 19)
        assert row.field_name == 'total_output_daily'
        assert row.value_payload == {'value': 366.0}
        assert row.unit == '吨'
        assert row.reason == 'root_owner 自然语言修正'
        assert row.trace_id == 'trace-direct-correction'
        assert row.actor_user_id == 983
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


def test_day1_report_runs_real_orchestrator_and_writes_report_run_and_inbox(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    output_skill_root = tmp_path / 'output-skill'
    output_skill_root.mkdir()
    monkeypatch.setenv('HERMES_DAY1_ENABLED', 'true')
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    monkeypatch.setenv('OUTPUT_SKILL_ROOT', str(output_skill_root))
    _patch_day1_orchestrator_pipeline(monkeypatch)
    try:
        _add_user(db, user_id=5, name='张兆嘉', dingtalk_user_id='dt-owner')

        code, payload = _run_cli(
            [
                'day1-report',
                '--text',
                '生成 6月19日 root_owner 完整版三段式日报',
                '--dingtalk-user-id',
                'dt-owner',
                '--trace-id',
                'trace-day1-cli-run-001',
            ],
            capsys,
        )

        assert code == 0
        assert payload['ok'] is True
        assert payload['action'] == 'day1-report'
        assert payload['trace_id'] == 'trace-day1-cli-run-001'
        assert payload['reply'] == '工厂大脑判断单\n正式日报正文'
        assert payload['data']['status'] == 'ready'
        assert payload['data']['message_count'] == 2
        assert payload['data']['chat_inbox_id'] is not None
        assert payload['data']['agent_run_id'] is not None
        assert payload['data']['report_id'] is not None
        assert db.query(DailyReport).count() == 1
        assert db.query(AgentRun).count() == 1
        assert db.query(ChatInboxMessage).count() == 1
        inbox = db.query(ChatInboxMessage).one()
        assert inbox.channel == 'dingtalk_private'
        assert inbox.trace_id == 'trace-day1-cli-run-001'
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()
