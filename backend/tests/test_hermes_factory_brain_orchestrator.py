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


def test_orchestrator_persists_closed_loop_payload() -> None:
    db = _db()
    user = User(id=1, username='admin2', password_hash='x', name='张兆嘉', role='admin', is_active=True)
    db.add(user)
    db.commit()

    result = run_factory_brain_turn(
        db,
        text='今日产量',
        channel='dingtalk',
        group_id='cid-root',
        sender_external_id='dt-root',
        current_user=user,
        trace_id='trace-factory-brain-closed-loop',
        source_payload={'messageId': 'msg-closed-loop'},
    )
    db.commit()

    payload = result.result_payload['factory_brain']
    assert payload['intent']['task_type'] == 'daily_output'
    assert payload['normalized_request']['metrics'] == ['daily_output', 'monthly_output']
    assert payload['progress_cards'][-1]['stage'] == 'feedback'


def test_orchestrator_reuses_precommitted_ingress_inbox() -> None:
    db = _db()
    user = User(id=1, username='admin3', password_hash='x', name='张兆嘉', role='admin', is_active=True)
    inbox = ChatInboxMessage(
        channel='dingtalk_group',
        group_id='cid-root',
        sender_external_id='dt-root',
        text='今日产量',
        agent_code='factory_dispatch',
        trace_id='trace-factory-brain-ingress',
        source_payload={'source': 'dingtalk_inbound'},
    )
    db.add_all([user, inbox])
    db.commit()

    result = run_factory_brain_turn(
        db,
        text='今日产量',
        channel='dingtalk_group',
        group_id='cid-root',
        sender_external_id='dt-root',
        current_user=user,
        trace_id='trace-factory-brain-ingress',
        source_payload={'messageId': 'msg-ingress'},
        chat_inbox=inbox,
    )
    db.commit()

    assert result.chat_inbox_id == inbox.id
    assert db.query(ChatInboxMessage).count() == 1
    db.refresh(inbox)
    assert inbox.agent_code == 'factory_brain'
    assert inbox.source_payload['factory_brain'] is True
