import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

from app.database import Base, get_db
from app.main import app
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentProfile,
    AgentRun,
    ChatInboxMessage,
    CommunicationChannel,
    MultimodalEvidence,
)
from app.models.master import Workshop
from app.models.system import User


FACTORY_BRAIN_INBOUND_TABLES = [
    User.__table__,
    Workshop.__table__,
    AgentProfile.__table__,
    CommunicationChannel.__table__,
    AgentChannelBinding.__table__,
    ChatInboxMessage.__table__,
    AgentRun.__table__,
    MultimodalEvidence.__table__,
]


def _install_db_override():
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=FACTORY_BRAIN_INBOUND_TABLES)
    db = Session(engine)

    def fake_get_db():
        yield db

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    return db, previous


def _restore(previous, db: Session) -> None:
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    db.close()


@pytest.mark.parametrize(
    ('text', 'trace_id'),
    [
        ('产量', 'trace-dingtalk-factory-brain-001'),
        ('今天怎么样', 'trace-dingtalk-factory-brain-002'),
        ('库存够不够', 'trace-dingtalk-factory-brain-003'),
        ('合同余量', 'trace-dingtalk-factory-brain-004'),
        ('能耗是不是异常', 'trace-dingtalk-factory-brain-005'),
        ('成本核算发我', 'trace-dingtalk-factory-brain-006'),
        ('生成一张产量表格', 'trace-dingtalk-factory-brain-007'),
        ('昨日日报', 'trace-dingtalk-factory-brain-008'),
    ],
)
def test_dingtalk_inbound_uses_factory_brain_for_rule_first_business_inputs(monkeypatch, text: str, trace_id: str) -> None:
    db, previous = _install_db_override()
    db.add(
        User(
            id=1,
            username='root-owner',
            password_hash='x',
            name='张兆嘉',
            role='admin',
            is_active=True,
            dingtalk_user_id='dt-root',
            dingtalk_union_id='union-root',
        )
    )
    db.commit()
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED', True, raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_DINGTALK_INBOUND_TOKEN', 'hermes-token', raising=False)
    monkeypatch.setattr(
        'app.services.hermes_factory_brain_orchestrator.run_factory_brain_turn',
        lambda *_args, **_kwargs: SimpleNamespace(
            trace_id=trace_id,
            status='replied',
            answer='工厂大脑回复',
            chat_inbox_id=1,
            agent_run_id=1,
        ),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'hermes-token'},
            json={
                'conversationId': 'cid-root',
                'conversationType': 'group',
                'senderStaffId': 'dt-root',
                'senderUnionId': 'union-root',
                'text': {'content': text},
                'agentCode': 'factory_dispatch',
                'traceId': trace_id,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['agent_code'] == 'factory_brain'
        assert payload['status'] == 'replied'
    finally:
        _restore(previous, db)


def test_dingtalk_inbound_falls_back_for_non_business_natural_language(monkeypatch) -> None:
    db, previous = _install_db_override()
    db.add(
        User(
            id=1,
            username='root-owner',
            password_hash='x',
            name='张兆嘉',
            role='admin',
            is_active=True,
            dingtalk_user_id='dt-root',
            dingtalk_union_id='union-root',
        )
    )
    db.commit()
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED', True, raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_DINGTALK_INBOUND_TOKEN', 'hermes-token', raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root', raising=False)
    monkeypatch.setattr(
        'app.routers.dingtalk.handle_agent_command',
        lambda *_args, **_kwargs: SimpleNamespace(
            trace_id='trace-dingtalk-fallback-natural-001',
            status_color='green',
            intent='general_chat',
            answer='旧链路回复',
            chat_inbox_id=1,
            agent_run_id=1,
            outbox_message_id=None,
        ),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'hermes-token'},
            json={
                'conversationId': 'cid-root',
                'conversationType': 'group',
                'senderStaffId': 'dt-root',
                'senderUnionId': 'union-root',
                'text': {'content': '给我讲个轻松的笑话'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-fallback-natural-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload.get('agent_code') != 'factory_brain'
        assert payload['answer'] == '旧链路回复'
        assert db.query(AgentRun).count() == 0
    finally:
        _restore(previous, db)


def test_dingtalk_inbound_rejects_root_owner_only_factory_brain_request_for_non_root_owner(monkeypatch) -> None:
    db, previous = _install_db_override()
    db.add(
        User(
            id=1,
            username='manager-not-owner',
            password_hash='x',
            name='授权经理',
            role='manager',
            is_manager=True,
            is_active=True,
            dingtalk_user_id='dt-manager-not-owner',
            dingtalk_union_id='union-manager-not-owner',
        )
    )
    db.commit()

    orchestrator_called = {'value': False}

    def fake_run_factory_brain_turn(*_args, **_kwargs):
        orchestrator_called['value'] = True
        return SimpleNamespace(
            trace_id='trace-dingtalk-root-owner-only-denied-001',
            status='replied',
            answer='不该进入这里',
            chat_inbox_id=1,
            agent_run_id=1,
        )

    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED', True, raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_DINGTALK_INBOUND_TOKEN', 'hermes-token', raising=False)
    monkeypatch.delenv('HERMES_OWNER_DINGTALK_USER_IDS', raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_OWNER_DINGTALK_USER_IDS', '', raising=False)
    monkeypatch.setattr(
        'app.services.hermes_factory_brain_orchestrator.run_factory_brain_turn',
        fake_run_factory_brain_turn,
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'hermes-token'},
            json={
                'conversationId': 'cid-non-root-owner',
                'senderStaffId': 'dt-manager-not-owner',
                'senderUnionId': 'union-manager-not-owner',
                'text': {'content': '帮我生成 skill'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-root-owner-only-denied-001',
            },
        )

        assert response.status_code == 403
        assert response.json()['detail'] == 'owner_required'
        assert orchestrator_called['value'] is False
        assert db.query(ChatInboxMessage).count() == 0
        assert db.query(AgentRun).count() == 0
    finally:
        _restore(previous, db)


@pytest.mark.parametrize(
    ('text', 'trace_id'),
    [
        ('你好', 'trace-dingtalk-fallback-natural-hello-001'),
        ('随便聊两句', 'trace-dingtalk-fallback-natural-chat-001'),
        ('帮我随便说点什么', 'trace-dingtalk-fallback-natural-random-001'),
        ('GitHub skill 文档在哪里', 'trace-dingtalk-fallback-natural-skill-doc-001'),
        ('这个PDF打不开', 'trace-dingtalk-fallback-natural-pdf-001'),
        ('这张图片发不过去', 'trace-dingtalk-fallback-natural-image-001'),
        ('你有什么意见', 'trace-dingtalk-fallback-natural-opinion-001'),
    ],
)
def test_dingtalk_inbound_falls_back_for_ordinary_non_business_text(monkeypatch, text: str, trace_id: str) -> None:
    db, previous = _install_db_override()
    db.add(
        User(
            id=1,
            username='root-owner',
            password_hash='x',
            name='张兆嘉',
            role='admin',
            is_active=True,
            dingtalk_user_id='dt-root',
            dingtalk_union_id='union-root',
        )
    )
    db.commit()
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED', True, raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_DINGTALK_INBOUND_TOKEN', 'hermes-token', raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root', raising=False)
    monkeypatch.setattr(
        'app.routers.dingtalk.handle_agent_command',
        lambda *_args, **_kwargs: SimpleNamespace(
            trace_id=trace_id,
            status_color='green',
            intent='general_chat',
            answer='旧链路回复',
            chat_inbox_id=1,
            agent_run_id=1,
            outbox_message_id=None,
        ),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'hermes-token'},
            json={
                'conversationId': 'cid-root',
                'conversationType': 'group',
                'senderStaffId': 'dt-root',
                'senderUnionId': 'union-root',
                'text': {'content': text},
                'agentCode': 'factory_dispatch',
                'traceId': trace_id,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload.get('agent_code') != 'factory_brain'
        assert payload['answer'] == '旧链路回复'
        assert db.query(AgentRun).count() == 0
    finally:
        _restore(previous, db)


def test_dingtalk_inbound_falls_back_for_non_factory_brain_text(monkeypatch) -> None:
    db, previous = _install_db_override()
    db.add(
        User(
            id=1,
            username='root-owner',
            password_hash='x',
            name='张兆嘉',
            role='admin',
            is_active=True,
            dingtalk_user_id='dt-root',
            dingtalk_union_id='union-root',
        )
    )
    db.commit()
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED', True, raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_DINGTALK_INBOUND_TOKEN', 'hermes-token', raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_OWNER_DINGTALK_USER_IDS', 'dt-root', raising=False)
    monkeypatch.setattr(
        'app.routers.dingtalk.handle_agent_command',
        lambda *_args, **_kwargs: SimpleNamespace(
            trace_id='trace-dingtalk-fallback-001',
            status_color='green',
            intent='help',
            answer='旧链路回复',
            chat_inbox_id=1,
            agent_run_id=1,
            outbox_message_id=None,
        ),
    )

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'hermes-token'},
            json={
                'conversationId': 'cid-root',
                'conversationType': 'group',
                'senderStaffId': 'dt-root',
                'senderUnionId': 'union-root',
                'text': {'content': '/commands'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-fallback-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload.get('agent_code') != 'factory_brain'
        assert payload['answer'] == '旧链路回复'
        assert db.query(AgentRun).count() == 0
    finally:
        _restore(previous, db)
