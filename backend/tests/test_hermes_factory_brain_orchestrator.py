from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.base import Base
from app.models.master import Team, Workshop
from app.models.system import User
from app.services.hermes_factory_brain_orchestrator import run_factory_brain_turn


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Workshop.__table__, Team.__table__, User.__table__, ChatInboxMessage.__table__, AgentRun.__table__],
    )
    return Session(engine)


def test_orchestrator_persists_inbox_and_agent_run() -> None:
    db = _db()
    user = User(id=1, username='admin', password_hash='x', name='张兆嘉', role='admin', is_active=True)
    db.add(user)
    db.commit()

    result = run_factory_brain_turn(
        db,
        text='产量出来了吗',
        channel='dingtalk_group',
        group_id='cid-root',
        sender_external_id='dt-root',
        current_user=user,
        trace_id='trace-factory-brain-001',
        source_payload={'messageId': 'msg-001'},
    )
    db.commit()

    assert result.trace_id == 'trace-factory-brain-001'
    assert result.status == 'replied'
    assert db.query(ChatInboxMessage).one().text == '产量出来了吗'
    run = db.query(AgentRun).one()
    assert run.result_payload['factory_brain']['state_trace'][-1] == 'reply_to_dingtalk'
