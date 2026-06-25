from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.agent_communication import AgentChannelBinding, AgentProfile, AgentRun, ChatInboxMessage, CommunicationChannel
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


def test_dingtalk_inbound_uses_factory_brain_when_enabled(monkeypatch) -> None:
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

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'hermes-token'},
            json={
                'conversationId': 'cid-root',
                'senderStaffId': 'dt-root',
                'senderUnionId': 'union-root',
                'text': {'content': '产量出来了吗'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-factory-brain-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['agent_code'] == 'factory_brain'
        assert payload['status'] == 'replied'
        assert db.query(ChatInboxMessage).one().agent_code == 'factory_brain'
        assert db.query(AgentRun).one().agent_code == 'factory_brain'
    finally:
        _restore(previous, db)
