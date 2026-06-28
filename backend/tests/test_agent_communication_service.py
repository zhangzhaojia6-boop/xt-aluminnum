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


def test_dispatch_enabled_dingtalk_work_notice_calls_personal_sender_once() -> None:
    db = _db_session()
    sender_calls = []
    try:
        service.register_agent(db, code='factory_dispatch_zzj', name='张兆嘉全厂调度 Agent')
        service.register_channel(
            db,
            channel_type='dingtalk_work_notice',
            channel_key='666327013924069283',
            name='张兆嘉个人工作通知',
            target_type='user',
            target_key='666327013924069283',
            dry_run=False,
        )
        service.bind_agent_to_channel(
            db,
            agent_code='factory_dispatch_zzj',
            channel_key='666327013924069283',
            channel_type='dingtalk_work_notice',
        )
        message = service.queue_bound_message(
            db,
            agent_code='factory_dispatch_zzj',
            channel_key='666327013924069283',
            channel_type='dingtalk_work_notice',
            title='【张兆嘉测试】全厂总览',
            content='仅发给张兆嘉的个人工作通知测试。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )

        def fake_sender(userid: str, payload: dict) -> tuple[bool, str]:
            sender_calls.append((userid, payload))
            return True, 'dingtalk_work_notice_sent'

        outcome = service.dispatch_outbox_message(db, message.id, sender=fake_sender)

        assert outcome.status == 'sent'
        assert sender_calls == [
            (
                '666327013924069283',
                {
                    'msgtype': 'markdown',
                    'markdown': {
                        'title': '【张兆嘉测试】全厂总览',
                        'text': '仅发给张兆嘉的个人工作通知测试。',
                    },
                },
            )
        ]
        db.refresh(message)
        assert message.status == 'sent'
        logs = service.list_external_logs(db, outbox_message_id=message.id)
        assert logs[0].channel_type == 'dingtalk_work_notice'
        assert logs[0].channel_key == '666327013924069283'
        assert logs[0].status == 'sent'
    finally:
        db.close()


def test_dispatch_enabled_dingtalk_work_notice_uses_target_key_for_private_channel() -> None:
    db = _db_session()
    sender_calls = []
    private_channel_key = 'root_owner:factory_dispatch:dt-root-001'
    try:
        service.register_agent(db, code='factory_dispatch', name='全厂调度 Agent')
        service.register_channel(
            db,
            channel_type='dingtalk_work_notice',
            channel_key=private_channel_key,
            name='root_owner 私聊回复通道',
            target_type='user',
            target_key='dt-root-001',
            dry_run=False,
        )
        service.bind_agent_to_channel(
            db,
            agent_code='factory_dispatch',
            channel_key=private_channel_key,
            channel_type='dingtalk_work_notice',
        )
        message = service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key=private_channel_key,
            channel_type='dingtalk_work_notice',
            title='【root_owner】私聊回复',
            content='仅发给真实钉钉用户。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )

        def fake_sender(userid: str, payload: dict) -> tuple[bool, str]:
            sender_calls.append((userid, payload))
            return True, 'dingtalk_work_notice_sent'

        outcome = service.dispatch_outbox_message(db, message.id, sender=fake_sender)

        assert outcome.status == 'sent'
        assert sender_calls == [
            (
                'dt-root-001',
                {
                    'msgtype': 'markdown',
                    'markdown': {
                        'title': '【root_owner】私聊回复',
                        'text': '仅发给真实钉钉用户。',
                    },
                },
            )
        ]
        assert sender_calls[0][0] != private_channel_key
        logs = service.list_external_logs(db, outbox_message_id=message.id)
        assert logs[0].channel_type == 'dingtalk_work_notice'
        assert logs[0].channel_key == private_channel_key
    finally:
        db.close()


def test_dispatch_enabled_dingtalk_custom_robot_uses_channel_secret_ref(monkeypatch) -> None:
    db = _db_session()
    calls = []
    try:
        monkeypatch.setattr(
            service.dingtalk_service,
            'send_custom_robot_message',
            lambda webhook_ref, payload, *, secret_ref=None: calls.append((webhook_ref, payload, secret_ref)) or (
                True,
                {
                    'detail': 'dingtalk_custom_robot_sent',
                    'response_payload': {'errcode': 0, 'errmsg': 'ok'},
                },
            ),
        )
        service.register_agent(db, code='factory_dispatch_zzj', name='张兆嘉全厂调度 Agent')
        service.register_channel(
            db,
            channel_type='dingtalk_custom_robot',
            channel_key='DINGTALK_ROBOT_FACTORY_DISPATCH_WEBHOOK',
            name='鑫泰全厂调度 Agent 机器人',
            target_type='debug_group',
            target_key='zzj-debug-agent-group',
            dry_run=False,
            secret_ref='DINGTALK_ROBOT_FACTORY_DISPATCH_SECRET',
        )
        service.bind_agent_to_channel(
            db,
            agent_code='factory_dispatch_zzj',
            channel_key='DINGTALK_ROBOT_FACTORY_DISPATCH_WEBHOOK',
            channel_type='dingtalk_custom_robot',
        )
        message = service.queue_bound_message(
            db,
            agent_code='factory_dispatch_zzj',
            channel_key='DINGTALK_ROBOT_FACTORY_DISPATCH_WEBHOOK',
            channel_type='dingtalk_custom_robot',
            title='【全厂调度】机器人测试',
            content='通过自定义机器人发送。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )

        outcome = service.dispatch_outbox_message(db, message.id)

        assert outcome.status == 'sent'
        assert calls == [
            (
                'DINGTALK_ROBOT_FACTORY_DISPATCH_WEBHOOK',
                {
                    'msgtype': 'markdown',
                    'markdown': {
                        'title': '【全厂调度】机器人测试',
                        'text': '通过自定义机器人发送。',
                    },
                },
                'DINGTALK_ROBOT_FACTORY_DISPATCH_SECRET',
            )
        ]
        logs = service.list_external_logs(db, outbox_message_id=message.id)
        assert logs[0].channel_type == 'dingtalk_custom_robot'
        assert logs[0].channel_key == 'DINGTALK_ROBOT_FACTORY_DISPATCH_WEBHOOK'
    finally:
        db.close()


def test_dispatch_records_structured_provider_response_in_external_log() -> None:
    db = _db_session()
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
            title='【全厂总览】真实返回测试',
            content='全厂主动汇报测试消息。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )

        def structured_sender(_chat_id: str, _payload: dict) -> tuple[bool, dict]:
            return True, {
                'detail': 'dingtalk_sent',
                'provider_message_id': 'ding-msg-001',
                'response_payload': {'errcode': 0, 'errmsg': 'ok'},
            }

        outcome = service.dispatch_outbox_message(db, message.id, sender=structured_sender)

        assert outcome.status == 'sent'
        assert outcome.detail == 'dingtalk_sent'
        logs = service.list_external_logs(db, outbox_message_id=message.id)
        assert logs[0].status == 'sent'
        assert logs[0].detail == 'dingtalk_sent'
        assert logs[0].provider_message_id == 'ding-msg-001'
        assert logs[0].response_payload == {'errcode': 0, 'errmsg': 'ok'}
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

        message.next_retry_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        second = service.dispatch_outbox_message(db, message.id, sender=failing_sender)
        db.refresh(message)
        assert second.status == 'retrying'
        assert message.status == 'retrying'
        assert message.attempts == 2
        assert message.next_retry_at is not None

        message.next_retry_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
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


def test_dispatch_retrying_message_waits_until_next_retry_time_before_resending() -> None:
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
            title='【全厂总览】重试时间保护测试',
            content='这条消息用于验证未到重试时间不会重复发送。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )

        def failing_sender(chat_id: str, payload: dict) -> tuple[bool, str]:
            sender_calls.append((chat_id, payload))
            return False, 'dingtalk_timeout'

        first = service.dispatch_outbox_message(db, message.id, sender=failing_sender)
        db.refresh(message)
        assert first.status == 'retrying'
        assert message.attempts == 1
        assert message.next_retry_at is not None

        second = service.dispatch_outbox_message(
            db,
            message.id,
            sender=lambda *_args, **_kwargs: sender_calls.append(('unexpected', {})) or (True, 'sent'),
        )

        db.refresh(message)
        assert second.status == 'retrying'
        assert second.detail == 'retry_not_due'
        assert message.status == 'retrying'
        assert message.attempts == 1
        assert len(sender_calls) == 1
        logs = service.list_external_logs(db, outbox_message_id=message.id)
        assert [log.status for log in logs] == ['retrying']
    finally:
        db.close()


def test_dispatch_failure_records_structured_provider_response_in_external_log() -> None:
    db = _db_session()
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
            title='【全厂总览】失败返回测试',
            content='这条消息用于验证失败返回体留证。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )

        def structured_failure_sender(_chat_id: str, _payload: dict) -> tuple[bool, dict]:
            return False, {
                'errmsg': 'invalid robot code',
                'provider_message_id': 'ding-failed-001',
                'response_payload': {'errcode': 310000, 'request_id': 'req-failed-001'},
            }

        outcome = service.dispatch_outbox_message(db, message.id, sender=structured_failure_sender)

        assert outcome.status == 'retrying'
        assert outcome.detail == 'invalid robot code'
        logs = service.list_external_logs(db, outbox_message_id=message.id)
        assert logs[0].status == 'retrying'
        assert logs[0].detail == 'invalid robot code'
        assert logs[0].provider_message_id == 'ding-failed-001'
        assert logs[0].response_payload == {'errcode': 310000, 'request_id': 'req-failed-001'}
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


def test_dispatch_due_outbox_messages_only_sends_pending_and_due_retrying() -> None:
    db = _db_session()
    sender_calls = []
    now = datetime(2026, 6, 13, 9, 30, tzinfo=UTC)
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
        pending = service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-management',
            title='待发送消息',
            content='这条消息应该被批量调度发送。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )
        due_retry = service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-management',
            title='到点重试消息',
            content='这条消息已经到重试时间。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )
        future_retry = service.queue_bound_message(
            db,
            agent_code='factory_dispatch',
            channel_key='chat-management',
            title='未到点重试消息',
            content='这条消息还不能再次发送。',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
        )
        due_retry.status = 'retrying'
        due_retry.attempts = 1
        due_retry.next_retry_at = now - timedelta(minutes=1)
        future_retry.status = 'retrying'
        future_retry.attempts = 1
        future_retry.next_retry_at = now + timedelta(minutes=10)
        db.commit()

        def fake_sender(chat_id: str, payload: dict) -> tuple[bool, str]:
            sender_calls.append((chat_id, payload['markdown']['title']))
            return True, 'dingtalk_sent'

        outcomes = service.dispatch_due_outbox_messages(db, limit=10, sender=fake_sender, now=now)

        assert [item.outbox_message_id for item in outcomes] == [pending.id, due_retry.id]
        assert [item.status for item in outcomes] == ['sent', 'sent']
        assert sender_calls == [
            ('chat-management', '待发送消息'),
            ('chat-management', '到点重试消息'),
        ]
        db.refresh(pending)
        db.refresh(due_retry)
        db.refresh(future_retry)
        assert pending.status == 'sent'
        assert due_retry.status == 'sent'
        assert future_retry.status == 'retrying'
        assert future_retry.attempts == 1
        assert service.list_external_logs(db, outbox_message_id=future_retry.id) == []
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
