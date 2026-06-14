from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentOutboxMessage,
    AgentProfile,
    AgentRun,
    ChatInboxMessage,
    CommunicationChannel,
)
from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.system import User
from app.services import agent_communication_service
from app.services.rag_service import create_document_from_bytes


AGENT_COMMAND_TABLES = [
    User.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    AgentProfile.__table__,
    CommunicationChannel.__table__,
    AgentChannelBinding.__table__,
    AgentOutboxMessage.__table__,
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


def test_agent_command_can_queue_bound_group_reply_without_dispatch() -> None:
    db, previous_overrides = _install_overrides()

    try:
        create_document_from_bytes(
            db,
            filename='停机升级规则.md',
            content=('停机超过三十分钟需要升级给车间负责人，并进入橙色状态。' * 20).encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        agent_communication_service.register_agent(db, code='maintenance_agent', name='修停机 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-maintenance',
            name='修停机测试群',
            target_type='workshop',
            target_key='maintenance',
            dry_run=True,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='maintenance_agent',
            channel_key='chat-maintenance',
        )

        client = TestClient(app)
        response = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-maintenance',
                'sender_external_id': 'ding-user-002',
                'text': '停机超过三十分钟怎么办',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-outbox-001',
                'queue_outbox': True,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['outbox_message_id'] is not None

        message = db.get(AgentOutboxMessage, payload['outbox_message_id'])
        assert message is not None
        assert message.status == 'pending'
        assert message.attempts == 0
        assert message.trace_id == 'trace-agent-outbox-001'
        assert message.content == payload['answer']
        assert message.payload['chat_inbox_id'] == payload['chat_inbox_id']
        assert message.payload['agent_run_id'] == payload['agent_run_id']
        assert message.payload['rag_citation_count'] == 1

        run = db.get(AgentRun, payload['agent_run_id'])
        assert run.result_payload['outbox_message_id'] == payload['outbox_message_id']
    finally:
        _restore_overrides(previous_overrides, db)


def test_agent_command_reuses_group_reply_outbox_for_same_question() -> None:
    db, previous_overrides = _install_overrides()

    try:
        create_document_from_bytes(
            db,
            filename='停机升级规则.md',
            content=('停机超过三十分钟需要升级给车间负责人，并进入橙色状态。' * 20).encode('utf-8'),
            content_type='text/markdown',
            uploaded_by=None,
        )
        agent_communication_service.register_agent(db, code='maintenance_agent', name='修停机 Agent')
        agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-maintenance',
            name='修停机测试群',
            target_type='workshop',
            target_key='maintenance',
            dry_run=True,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code='maintenance_agent',
            channel_key='chat-maintenance',
        )

        client = TestClient(app)
        first = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-maintenance',
                'sender_external_id': 'ding-user-002',
                'text': '停机超过三十分钟怎么办',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-outbox-101',
                'queue_outbox': True,
            },
        )
        second = client.post(
            '/api/v1/agent/command',
            json={
                'channel': 'dingtalk_group',
                'group_id': 'chat-maintenance',
                'sender_external_id': 'ding-user-003',
                'text': '停机超过三十分钟怎么办',
                'agent_code': 'maintenance_agent',
                'trace_id': 'trace-agent-outbox-102',
                'queue_outbox': True,
            },
        )

        assert first.status_code == 200
        assert second.status_code == 200
        first_payload = first.json()
        second_payload = second.json()
        assert second_payload['outbox_message_id'] == first_payload['outbox_message_id']
        assert db.query(AgentOutboxMessage).count() == 1

        message = db.get(AgentOutboxMessage, first_payload['outbox_message_id'])
        assert message is not None
        assert message.dedupe_key == 'agent_command:dingtalk_group:chat-maintenance:maintenance_agent:8d8bd2d8b199e09b'
        assert message.dedupe_expires_at is not None
        assert db.query(ChatInboxMessage).count() == 2
        assert db.query(AgentRun).count() == 2
    finally:
        _restore_overrides(previous_overrides, db)
