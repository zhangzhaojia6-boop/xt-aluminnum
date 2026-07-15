from __future__ import annotations

import base64
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.core.active_workshops import is_active_production_workshop_name, normalize_workshop_name
from app.core.business_time import resolve_production_business_date
from app.core.redaction import redact_secret_text
from app.models.agent_communication import MultimodalEvidence
from app.services.dingtalk_energy_ingest_service import (
    DATE_KEYS,
    INLINE_FILE_KEYS,
    ingest_dingtalk_energy_file,
    resolve_dingtalk_energy_business_date,
)
from app.services.dingtalk_secret_sanitizer import (
    RAW_METADATA_MAX_ITEMS,
    RAW_METADATA_MAX_STRING_LENGTH,
    RAW_METADATA_MAX_DEPTH,
    RAW_METADATA_TRUNCATION_MARKER,
    sanitize_dingtalk_payload_for_storage,
)
from app.services.dingtalk_file_text_extractor import DingTalkFileText, extract_dingtalk_file_text
from app.services.dingtalk_service import DingTalkDownloadedFile, DingTalkService
from app.services.dingtalk_stream_event_service import NormalizedDingTalkEvent
from app.services.dingtalk_stream_event_service import normalize_dingtalk_stream_event, validate_authorized_group
from app.services.hermes_day1_evidence_service import record_day1_dingtalk_evidence


LOGGER = logging.getLogger(__name__)
EXCEL_SUFFIXES = {'.xls', '.xlsx', '.xlsm'}
INLINE_FILE_BYTES_LIMIT = 10 * 1024 * 1024


def ingest_dingtalk_stream_event(
    db: Session,
    payload: Mapping[str, Any],
    *,
    dingtalk_service: DingTalkService | None = None,
    require_authorized_group: bool = True,
    source_transport: str = 'dingtalk_stream',
    commit: bool = True,
    process_energy: bool = True,
) -> dict[str, Any]:
    if not commit and process_energy:
        raise ValueError('deferred_commit_requires_energy_processing_disabled')
    event = normalize_dingtalk_stream_event(payload)
    if require_authorized_group:
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

    duplicate = _find_duplicate_evidence(
        db,
        event,
        file_hash=None,
        source_transport=source_transport,
    )
    if duplicate is not None:
        return _result(
            event,
            accepted=True,
            duplicate=True,
            parse_status=_parse_status(duplicate),
            evidence_id=duplicate.id,
        )

    if _is_file_event(event):
        return _ingest_file_event(
            db,
            event,
            dingtalk_service=dingtalk_service or DingTalkService(),
            source_transport=source_transport,
            commit=commit,
            process_energy=process_energy,
        )
    return _ingest_text_event(db, event, source_transport=source_transport, commit=commit)


def _ingest_text_event(
    db: Session,
    event: NormalizedDingTalkEvent,
    *,
    source_transport: str,
    commit: bool,
) -> dict[str, Any]:
    text = str(event.message_text or '').strip()
    parse_status = 'text_captured' if text else 'text_unavailable'
    evidence_payload = _base_evidence_payload(
        event,
        parse_status=parse_status,
        source_transport=source_transport,
    )

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
    _commit_evidence(db, evidence, commit=commit)
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
    source_transport: str,
    commit: bool,
    process_energy: bool,
) -> dict[str, Any]:
    file_payload = _base_evidence_payload(
        event,
        parse_status='text_unavailable',
        source_transport=source_transport,
    )
    downloaded: DingTalkDownloadedFile | None = None
    file_text: DingTalkFileText | None = None
    recognized_text = ''

    inline_content = _inline_file_bytes(event.raw_payload)
    if inline_content is not None:
        downloaded = DingTalkDownloadedFile(
            download_url_host='inline-payload',
            content=inline_content,
            content_type='application/octet-stream',
            size=len(inline_content),
        )
    elif not event.download_code:
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
    if downloaded is not None:
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

    duplicate = _find_duplicate_evidence(
        db,
        event,
        file_hash=file_payload.get('file_hash'),
        source_transport=source_transport,
    )
    if duplicate is not None:
        return _result(
            event,
            accepted=True,
            duplicate=True,
            parse_status=_parse_status(duplicate),
            evidence_id=duplicate.id,
        )

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
    _commit_evidence(db, evidence, commit=commit)

    energy_result = _maybe_ingest_energy_file(db, file_payload, evidence, event, downloaded) if process_energy else None
    return _result(
        event,
        accepted=True,
        duplicate=False,
        evidence_id=getattr(evidence, 'id', None),
        file_text=bool(str(recognized_text or '').strip()),
        parse_status=file_payload.get('parse_status') or 'text_unavailable',
        energy_ingest=energy_result,
    )


def _inline_file_bytes(payload: Mapping[str, Any]) -> bytes | None:
    for key in INLINE_FILE_KEYS:
        raw = payload.get(key)
        if raw in (None, ''):
            continue
        if isinstance(raw, bytes):
            return raw if len(raw) <= INLINE_FILE_BYTES_LIMIT else None
        if not isinstance(raw, str):
            return None
        encoded = raw.strip()
        if len(encoded) > ((INLINE_FILE_BYTES_LIMIT + 2) // 3) * 4 + 16:
            return None
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return None
        return decoded if len(decoded) <= INLINE_FILE_BYTES_LIMIT else None
    return None


def _maybe_ingest_energy_file(
    db: Session,
    file_payload: dict[str, Any],
    evidence: MultimodalEvidence | None,
    event: NormalizedDingTalkEvent,
    downloaded: DingTalkDownloadedFile | None,
) -> dict[str, Any] | None:
    if evidence is None:
        return None
    if Path(str(event.file_name or '')).suffix.lower() not in EXCEL_SUFFIXES:
        return None
    if downloaded is None:
        return ingest_dingtalk_energy_file(
            db,
            payload=file_payload,
            evidence=evidence,
            trace_id=event.trace_id,
        )

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


def _base_evidence_payload(
    event: NormalizedDingTalkEvent,
    *,
    parse_status: str,
    source_transport: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'source_transport': source_transport,
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
        'senderIdentityType': event.raw_payload.get('senderIdentityType'),
        'sender_identity_type': event.raw_payload.get('sender_identity_type')
        or event.raw_payload.get('senderIdentityType'),
        'eventTime': event.event_time,
        'event_time': event.event_time,
        'messageTime': event.event_time,
        'msgCreateTime': event.event_time,
        'receivedAt': event.raw_payload.get('receivedAt') or event.raw_payload.get('received_at'),
        'received_at': event.raw_payload.get('received_at') or event.raw_payload.get('receivedAt'),
        'raw_metadata': _redacted_raw_metadata(event.raw_payload),
    }
    for key in DATE_KEYS:
        value = event.raw_payload.get(key)
        if value not in (None, ''):
            payload[key] = value
    for key in ('workshop_name', 'workshopName', 'workshop'):
        value = event.raw_payload.get(key)
        if value not in (None, ''):
            payload[key] = value
    return payload


def _find_duplicate_evidence(
    db: Session,
    event: NormalizedDingTalkEvent,
    *,
    file_hash: Any,
    source_transport: str,
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
        if payload.get('source_transport') != source_transport:
            continue
        if file_hash and payload.get('file_hash') != file_hash:
            continue
        return row
    return None


def _resolve_business_date(event: NormalizedDingTalkEvent):
    explicit_date = resolve_dingtalk_energy_business_date(
        dict(event.raw_payload),
        file_name=event.file_name,
        fallback_to_last_completed=False,
    )
    if explicit_date is not None:
        return explicit_date
    workshop_name = normalize_workshop_name(
        event.raw_payload.get('workshop_name')
        or event.raw_payload.get('workshopName')
        or event.raw_payload.get('workshop')
    )
    event_time = _parse_event_datetime(event.event_time)
    if not is_active_production_workshop_name(workshop_name) or event_time is None:
        return None
    return resolve_production_business_date(event_time, workshop_name=workshop_name)


def _parse_event_datetime(value: Any) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        numeric_value = float(text)
    except ValueError:
        numeric_value = None
    if numeric_value is not None:
        if numeric_value > 10**12:
            numeric_value /= 1000.0
        return datetime.fromtimestamp(numeric_value, tz=ZoneInfo(settings.DEFAULT_TIMEZONE))
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


def _is_file_event(event: NormalizedDingTalkEvent) -> bool:
    return bool(event.file_name or event.file_id or event.download_code)


def _redacted_raw_metadata(value: Any, *, depth: int = 0) -> Any:
    return sanitize_dingtalk_payload_for_storage(value, depth=depth)


def _commit_evidence(db: Session, evidence: MultimodalEvidence | None, *, commit: bool) -> None:
    if commit:
        db.commit()
        if evidence is not None:
            db.refresh(evidence)
        return
    db.flush()


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
