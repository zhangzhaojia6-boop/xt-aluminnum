from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.config import settings
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.models.agent_communication import MultimodalEvidence
from app.services.dingtalk_energy_ingest_service import (
    DATE_KEYS,
    ingest_dingtalk_energy_file,
    resolve_dingtalk_energy_business_date,
)
from app.services.dingtalk_file_text_extractor import DingTalkFileText, extract_dingtalk_file_text
from app.services.dingtalk_service import DingTalkDownloadedFile, DingTalkService
from app.services.dingtalk_stream_event_service import NormalizedDingTalkEvent
from app.services.dingtalk_stream_event_service import normalize_dingtalk_stream_event, validate_authorized_group
from app.services.hermes_day1_evidence_service import record_day1_dingtalk_evidence


LOGGER = logging.getLogger(__name__)
EXCEL_SUFFIXES = {'.xls', '.xlsx', '.xlsm'}
SENSITIVE_RAW_METADATA_KEYS = {'downloadcode', 'download_code'}
SENSITIVE_RAW_METADATA_QUERY_KEYS = {'downloadcode', 'download_code', 'access_token', 'signature', 'sign', 'sig'}
RAW_METADATA_MAX_STRING_LENGTH = 512
RAW_METADATA_MAX_ITEMS = 25
RAW_METADATA_MAX_DEPTH = 6
RAW_METADATA_TRUNCATION_MARKER = '...[truncated]'
SECRET_PAIR_PATTERN = re.compile(
    r'(?i)\b(downloadcode|download_code|access_token|signature|sign|sig)\s*[:=]\s*["\']?[^"\'\s,&}]+'
)
URL_PATTERN = re.compile(r'https?://[^\s"\'<>]+')


def ingest_dingtalk_stream_event(
    db: Session,
    payload: Mapping[str, Any],
    *,
    dingtalk_service: DingTalkService | None = None,
) -> dict[str, Any]:
    event = normalize_dingtalk_stream_event(payload)
    try:
        validate_authorized_group(event, settings.dingtalk_authorized_group_ids)
    except ValueError as exc:
        LOGGER.warning(
            'dingtalk_stream_event_rejected reason=%s group_id_present=%s trace_id=%s',
            str(exc),
            bool(event.group_id),
            event.trace_id,
        )
        return _result(event, accepted=False, reason=str(exc))

    duplicate = _find_duplicate_evidence(db, event, file_hash=None)
    if duplicate is not None:
        return _result(event, accepted=True, duplicate=True, parse_status=_parse_status(duplicate))

    if _is_file_event(event):
        return _ingest_file_event(db, event, dingtalk_service=dingtalk_service or DingTalkService())
    return _ingest_text_event(db, event)


def _ingest_text_event(db: Session, event: NormalizedDingTalkEvent) -> dict[str, Any]:
    text = str(event.message_text or '').strip()
    parse_status = 'text_captured' if text else 'text_unavailable'
    evidence_payload = _base_evidence_payload(event, parse_status=parse_status)

    evidence = record_day1_dingtalk_evidence(
        db,
        payload=evidence_payload,
        actor=None,
        business_date=_resolve_business_date(event),
        channel=event.channel,
        group_id=event.group_id,
        trace_id=event.trace_id,
        recognized_text=text,
        confirmation_status='machine_only',
    )
    _merge_stream_payload(evidence, evidence_payload)
    _commit_evidence(db, evidence)
    return _result(
        event,
        accepted=True,
        duplicate=False,
        evidence_id=getattr(evidence, 'id', None),
        message_text=bool(text),
        parse_status=parse_status,
    )


def _ingest_file_event(
    db: Session,
    event: NormalizedDingTalkEvent,
    *,
    dingtalk_service: DingTalkService,
) -> dict[str, Any]:
    file_payload = _base_evidence_payload(event, parse_status='text_unavailable')
    downloaded: DingTalkDownloadedFile | None = None
    file_text: DingTalkFileText | None = None
    recognized_text = ''

    if not event.download_code:
        file_payload.update({'parse_status': 'download_failed', 'download_status': 'missing_download_code'})
    else:
        try:
            downloaded = dingtalk_service.download_robot_message_file(download_code=event.download_code)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                'dingtalk_stream_file_download_failed error=%s trace_id=%s',
                exc.__class__.__name__,
                event.trace_id,
            )
            file_payload.update({'parse_status': 'download_failed', 'download_status': 'download_failed'})
        else:
            file_text = extract_dingtalk_file_text(
                event.file_name or '',
                downloaded.content,
                settings.DINGTALK_FILE_TEXT_MAX_BYTES,
            )
            file_payload.update(
                {
                    'file_hash': file_text.content_hash,
                    'parse_status': file_text.status,
                    'text_extract_detail': file_text.detail,
                    'download_status': 'downloaded',
                    'download_url_host': downloaded.download_url_host,
                    'content_type': downloaded.content_type,
                    'file_size': downloaded.size,
                }
            )
            if file_text.status == 'text_captured':
                recognized_text = file_text.text

    duplicate = _find_duplicate_evidence(db, event, file_hash=file_payload.get('file_hash'))
    if duplicate is not None:
        return _result(event, accepted=True, duplicate=True, parse_status=_parse_status(duplicate))

    evidence = record_day1_dingtalk_evidence(
        db,
        payload=file_payload,
        actor=None,
        business_date=_resolve_business_date(event),
        channel=event.channel,
        group_id=event.group_id,
        trace_id=event.trace_id,
        recognized_text=recognized_text,
        confirmation_status='machine_only',
    )
    _merge_stream_payload(evidence, file_payload)
    _commit_evidence(db, evidence)

    energy_result = _maybe_ingest_energy_file(db, file_payload, evidence, event, downloaded)
    return _result(
        event,
        accepted=True,
        duplicate=False,
        evidence_id=getattr(evidence, 'id', None),
        file_text=bool(str(recognized_text or '').strip()),
        parse_status=file_payload.get('parse_status') or 'text_unavailable',
        energy_ingest=energy_result,
    )


def _maybe_ingest_energy_file(
    db: Session,
    file_payload: dict[str, Any],
    evidence: MultimodalEvidence | None,
    event: NormalizedDingTalkEvent,
    downloaded: DingTalkDownloadedFile | None,
) -> dict[str, Any] | None:
    if evidence is None or downloaded is None:
        return None
    if Path(str(event.file_name or '')).suffix.lower() not in EXCEL_SUFFIXES:
        return None

    ingest_payload = dict(file_payload)
    ingest_payload['fileContentBase64'] = base64.b64encode(downloaded.content).decode('ascii')
    try:
        return ingest_dingtalk_energy_file(db, payload=ingest_payload, evidence=evidence, trace_id=event.trace_id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        LOGGER.warning(
            'dingtalk_stream_energy_ingest_failed error=%s trace_id=%s',
            exc.__class__.__name__,
            event.trace_id,
        )
        return {'status': 'blocked', 'reason': 'energy_ingest_failed', 'error': exc.__class__.__name__}


def _base_evidence_payload(event: NormalizedDingTalkEvent, *, parse_status: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'messageId': event.message_id,
        'message_id': event.message_id,
        'msgtype': event.message_type,
        'messageType': event.message_type,
        'fileName': event.file_name,
        'file_name': event.file_name,
        'mediaId': event.file_id,
        'fileId': event.file_id,
        'file_id': event.file_id,
        'downloadCode_present': bool(event.download_code),
        'parse_status': parse_status,
        'senderStaffId': event.sender_staff_id,
        'senderUnionId': event.sender_union_id,
        'eventTime': event.event_time,
        'event_time': event.event_time,
        'messageTime': event.event_time,
        'msgCreateTime': event.event_time,
        'raw_metadata': _redacted_raw_metadata(event.raw_payload),
    }
    for key in DATE_KEYS:
        value = event.raw_payload.get(key)
        if value not in (None, ''):
            payload[key] = value
    return payload


def _find_duplicate_evidence(
    db: Session,
    event: NormalizedDingTalkEvent,
    *,
    file_hash: Any,
) -> MultimodalEvidence | None:
    rows = (
        db.query(MultimodalEvidence)
        .filter(MultimodalEvidence.evidence_type.in_(('text', 'attachment')))
        .order_by(MultimodalEvidence.id.desc())
        .limit(5000)
        .all()
    )
    for row in rows:
        payload = row.payload or {}
        if payload.get('source') != 'dingtalk':
            continue
        if payload.get('channel') != event.channel:
            continue
        if payload.get('group_id') != event.group_id:
            continue
        if payload.get('trace_id') != event.trace_id:
            continue
        if file_hash and payload.get('file_hash') != file_hash:
            continue
        return row
    return None


def _resolve_business_date(event: NormalizedDingTalkEvent):
    return resolve_dingtalk_energy_business_date(dict(event.raw_payload), file_name=event.file_name)


def _is_file_event(event: NormalizedDingTalkEvent) -> bool:
    return bool(event.file_name or event.file_id or event.download_code)


def _redacted_raw_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth >= RAW_METADATA_MAX_DEPTH:
        return RAW_METADATA_TRUNCATION_MARKER
    if isinstance(value, Mapping):
        filtered = filter_sensitive_mapping(value)
        sanitized: dict[str, Any] = {}
        kept = 0
        for raw_key, item in filtered.items():
            normalized_key = str(raw_key).strip().lower().replace('-', '_')
            if normalized_key in SENSITIVE_RAW_METADATA_KEYS:
                continue
            if kept >= RAW_METADATA_MAX_ITEMS:
                sanitized['__truncated__'] = RAW_METADATA_TRUNCATION_MARKER
                break
            sanitized[str(raw_key)] = _redacted_raw_metadata(item, depth=depth + 1)
            kept += 1
        return sanitized
    if isinstance(value, (list, tuple, set)):
        sanitized_items = [_redacted_raw_metadata(item, depth=depth + 1) for item in list(value)[:RAW_METADATA_MAX_ITEMS]]
        if len(value) > RAW_METADATA_MAX_ITEMS:
            sanitized_items.append(RAW_METADATA_TRUNCATION_MARKER)
        return sanitized_items
    if isinstance(value, str):
        return _sanitize_raw_metadata_text(value, depth=depth)
    return value


def _sanitize_raw_metadata_text(value: str, *, depth: int) -> Any:
    parsed = _parse_json_like_text(value)
    if parsed is not None:
        return _redacted_raw_metadata(parsed, depth=depth + 1)
    sanitized = redact_secret_text(value)
    sanitized = SECRET_PAIR_PATTERN.sub(lambda match: f'{match.group(1)}=<redacted>', sanitized)
    sanitized = URL_PATTERN.sub(lambda match: _sanitize_signed_url(match.group(0)), sanitized)
    return _truncate_raw_metadata_string(sanitized)


def _parse_json_like_text(value: str) -> Mapping[str, Any] | list[Any] | None:
    text = str(value or '').strip()
    if not text:
        return None
    if not ((text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']'))):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, (Mapping, list)):
        return parsed
    return None


def _sanitize_signed_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.scheme or not parts.netloc or not parts.query:
        return value
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    if not query_pairs:
        return value

    sanitized_pairs: list[str] = []
    for key, item in query_pairs:
        normalized_key = str(key).strip().lower().replace('-', '_')
        safe_key = quote(str(key), safe='')
        if normalized_key in SENSITIVE_RAW_METADATA_QUERY_KEYS:
            sanitized_pairs.append(f'{safe_key}=<redacted>')
            continue
        sanitized_pairs.append(f'{safe_key}={quote(str(item), safe="")}')

    return urlunsplit((parts.scheme, parts.netloc, parts.path, '&'.join(sanitized_pairs), parts.fragment))


def _truncate_raw_metadata_string(value: str) -> str:
    if len(value) <= RAW_METADATA_MAX_STRING_LENGTH:
        return value
    keep = max(0, RAW_METADATA_MAX_STRING_LENGTH - len(RAW_METADATA_TRUNCATION_MARKER))
    return f'{value[:keep]}{RAW_METADATA_TRUNCATION_MARKER}'


def _commit_evidence(db: Session, evidence: MultimodalEvidence | None) -> None:
    db.commit()
    if evidence is not None:
        db.refresh(evidence)


def _merge_stream_payload(evidence: MultimodalEvidence | None, stream_payload: Mapping[str, Any]) -> None:
    if evidence is None:
        return
    payload = dict(evidence.payload) if isinstance(evidence.payload, dict) else {}
    for key, value in stream_payload.items():
        if key == 'raw_metadata' or value not in (None, ''):
            payload[key] = value
    evidence.payload = payload


def _parse_status(evidence: MultimodalEvidence) -> str:
    return str((evidence.payload or {}).get('parse_status') or 'unknown')


def _result(
    event: NormalizedDingTalkEvent,
    *,
    accepted: bool,
    duplicate: bool = False,
    trace_id: str | None = None,
    message_text: bool = False,
    file_text: bool = False,
    parse_status: str = 'unknown',
    reason: str | None = None,
    evidence_id: int | None = None,
    energy_ingest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        'accepted': accepted,
        'duplicate': duplicate,
        'trace_id': trace_id or event.trace_id,
        'message_text': message_text,
        'file_text': file_text,
        'parse_status': parse_status,
    }
    if reason:
        result['reason'] = reason
    if evidence_id is not None:
        result['evidence_id'] = evidence_id
    if energy_ingest is not None:
        result['energy_ingest'] = energy_ingest
    return result
