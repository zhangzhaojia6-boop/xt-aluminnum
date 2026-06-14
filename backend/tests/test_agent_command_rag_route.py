from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.system import User
from app.services.rag_service import create_document_from_bytes


AGENT_COMMAND_TABLES = [
    User.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    ChatInboxMessage.__table__,
    AgentRun.__table__,
]


def _install_overrides(*, role: str = 'admin'):
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=AGENT_COMMAND_TABLES)
    db = Session(engine)

    def fake_get_db():
        yield db

    def fake_get_user() -> User:
        return User(id=1, username=role, password_hash='x', name='User', role=role, is_active=True)

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    return db, previous_overrides


def _restore_overrides(previous_overrides, db: Session) -> None:
    db.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_agent_command_answers_from_rag_and_records_audit_trail() -> None:
    db, previous_overrides = _install_overrides()

    try:
        create_document_from_bytes(
            db,
            filename='换辊处理规则.md',
            content=('换辊超时需要通知设备员，超过三十分钟升级为橙色异常。' * 20).encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        db.commit()

        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-test',
                'sender_external_id': 'ding-user-001',
                'text': '换辊超时怎么办',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-rag-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['trace_id'] == 'trace-agent-rag-001'
        assert payload['status_color'] == 'green'
        assert payload['answer'].startswith('【全厂｜')
        assert '状态：绿' in payload['answer']
        assert '换辊超时' in payload['answer']
        assert '数据来源' in payload['answer']
        assert payload['rag']['citations'][0]['filename'] == '换辊处理规则.md'
        assert payload['outbox_message_id'] is None

        inbox = db.query(ChatInboxMessage).one()
        assert inbox.group_id == 'chat-test'
        assert inbox.sender_external_id == 'ding-user-001'
        assert inbox.text == '换辊超时怎么办'
        assert inbox.trace_id == 'trace-agent-rag-001'

        run = db.query(AgentRun).one()
        assert run.trace_id == 'trace-agent-rag-001'
        assert run.agent_code == 'maintenance_agent'
        assert run.rag_citation_count == 1
        assert run.status == 'answered'
        assert run.result_payload['status_color'] == 'green'

        assert db.query(RagQueryLog).count() == 1
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_requires_management_scope() -> None:
    db, previous_overrides = _install_overrides(role='machine_operator')

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-test',
                'sender_external_id': 'ding-user-001',
                'text': '今日产量',
                'agent_code': 'factory_dispatch',
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'Agent command access denied'
    finally:
        _restore_overrides(previous_overrides, db)
