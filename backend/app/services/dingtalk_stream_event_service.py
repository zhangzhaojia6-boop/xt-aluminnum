from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any, Mapping


ALL_GROUPS_MARKER = '*'


@dataclass(frozen=True, slots=True)
class NormalizedDingTalkEvent:
    source: str
    channel: str
    group_id: str | None
    trace_id: str
    message_id: str | None
    sender_staff_id: str | None
    sender_union_id: str | None
    message_type: str | None
    message_text: str | None
    file_name: str | None
    download_code: str | None
    file_id: str | None
    event_time: str | None
    raw_payload: Mapping[str, Any]


def normalize_dingtalk_stream_event(payload: Mapping[str, Any]) -> NormalizedDingTalkEvent:
    event_payload = _unwrap_event_payload(payload)
    group_id = _extract_group_id(event_payload)
    normalized = NormalizedDingTalkEvent(
        source='dingtalk_stream',
        channel=_resolve_channel(event_payload, group_id=group_id),
        group_id=group_id,
        trace_id='',
        message_id=_first_text(
            event_payload.get('messageId'),
            event_payload.get('msgId'),
            event_payload.get('message_id'),
            event_payload.get('messageid'),
        ),
        sender_staff_id=_first_text(
            event_payload.get('senderStaffId'),
            event_payload.get('senderId'),
            event_payload.get('senderUserId'),
            event_payload.get('staffId'),
            event_payload.get('userid'),
            event_payload.get('userId'),
        ),
        sender_union_id=_first_text(
            event_payload.get('senderUnionId'),
            event_payload.get('unionId'),
        ),
        message_type=_first_text(
            event_payload.get('msgtype'),
            event_payload.get('messageType'),
            event_payload.get('message_type'),
            event_payload.get('type'),
        ),
        message_text=_extract_message_text(event_payload),
        file_name=_extract_file_name(event_payload),
        download_code=_extract_download_code(event_payload),
        file_id=_extract_file_id(event_payload),
        event_time=_first_text(
            event_payload.get('createTime'),
            event_payload.get('msgCreateTime'),
            event_payload.get('messageTime'),
            event_payload.get('createAt'),
            event_payload.get('eventTime'),
            event_payload.get('timestamp'),
        ),
        raw_payload=dict(event_payload),
    )
    return replace(normalized, trace_id=build_stable_trace_id(normalized))


def is_authorized_group(group_id: str, allowed_group_ids: set[str]) -> bool:
    clean_group_id = _clean_text(group_id)
    if not clean_group_id:
        return False
    clean_allowed = {_clean_text(item) for item in allowed_group_ids if _clean_text(item)}
    if ALL_GROUPS_MARKER in clean_allowed:
        return True
    return clean_group_id in clean_allowed


def validate_authorized_group(
    event: NormalizedDingTalkEvent,
    allowed_group_ids: set[str],
) -> NormalizedDingTalkEvent:
    if not _clean_text(event.group_id):
        raise ValueError('missing_group_id')
    if not is_authorized_group(event.group_id or '', allowed_group_ids):
        raise ValueError('unauthorized_group_id')
    return event


def build_stable_trace_id(event: NormalizedDingTalkEvent) -> str:
    if _clean_text(event.message_id):
        return _clean_text(event.message_id)
    if _clean_text(event.file_id):
        return _clean_text(event.file_id)

    sender = _clean_text(event.sender_staff_id) or _clean_text(event.sender_union_id)
    payload = '|'.join(
        (
            _clean_text(event.group_id),
            sender,
            _clean_text(event.event_time),
            _clean_text(event.message_text) or _clean_text(event.file_name),
        )
    )
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    return f'dingtalk-stream-sha256:{digest}'


def _unwrap_event_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get('data')
    if isinstance(data, Mapping):
        return data
    return payload


def _extract_group_id(payload: Mapping[str, Any]) -> str | None:
    return _first_text(
        payload.get('conversationId'),
        payload.get('openConversationId'),
        payload.get('chatId'),
        _path_value(payload, 'sessionWebhookExpiredTime', 'openConversationId'),
        _path_value(payload, 'conversation', 'id'),
    )


def _extract_message_text(payload: Mapping[str, Any]) -> str | None:
    return _first_text(
        _path_value(payload, 'text', 'content'),
        _path_value(payload, 'content', 'text'),
        _path_value(payload, 'content', 'content'),
        payload.get('text'),
        _path_value(payload, 'msgParam', 'content'),
        _path_value(payload, 'body', 'content'),
    )


def _extract_download_code(payload: Mapping[str, Any]) -> str | None:
    return _first_text(
        _path_value(payload, 'content', 'downloadCode'),
        payload.get('downloadCode'),
        _path_value(payload, 'file', 'downloadCode'),
        _path_value(payload, 'content', 'file', 'downloadCode'),
    )


def _extract_file_name(payload: Mapping[str, Any]) -> str | None:
    return _first_text(
        _path_value(payload, 'content', 'fileName'),
        payload.get('fileName'),
        _path_value(payload, 'file', 'fileName'),
        _path_value(payload, 'content', 'file', 'fileName'),
    )


def _extract_file_id(payload: Mapping[str, Any]) -> str | None:
    return _first_text(
        _path_value(payload, 'content', 'fileId'),
        payload.get('fileId'),
        payload.get('mediaId'),
        _path_value(payload, 'content', 'mediaId'),
        _path_value(payload, 'file', 'fileId'),
        _path_value(payload, 'file', 'mediaId'),
        _path_value(payload, 'content', 'file', 'fileId'),
        _path_value(payload, 'content', 'file', 'mediaId'),
    )


def _resolve_channel(payload: Mapping[str, Any], *, group_id: str | None = None) -> str:
    if not _clean_text(group_id):
        return 'dingtalk_private'
    conversation_type = _clean_text(
        _first_text(
            payload.get('conversationType'),
            payload.get('conversation_type'),
            payload.get('chatType'),
            payload.get('chat_type'),
        )
    ).lower()
    if conversation_type in {'single', 'private', '1v1', 'private_chat', '1', 'one_to_one'}:
        return 'dingtalk_private'
    if conversation_type in {'group', 'chat', '2', 'group_chat', 'groupchat', 'chat_group'}:
        return 'dingtalk_group'
    return 'dingtalk_private'


def _path_value(payload: Mapping[str, Any], *path: str) -> Any:
    current: Any = payload
    for key in path:
        current = _coerce_mapping(current)
        if current is None:
            return None
        current = current.get(key)
    return current


def _coerce_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not (text.startswith('{') and text.endswith('}')):
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, Mapping):
        return parsed
    return None


def _first_text(*values: Any) -> str | None:
    for value in values:
        clean = _clean_text(value)
        if clean:
            return clean
    return None


def _clean_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value).strip()
    return ''
