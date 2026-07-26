from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import (
    AgentEvent,
    AgentOutboxMessage,
    CommunicationChannel,
    ExternalMessageLog,
)
from app.routers import hermes
from app.services import hermes_outbound_service


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_relay_proactive_message_uses_audited_work_notice_outbox(monkeypatch) -> None:
    monkeypatch.setattr(
        hermes_outbound_service.settings,
        'DINGTALK_NOTIFY_DRY_RUN',
        False,
        raising=False,
    )
    db = _db_session()
    sender_calls: list[tuple[str, dict]] = []

    def sender(target_user_id: str, payload: dict):
        sender_calls.append((target_user_id, payload))
        return True, {
            'detail': 'accepted',
            'provider_message_id': 'ding-work-notice-001',
        }

    try:
        outcome = hermes_outbound_service.relay_proactive_message(
            db,
            target_user_id='staff-user-001',
            title='鑫泰铝业智能大脑',
            content='今日事实核查已完成。',
            trace_id='hermes-proactive-test-001',
            dedupe_key='hermes-proactive-dedupe-001',
            source_ref='cron-test-001',
            sender=sender,
        )

        assert outcome.status == 'sent'
        assert outcome.duplicate is False
        assert len(sender_calls) == 1
        assert sender_calls[0][0] == 'staff-user-001'

        event = db.get(AgentEvent, outcome.event_id)
        message = db.get(AgentOutboxMessage, outcome.outbox_message_id)
        channel = db.get(CommunicationChannel, message.channel_id)
        logs = (
            db.query(ExternalMessageLog)
            .filter(ExternalMessageLog.outbox_message_id == message.id)
            .all()
        )

        assert event is not None
        assert event.event_type == 'hermes_proactive_message'
        assert event.status == 'completed'
        assert event.payload['trace_id'] == 'hermes-proactive-test-001'
        assert message is not None
        assert message.event_id == event.id
        assert message.source_summary == 'hermes_gateway_proactive_outbound'
        assert message.trace_id == 'hermes-proactive-test-001'
        assert channel is not None
        assert channel.channel_type == 'dingtalk_work_notice'
        assert channel.target_key == 'staff-user-001'
        assert logs[0].status == 'sent'
        assert logs[0].provider_message_id == 'ding-work-notice-001'
    finally:
        db.close()


def test_relay_proactive_message_dedupes_before_external_send(monkeypatch) -> None:
    monkeypatch.setattr(
        hermes_outbound_service.settings,
        'DINGTALK_NOTIFY_DRY_RUN',
        False,
        raising=False,
    )
    db = _db_session()
    sender_calls: list[str] = []

    def sender(target_user_id: str, _payload: dict):
        sender_calls.append(target_user_id)
        return True, 'accepted'

    try:
        first = hermes_outbound_service.relay_proactive_message(
            db,
            target_user_id='staff-user-001',
            title='鑫泰铝业智能大脑',
            content='同一条主动消息。',
            dedupe_key='hermes-proactive-dedupe-002',
            sender=sender,
        )
        second = hermes_outbound_service.relay_proactive_message(
            db,
            target_user_id='staff-user-001',
            title='鑫泰铝业智能大脑',
            content='同一条主动消息。',
            dedupe_key='hermes-proactive-dedupe-002',
            sender=sender,
        )

        assert first.outbox_message_id == second.outbox_message_id
        assert second.duplicate is True
        assert sender_calls == ['staff-user-001']
        assert db.query(AgentEvent).count() == 1
        assert db.query(AgentOutboxMessage).count() == 1
    finally:
        db.close()


def test_hermes_outbound_route_requires_stream_relay_token(monkeypatch) -> None:
    monkeypatch.setattr(
        hermes.settings,
        'HERMES_DINGTALK_STREAM_RELAY_TOKEN',
        'relay-secret',
        raising=False,
    )
    request = hermes.HermesOutboundRequest(
        target_user_id='staff-user-001',
        content='测试消息',
    )

    with pytest.raises(HTTPException, match='hermes_outbound_token_invalid'):
        hermes.hermes_outbound(
            payload=request,
            db=object(),
            relay_token='wrong-secret',
        )


def test_hermes_outbound_route_returns_durable_acceptance(monkeypatch) -> None:
    monkeypatch.setattr(
        hermes.settings,
        'HERMES_DINGTALK_STREAM_RELAY_TOKEN',
        'relay-secret',
        raising=False,
    )
    expected = hermes_outbound_service.HermesOutboundOutcome(
        status='retrying',
        event_id=12,
        outbox_message_id=34,
        duplicate=False,
    )
    monkeypatch.setattr(
        hermes.hermes_outbound_service,
        'relay_proactive_message',
        lambda *_args, **_kwargs: expected,
    )

    response = hermes.hermes_outbound(
        payload=hermes.HermesOutboundRequest(
            target_user_id='staff-user-001',
            content='测试消息',
            dedupe_key='dedupe-001',
        ),
        db=object(),
        relay_token='relay-secret',
    )

    assert response == {
        'success': True,
        'accepted': True,
        'status': 'retrying',
        'event_id': 12,
        'outbox_message_id': 34,
        'duplicate': False,
    }
