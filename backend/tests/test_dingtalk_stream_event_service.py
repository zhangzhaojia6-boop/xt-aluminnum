from __future__ import annotations

import pytest

from app.services.dingtalk_stream_event_service import (
    build_stable_trace_id,
    is_authorized_group,
    normalize_dingtalk_stream_event,
    validate_authorized_group,
)


def test_text_event_normalizes_from_dingtalk_sdk_callback_data_shape() -> None:
    event = normalize_dingtalk_stream_event(
        {
            'headers': {'topic': 'chatbot_message'},
            'data': {
                'conversationId': 'cid-group-001',
                'conversationType': '2',
                'senderStaffId': 'staff-001',
                'senderUnionId': 'union-001',
                'messageId': 'msg-001',
                'msgtype': 'text',
                'text': {'content': '验收：今天包装入库 123.45 吨'},
                'createTime': '2026-07-08T08:30:00+08:00',
            },
        }
    )

    assert event.source == 'dingtalk_stream'
    assert event.channel == 'dingtalk_group'
    assert event.group_id == 'cid-group-001'
    assert event.message_id == 'msg-001'
    assert event.sender_staff_id == 'staff-001'
    assert event.sender_union_id == 'union-001'
    assert event.message_type == 'text'
    assert event.message_text == '验收：今天包装入库 123.45 吨'
    assert event.file_name is None
    assert event.download_code is None
    assert event.file_id is None
    assert event.event_time == '2026-07-08T08:30:00+08:00'
    assert event.trace_id == 'msg-001'


def test_file_event_normalizes_download_code_and_file_name() -> None:
    event = normalize_dingtalk_stream_event(
        {
            'openConversationId': 'cid-group-file-001',
            'senderStaffId': 'staff-file-001',
            'messageId': 'msg-file-001',
            'msgtype': 'file',
            'content': {
                'downloadCode': 'download-code-001',
                'fileName': '7月8日日报.xlsx',
                'fileId': 'file-001',
                'file': {
                    'fileName': 'should-not-win.xlsx',
                    'downloadCode': 'nested-download-code',
                },
            },
            'createTime': '2026-07-08 09:01:02',
        }
    )

    assert event.channel == 'dingtalk_group'
    assert event.group_id == 'cid-group-file-001'
    assert event.message_type == 'file'
    assert event.file_name == '7月8日日报.xlsx'
    assert event.download_code == 'download-code-001'
    assert event.file_id == 'file-001'
    assert event.message_text is None
    assert event.trace_id == 'msg-file-001'


def test_unknown_wording_is_still_captured_as_raw_evidence_text_when_group_is_authorized() -> None:
    event = normalize_dingtalk_stream_event(
        {
            'conversation': {'id': 'cid-authorized-001'},
            'senderId': 'staff-raw-001',
            'msgtype': 'richText',
            'body': {'content': '老板说今天先记原话，不要丢。'},
            'createAt': '2026-07-08T10:20:30+08:00',
        }
    )

    validated = validate_authorized_group(event, {'cid-authorized-001'})

    assert validated.group_id == 'cid-authorized-001'
    assert validated.message_text == '老板说今天先记原话，不要丢。'
    assert is_authorized_group(validated.group_id or '', {'cid-authorized-001'}) is True


def test_missing_group_id_is_rejected_by_gateway_helper() -> None:
    event = normalize_dingtalk_stream_event(
        {
            'senderStaffId': 'staff-no-group-001',
            'msgtype': 'text',
            'text': {'content': '没有群 id 的消息'},
            'messageId': 'msg-no-group-001',
        }
    )

    with pytest.raises(ValueError, match='missing_group_id'):
        validate_authorized_group(event, {'cid-authorized-001'})


def test_unauthorized_group_id_is_rejected_before_persistence() -> None:
    event = normalize_dingtalk_stream_event(
        {
            'chatId': 'cid-unauthorized-001',
            'senderStaffId': 'staff-unauthorized-001',
            'msgtype': 'text',
            'text': '这条消息不应该进库',
        }
    )

    with pytest.raises(ValueError, match='unauthorized_group_id'):
        validate_authorized_group(event, {'cid-authorized-001'})


def test_stable_trace_id_is_identical_for_the_same_event() -> None:
    event = normalize_dingtalk_stream_event(
        {
            'sessionWebhookExpiredTime': {'openConversationId': 'cid-stable-001'},
            'senderStaffId': 'staff-stable-001',
            'content': {'content': '同一条事件多次处理，trace 要一样'},
            'createTime': '2026-07-08T11:22:33+08:00',
        }
    )

    trace_id_first = build_stable_trace_id(event)
    trace_id_second = build_stable_trace_id(event)

    assert event.trace_id == trace_id_first
    assert trace_id_first == trace_id_second
    assert trace_id_first.startswith('dingtalk-stream-sha256:')
