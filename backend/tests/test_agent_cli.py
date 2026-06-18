from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_engine, get_sessionmaker
from app.models.master import Workshop
from app.models.rag import RagChunk, RagDocument, RagEmbedding, RagQueryLog, RagSourceIngestion
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
    DailyReport.__table__,
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


def test_agent_cli_ingests_safe_system_understanding_copy(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
    source = tmp_path / 'system-understanding.md'
    output = tmp_path / 'system-understanding.rag-safe.md'
    source.write_text(
        'Hermes 工厂规则：数字来自数据中枢 CLI。\n'
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


def test_dingtalk_daily_report_without_archive_returns_safe_preview_message(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv('HERMES_OWNER_DINGTALK_USER_IDS', 'dt-owner')
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
        assert payload['action'] == 'approval-preview'
        assert payload['data']['status'] == 'daily_report_not_found'
        assert payload['data']['sent'] is False
        assert payload['data']['approval_id'] is None
    finally:
        db.close()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()
