from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentOutboxMessage
from app.services import agent_communication_service as service


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_queue_message_rejects_unbound_channel() -> None:
    db = _db_session()
    try:
        service.register_agent(db, code='workshop_status', name='车间汇报 Agent')
        service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-test',
            name='测试车间群',
            target_type='workshop',
            target_key='2',
            workshop_id=2,
        )

        with pytest.raises(service.AgentCommunicationError, match='agent_channel_not_bound'):
            service.queue_bound_message(
                db,
                agent_code='workshop_status',
                channel_key='chat-test',
                title='测试汇报',
                content='这条消息不应该入队',
                business_date=date(2026, 6, 13),
                source_summary='unit_test',
            )
    finally:
        db.close()


def test_dispatch_dry_run_message_records_log_without_sender_call() -> None:
    db = _db_session()
    sender_calls = []
    try:
        service.register_agent(db, code='workshop_status', name='车间汇报 Agent')
        service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-test',
            name='测试车间群',
            target_type='workshop',
            target_key='2',
            workshop_id=2,
            dry_run=True,
        )
        service.bind_agent_to_channel(db, agent_code='workshop_status', channel_key='chat-test')
        message = service.queue_bound_message(
            db,
            agent_code='workshop_status',
            channel_key='chat-test',
            title='【车间汇报】测试',
            content='产量 0 吨，仅用于 dry-run。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
            trace_id='trace-dry-run',
        )

        outcome = service.dispatch_outbox_message(
            db,
            message.id,
            sender=lambda *_args, **_kwargs: sender_calls.append((_args, _kwargs)) or (True, 'sent'),
        )

        assert outcome.status == 'dry_run'
        assert sender_calls == []
        db.refresh(message)
        assert message.status == 'dry_run'
        assert message.trace_id == 'trace-dry-run'
        logs = service.list_external_logs(db, outbox_message_id=message.id)
        assert len(logs) == 1
        assert logs[0].status == 'dry_run'
        assert logs[0].detail == 'dry-run only, message not sent'
    finally:
        db.close()


def test_dispatch_enabled_dingtalk_group_message_calls_sender_once() -> None:
    db = _db_session()
    sender_calls = []
    try:
        service.register_agent(db, code='factory_dispatch', name='全厂调度 Agent')
        service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-management',
            name='管理测试群',
            target_type='management',
            target_key='management',
            dry_run=False,
        )
        service.bind_agent_to_channel(db, agent_code='factory_dispatch', channel_key='chat-management')
        message = service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-management',
            title='【全厂总览】测试',
            content='全厂主动汇报测试消息。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )

        def fake_sender(chat_id: str, payload: dict) -> tuple[bool, str]:
            sender_calls.append((chat_id, payload))
            return True, 'dingtalk_sent'

        outcome = service.dispatch_outbox_message(db, message.id, sender=fake_sender)

        assert outcome.status == 'sent'
        assert sender_calls == [
            (
                'chat-management',
                {
                    'msgtype': 'markdown',
                    'markdown': {
                        'title': '【全厂总览】测试',
                        'text': '全厂主动汇报测试消息。',
                    },
                },
            )
        ]
        db.refresh(message)
        assert message.status == 'sent'
        assert message.sent_at is not None
        logs = service.list_external_logs(db, outbox_message_id=message.id)
        assert logs[0].status == 'sent'
        assert logs[0].detail == 'dingtalk_sent'
    finally:
        db.close()


def test_dispatch_failure_retries_twice_then_dead_letters_without_extra_send() -> None:
    db = _db_session()
    sender_calls = []
    try:
        service.register_agent(db, code='factory_dispatch', name='全厂调度 Agent')
        service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-management',
            name='管理测试群',
            target_type='management',
            target_key='management',
            dry_run=False,
        )
        service.bind_agent_to_channel(db, agent_code='factory_dispatch', channel_key='chat-management')
        message = service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-management',
            title='【全厂总览】失败重试测试',
            content='这条消息用于验证失败重试和死信。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )

        def failing_sender(chat_id: str, payload: dict) -> tuple[bool, str]:
            sender_calls.append((chat_id, payload))
            return False, 'dingtalk_timeout'

        first = service.dispatch_outbox_message(db, message.id, sender=failing_sender)
        db.refresh(message)
        assert first.status == 'retrying'
        assert message.status == 'retrying'
        assert message.attempts == 1
        assert message.last_error == 'dingtalk_timeout'
        assert message.next_retry_at is not None

        second = service.dispatch_outbox_message(db, message.id, sender=failing_sender)
        db.refresh(message)
        assert second.status == 'retrying'
        assert message.status == 'retrying'
        assert message.attempts == 2
        assert message.next_retry_at is not None

        third = service.dispatch_outbox_message(db, message.id, sender=failing_sender)
        db.refresh(message)
        assert third.status == 'dead_letter'
        assert message.status == 'dead_letter'
        assert message.attempts == 3
        assert message.next_retry_at is None

        fourth = service.dispatch_outbox_message(db, message.id, sender=failing_sender)
        db.refresh(message)
        assert fourth.status == 'dead_letter'
        assert len(sender_calls) == 3

        logs = service.list_external_logs(db, outbox_message_id=message.id)
        assert [log.status for log in logs] == ['retrying', 'retrying', 'dead_letter']
    finally:
        db.close()


def test_queue_message_dedupes_same_event_inside_thirty_minute_window() -> None:
    db = _db_session()
    try:
        service.register_agent(db, code='stop_detector', name='修停机 Agent')
        service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-maintenance',
            name='修停机测试群',
            target_type='workshop',
            target_key='2',
            workshop_id=2,
            dry_run=False,
        )
        service.bind_agent_to_channel(db, agent_code='stop_detector', channel_key='chat-maintenance')
        started_at = datetime(2026, 6, 13, 8, 0, tzinfo=UTC)

        first = service.queue_bound_message(
            db,
            agent_code='stop_detector',
            channel_key='chat-maintenance',
            title='【冷轧1650｜停机】测试',
            content='1#机停机 10 分钟。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
            trace_id='trace-stop-1',
            dedupe_key='machine_stop:workshop-2:line-1',
            now=started_at,
        )
        duplicate = service.queue_bound_message(
            db,
            agent_code='stop_detector',
            channel_key='chat-maintenance',
            title='【冷轧1650｜停机】测试重复',
            content='1#机停机 18 分钟。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
            trace_id='trace-stop-2',
            dedupe_key='machine_stop:workshop-2:line-1',
            now=started_at + timedelta(minutes=10),
        )
        after_window = service.queue_bound_message(
            db,
            agent_code='stop_detector',
            channel_key='chat-maintenance',
            title='【冷轧1650｜停机】测试升级',
            content='1#机停机 41 分钟。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
            trace_id='trace-stop-3',
            dedupe_key='machine_stop:workshop-2:line-1',
            now=started_at + timedelta(minutes=31),
        )

        assert duplicate.id == first.id
        assert duplicate.trace_id == 'trace-stop-1'
        assert after_window.id != first.id
        assert db.query(AgentOutboxMessage).count() == 2
    finally:
        db.close()


def test_rate_limit_key_blocks_duplicate_active_window() -> None:
    db = _db_session()
    try:
        first = service.record_rate_limit_hit(
            db,
            scope_key='workshop:2',
            event_key='machine_stop:2:line-1',
            window_started_at=datetime(2026, 6, 13, 8, 0, tzinfo=UTC),
            window_seconds=1800,
        )
        second = service.record_rate_limit_hit(
            db,
            scope_key='workshop:2',
            event_key='machine_stop:2:line-1',
            window_started_at=datetime(2026, 6, 13, 8, 5, tzinfo=UTC),
            window_seconds=1800,
        )

        assert first.allowed is True
        assert second.allowed is False
        assert second.detail == 'rate_limited'
    finally:
        db.close()
