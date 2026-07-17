from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Iterable, Mapping
import unicodedata

from sqlalchemy.orm import Session


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.active_workshops import is_active_production_workshop_name  # noqa: E402
from app.database import get_sessionmaker  # noqa: E402
from app.models.agent_communication import (  # noqa: E402
    ChatInboxMessage,
    DingTalkInboundReceipt,
    MultimodalEvidence,
)


ALLOWED_BUSINESS_DATE_STATUSES = {
    'command_explicit',
    'payload_explicit',
    'filename_explicit',
    'text_explicit',
    'event_time_window',
    'missing',
}
LEDGER_ENTRY_FIELDS = {
    'trace_hash',
    'message_type',
    'channel_type',
    'callback_receive_time',
    'source',
}
IMAGE_SUFFIXES = {'.bmp', '.gif', '.jpeg', '.jpg', '.png', '.webp'}
TERMINAL_RECEIPT_STATUSES = {'completed', 'completed_evidence'}
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
LEADING_DINGTALK_MENTION_RE = re.compile(r'^(?:@\S+[ \t\u3000]+)+')


def _clean(value: Any) -> str:
    return str(value or '').strip()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def normalized_text_sha256(value: str) -> str:
    normalized = unicodedata.normalize('NFKC', str(value or '')).strip()
    normalized = LEADING_DINGTALK_MENTION_RE.sub('', normalized)
    normalized = ' '.join(normalized.split())
    return _sha256(normalized)


def _contains_marker(value: Any, marker: str) -> bool:
    normalized_value = unicodedata.normalize('NFKC', str(value or ''))
    normalized_marker = unicodedata.normalize('NFKC', marker)
    return bool(normalized_marker and normalized_marker in normalized_value)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _at_or_after(value: Any, since: datetime) -> bool:
    return isinstance(value, datetime) and _as_utc(value) >= _as_utc(since)


def _load_ledger_entries(source: Any) -> tuple[list[Mapping[str, Any]], bool]:
    payload = source
    if isinstance(source, (str, Path)):
        try:
            payload = json.loads(Path(source).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return [], False
    if isinstance(payload, Mapping):
        payload = payload.get('entries')
    if not isinstance(payload, list):
        return [], False
    return [item for item in payload if isinstance(item, Mapping)], True


def _rows_by_trace(rows: Iterable[Any], trace_getter: Callable[[Any], str]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        trace_id = _clean(trace_getter(row))
        if trace_id:
            grouped[trace_id].append(row)
    return grouped


def _evidence_payload(row: MultimodalEvidence) -> dict[str, Any]:
    return dict(row.payload or {}) if isinstance(row.payload, Mapping) else {}


def _is_file_evidence(row: MultimodalEvidence) -> bool:
    payload = _evidence_payload(row)
    return row.evidence_type == 'attachment' or bool(_clean(payload.get('file_name')))


def _valid_iso_date(value: Any) -> bool:
    try:
        date.fromisoformat(_clean(value))
    except ValueError:
        return False
    return True


def _parse_iso_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(_clean(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _ledger_message_kind(value: Any) -> str:
    compact = re.sub(r'[^a-z0-9]', '', _clean(value).lower())
    if compact in {'file', 'image', 'picture', 'photo', 'attachment'}:
        return 'file'
    if compact in {'text', 'markdown', 'richtext'}:
        return 'text'
    return compact


def _ledger_channel_kind(value: Any) -> str:
    compact = re.sub(r'[^a-z0-9]', '', _clean(value).lower())
    if compact in {'group', 'groupchat', 'dingtalkgroup'}:
        return 'dingtalk_group'
    if compact in {'private', 'single', 'onetoone', 'dingtalkprivate'}:
        return 'dingtalk_private'
    return compact


def _business_date_payload_valid(payload: Mapping[str, Any]) -> bool:
    status = _clean(payload.get('business_date_status'))
    business_date = payload.get('business_date')
    if status not in ALLOWED_BUSINESS_DATE_STATUSES:
        return False
    if status == 'missing':
        return business_date in (None, '')
    if not _valid_iso_date(business_date):
        return False
    if status == 'event_time_window':
        return bool(
            _clean(payload.get('dingtalk_message_time'))
            and is_active_production_workshop_name(_clean(payload.get('workshop_name')))
        )
    return True


def _increment(counter: Counter[str], code: str, amount: int = 1) -> None:
    if amount > 0:
        counter[code] += amount


def inspect_dingtalk_stream_evidence_gate(
    db: Session,
    *,
    marker: str,
    min_text: int,
    min_files: int,
    since: datetime,
    hermes_ledger: Any,
    expected_u1_sha256: str,
    expected_u2_sha256: str,
) -> dict[str, Any]:
    clean_marker = _clean(marker)
    blockers: Counter[str] = Counter()
    if not clean_marker:
        _increment(blockers, 'MARKER_REQUIRED')

    inbox_rows = [
        row
        for row in db.query(ChatInboxMessage).order_by(ChatInboxMessage.id.asc()).all()
        if _at_or_after(row.created_at, since)
    ]
    receipt_rows = [
        row
        for row in db.query(DingTalkInboundReceipt).order_by(DingTalkInboundReceipt.id.asc()).all()
        if _at_or_after(row.created_at, since)
    ]
    evidence_rows = [
        row
        for row in db.query(MultimodalEvidence).order_by(MultimodalEvidence.id.asc()).all()
        if _at_or_after(row.created_at, since)
        and _clean(_evidence_payload(row).get('source_transport')) == 'dingtalk_stream'
    ]

    marker_traces = {
        _clean(row.trace_id)
        for row in inbox_rows
        if _contains_marker(row.text, clean_marker)
    }
    marker_traces.update(
        _clean(payload.get('trace_id'))
        for row in evidence_rows
        if _contains_marker((payload := _evidence_payload(row)).get('message_text'), clean_marker)
        or _contains_marker(payload.get('file_name'), clean_marker)
    )
    marker_traces.discard('')

    receipts_by_trace = _rows_by_trace(receipt_rows, lambda row: row.trace_id)
    inbox_by_trace = _rows_by_trace(inbox_rows, lambda row: row.trace_id)
    evidence_by_trace = _rows_by_trace(evidence_rows, lambda row: _evidence_payload(row).get('trace_id'))

    ledger_entries, ledger_available = _load_ledger_entries(hermes_ledger)
    if not ledger_available:
        _increment(blockers, 'LEDGER_UNAVAILABLE')
    ledger_by_trace_hash: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for entry in ledger_entries:
        if set(entry) != LEDGER_ENTRY_FIELDS:
            _increment(blockers, 'LEDGER_ENTRY_SCHEMA_INVALID')
            continue
        trace_hash = _clean(entry.get('trace_hash')).lower()
        if (
            SHA256_RE.fullmatch(trace_hash) is None
            or _clean(entry.get('source')) != 'stream_callback'
            or not _clean(entry.get('message_type'))
            or not _clean(entry.get('channel_type'))
            or _parse_iso_datetime(entry.get('callback_receive_time')) is None
        ):
            _increment(blockers, 'LEDGER_ENTRY_SCHEMA_INVALID')
            continue
        ledger_by_trace_hash[trace_hash].append(entry)

    candidate_evidence: list[MultimodalEvidence] = []
    correlated_trace_count = 0
    ledger_callback_count = 0
    event_time_fallback_traces: set[str] = set()
    for trace_id in sorted(marker_traces):
        receipts = receipts_by_trace.get(trace_id, [])
        inboxes = inbox_by_trace.get(trace_id, [])
        evidences = evidence_by_trace.get(trace_id, [])
        if len(receipts) != 1:
            _increment(blockers, 'TRACE_RECEIPT_COUNT_INVALID')
        if len(inboxes) != 1:
            _increment(blockers, 'TRACE_INBOX_COUNT_INVALID')
        if len(evidences) != 1:
            _increment(blockers, 'TRACE_EVIDENCE_COUNT_INVALID')
        if len(receipts) == len(inboxes) == len(evidences) == 1:
            receipt = receipts[0]
            inbox = inboxes[0]
            evidence = evidences[0]
            evidence_payload = _evidence_payload(evidence)
            correlation_valid = True
            if not _business_date_payload_valid(evidence_payload):
                _increment(blockers, 'BUSINESS_DATE_STATUS_INVALID')
                correlation_valid = False
            if _clean(receipt.status) not in TERMINAL_RECEIPT_STATUSES:
                _increment(blockers, 'RECEIPT_STATUS_INCOMPLETE')
                correlation_valid = False
            if (
                _clean(receipt.channel) != _clean(inbox.channel)
                or _clean(receipt.group_id) != _clean(inbox.group_id)
            ):
                _increment(blockers, 'TRACE_RECEIPT_SCOPE_MISMATCH')
                correlation_valid = False
            if (
                _clean(evidence_payload.get('channel')) != _clean(inbox.channel)
                or _clean(evidence_payload.get('group_id')) != _clean(inbox.group_id)
            ):
                _increment(blockers, 'TRACE_EVIDENCE_SCOPE_MISMATCH')
                correlation_valid = False
            evidence_sender = _clean(evidence_payload.get('dingtalk_sender_id')) or _clean(
                evidence_payload.get('dingtalk_sender_union_id')
            )
            if evidence_sender != _clean(inbox.sender_external_id):
                _increment(blockers, 'TRACE_SENDER_MISMATCH')
                correlation_valid = False
            if not _is_file_evidence(evidence):
                if normalized_text_sha256(evidence_payload.get('message_text')) != normalized_text_sha256(inbox.text):
                    _increment(blockers, 'TRACE_TEXT_MISMATCH')
                    correlation_valid = False
            raw_event_time = _clean(evidence_payload.get('dingtalk_message_time'))
            event_time = _parse_iso_datetime(raw_event_time)
            if event_time is None and not raw_event_time:
                received_time = _parse_iso_datetime(evidence_payload.get('dingtalk_received_at'))
                if received_time is not None:
                    event_time = received_time
                    event_time_fallback_traces.add(trace_id)
                elif isinstance(receipt.created_at, datetime):
                    event_time = receipt.created_at
                    event_time_fallback_traces.add(trace_id)
            if event_time is None:
                _increment(blockers, 'EVENT_TIME_MISSING')
                correlation_valid = False
            elif _as_utc(event_time) < _as_utc(since):
                _increment(blockers, 'EVENT_TIME_BEFORE_SINCE')
                correlation_valid = False
            inbox_transport = _clean((inbox.source_payload or {}).get('source_transport'))
            if inbox_transport != 'dingtalk_stream':
                _increment(blockers, 'INBOX_TRANSPORT_INVALID')
                correlation_valid = False
            if correlation_valid:
                correlated_trace_count += 1
                candidate_evidence.append(evidence)

        trace_hash = _sha256(trace_id)
        callbacks = ledger_by_trace_hash.get(trace_hash, [])
        if len(callbacks) != 1:
            _increment(blockers, 'LEDGER_CALLBACK_MISSING' if not callbacks else 'LEDGER_CALLBACK_COUNT_INVALID')
        else:
            callback_valid = True
            callback_time = _parse_iso_datetime(callbacks[0].get('callback_receive_time'))
            if callback_time is None or _as_utc(callback_time) < _as_utc(since):
                _increment(blockers, 'CALLBACK_TIME_BEFORE_SINCE')
                callback_valid = False
            if len(inboxes) == 1:
                expected_type = 'file' if len(evidences) == 1 and _is_file_evidence(evidences[0]) else 'text'
                callback = callbacks[0]
                if (
                    _ledger_message_kind(callback.get('message_type')) != expected_type
                    or _ledger_channel_kind(callback.get('channel_type')) != _clean(inboxes[0].channel)
                ):
                    _increment(blockers, 'LEDGER_CALLBACK_MISMATCH')
                    callback_valid = False
            if callback_valid:
                ledger_callback_count += 1

    text_evidence = [row for row in candidate_evidence if not _is_file_evidence(row)]
    file_evidence = [row for row in candidate_evidence if _is_file_evidence(row)]
    if len(text_evidence) < max(0, min_text):
        _increment(blockers, 'TEXT_MIN_NOT_MET')
    if len(file_evidence) < max(0, min_files):
        _increment(blockers, 'FILE_MIN_NOT_MET')

    candidate_inboxes = [row for trace_id in marker_traces for row in inbox_by_trace.get(trace_id, [])]
    group_trace_count = sum(_clean(row.channel) == 'dingtalk_group' for row in candidate_inboxes)
    private_trace_count = sum(_clean(row.channel) == 'dingtalk_private' for row in candidate_inboxes)
    if group_trace_count == 0:
        _increment(blockers, 'GROUP_COVERAGE_MISSING')
    if private_trace_count == 0:
        _increment(blockers, 'PRIVATE_COVERAGE_MISSING')

    file_type_counts = {'image': 0, 'xlsx': 0, 'pdf': 0}
    text_captured_file_count = 0
    for row in file_evidence:
        payload = _evidence_payload(row)
        file_name = _clean(payload.get('file_name'))
        suffix = Path(file_name).suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            file_type_counts['image'] += 1
        if suffix == '.xlsx':
            file_type_counts['xlsx'] += 1
        if suffix == '.pdf':
            file_type_counts['pdf'] += 1
        if not _contains_marker(file_name, clean_marker):
            _increment(blockers, 'FILE_MARKER_MISSING')
        if SHA256_RE.fullmatch(_clean(payload.get('file_hash')).lower()) is None:
            _increment(blockers, 'FILE_HASH_INVALID')
        if not _clean(payload.get('dingtalk_sender_id')):
            _increment(blockers, 'FILE_SENDER_MISSING')
        conversation_id = next(
            (
                _clean(payload.get(key))
                for key in ('conversation_id', 'conversationId', 'openConversationId', 'open_conversation_id', 'group_id')
                if _clean(payload.get(key))
            ),
            '',
        )
        if not conversation_id:
            _increment(blockers, 'FILE_CONVERSATION_MISSING')
        if (
            not _clean(payload.get('dingtalk_message_time'))
            and _clean(payload.get('trace_id')) not in event_time_fallback_traces
        ):
            _increment(blockers, 'FILE_EVENT_TIME_MISSING')

        parse_status = _clean(payload.get('parse_status'))
        if not parse_status:
            _increment(blockers, 'PARSE_STATUS_MISSING')
        has_file_text = bool(
            _clean(row.recognized_text)
            or _clean(payload.get('file_text'))
            or _clean(payload.get('attachment_text'))
        )
        if parse_status == 'text_captured':
            text_captured_file_count += 1
            if not has_file_text:
                _increment(blockers, 'FILE_TEXT_CAPTURE_MISSING')
        elif has_file_text:
            _increment(blockers, 'FILE_TEXT_INVENTED')

    if not all(file_type_counts.values()):
        _increment(blockers, 'FILE_TYPE_COVERAGE_MISSING')
    if text_captured_file_count < 2:
        _increment(blockers, 'FILE_TEXT_CAPTURE_MIN_NOT_MET')

    text_hashes = {
        normalized_text_sha256(row.text)
        for row in candidate_inboxes
        if len(evidence_by_trace.get(_clean(row.trace_id), [])) == 1
        and not _is_file_evidence(evidence_by_trace[_clean(row.trace_id)][0])
    }
    expected_u1 = _clean(expected_u1_sha256).lower()
    expected_u2 = _clean(expected_u2_sha256).lower()
    if SHA256_RE.fullmatch(expected_u1) is None or SHA256_RE.fullmatch(expected_u2) is None:
        _increment(blockers, 'NORMALIZATION_EXPECTED_HASH_INVALID')
    else:
        if expected_u1 == expected_u2:
            _increment(blockers, 'NORMALIZATION_EXPECTED_HASH_DUPLICATE')
        if expected_u1 not in text_hashes:
            _increment(blockers, 'NORMALIZATION_U1_MISSING')
        if expected_u2 not in text_hashes:
            _increment(blockers, 'NORMALIZATION_U2_MISSING')

    blocker_payload = [
        {'code': code, 'count': count}
        for code, count in sorted(blockers.items())
    ]
    return {
        'status': 'PASS' if not blocker_payload else 'BLOCKED',
        'blockers': blocker_payload,
        'marker_sha256': _sha256(clean_marker),
        'trace_hashes': sorted(_sha256(trace_id) for trace_id in marker_traces),
        'counts': {
            'candidate_trace_count': len(marker_traces),
            'correlated_trace_count': correlated_trace_count,
            'ledger_callback_count': ledger_callback_count,
            'text_count': len(text_evidence),
            'file_count': len(file_evidence),
            'image_file_count': file_type_counts['image'],
            'xlsx_file_count': file_type_counts['xlsx'],
            'pdf_file_count': file_type_counts['pdf'],
            'text_captured_file_count': text_captured_file_count,
            'group_trace_count': group_trace_count,
            'private_trace_count': private_trace_count,
            'normalization_u1_match_count': int(expected_u1 in text_hashes),
            'normalization_u2_match_count': int(expected_u2 in text_hashes),
            'event_time_fallback_count': len(event_time_fallback_traces),
        },
    }


def _parse_since(value: str) -> datetime:
    parsed = datetime.fromisoformat(_clean(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def main(
    argv: list[str] | None = None,
    *,
    session_factory: Callable[[], Session] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description='Check persisted DingTalk Stream acceptance evidence.')
    parser.add_argument('--marker', required=True)
    parser.add_argument('--min-text', type=int, default=10)
    parser.add_argument('--min-files', type=int, default=5)
    parser.add_argument('--since', required=True)
    parser.add_argument('--hermes-ledger', type=Path, required=True)
    parser.add_argument('--expected-u1-sha256', required=True)
    parser.add_argument('--expected-u2-sha256', required=True)
    parser.add_argument('--output-json', type=Path)
    args = parser.parse_args(argv)

    try:
        since = _parse_since(args.since)
    except ValueError:
        parser.error('--since must be an ISO-8601 datetime')

    resolved_session_factory = session_factory or get_sessionmaker()
    with resolved_session_factory() as db:
        payload = inspect_dingtalk_stream_evidence_gate(
            db,
            marker=args.marker,
            min_text=args.min_text,
            min_files=args.min_files,
            since=since,
            hermes_ledger=args.hermes_ledger,
            expected_u1_sha256=args.expected_u1_sha256,
            expected_u2_sha256=args.expected_u2_sha256,
        )

    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output_json is not None:
        args.output_json.write_text(f'{serialized}\n', encoding='utf-8')
    print(serialized)
    return 0 if payload['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
