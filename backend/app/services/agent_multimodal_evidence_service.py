from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.agent_communication import MultimodalEvidence


class MultimodalEvidenceError(RuntimeError):
    pass


SUPPORTED_EVIDENCE_TYPES = {'image', 'voice', 'attachment', 'text'}
DINGTALK_TYPE_MAP = {
    'image': 'image',
    'voice': 'voice',
    'file': 'attachment',
    'text': 'text',
}


def record_evidence(
    db: Session,
    *,
    evidence_type: str,
    file_uri: str | None,
    source_channel_id: int | None = None,
    source_user_id: int | None = None,
    event_id: int | None = None,
    recognized_text: str | None = None,
    confirmation_status: str = 'machine_only',
    payload: dict | None = None,
) -> MultimodalEvidence:
    clean_type = str(evidence_type or '').strip().lower()
    if clean_type not in SUPPORTED_EVIDENCE_TYPES:
        raise MultimodalEvidenceError('unsupported_evidence_type')

    safe_payload = dict(payload or {})
    safe_payload['metric_write_allowed'] = False
    evidence = MultimodalEvidence(
        evidence_type=clean_type,
        source_channel_id=source_channel_id,
        source_user_id=source_user_id,
        event_id=event_id,
        file_uri=file_uri,
        recognized_text=recognized_text,
        confirmation_status=confirmation_status,
        payload=safe_payload,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def record_dingtalk_media_message(
    db: Session,
    message_payload: dict,
    *,
    event_id: int | None = None,
    recognized_text: str | None = None,
) -> MultimodalEvidence:
    msg_type = str(message_payload.get('msgtype') or message_payload.get('msgType') or '').strip().lower()
    evidence_type = DINGTALK_TYPE_MAP.get(msg_type)
    if evidence_type is None:
        raise MultimodalEvidenceError('unsupported_dingtalk_message_type')

    media_id = str(message_payload.get('mediaId') or message_payload.get('media_id') or '').strip()
    msg_id = str(message_payload.get('msgId') or message_payload.get('msg_id') or '').strip()
    file_uri = f'dingtalk://media/{media_id}' if media_id else f'dingtalk://message/{msg_id or "unknown"}'
    payload = {
        'source': 'dingtalk',
        'dingtalk_msg_type': msg_type,
        'dingtalk_msg_id': msg_id or None,
        'dingtalk_media_id': media_id or None,
        'dingtalk_sender_id': message_payload.get('senderStaffId') or message_payload.get('senderId'),
        'dingtalk_conversation_id': message_payload.get('conversationId') or message_payload.get('conversation_id'),
    }
    return record_evidence(
        db,
        evidence_type=evidence_type,
        file_uri=file_uri,
        event_id=event_id,
        recognized_text=recognized_text or message_payload.get('text') or message_payload.get('content'),
        payload=payload,
    )


def mark_human_confirmed(
    db: Session,
    evidence_id: int,
    *,
    confirmer_user_id: int,
    result_payload: dict | None = None,
) -> MultimodalEvidence:
    evidence = db.get(MultimodalEvidence, int(evidence_id))
    if evidence is None:
        raise MultimodalEvidenceError('evidence_not_found')

    safe_payload = dict(evidence.payload or {})
    safe_payload['metric_write_allowed'] = False
    safe_payload['confirmed_by_user_id'] = int(confirmer_user_id)
    safe_payload['confirm_result'] = dict(result_payload or {})
    evidence.confirmation_status = 'human_confirmed'
    evidence.payload = safe_payload
    db.commit()
    db.refresh(evidence)
    return evidence


def list_event_evidence(db: Session, *, event_id: int) -> list[MultimodalEvidence]:
    return (
        db.query(MultimodalEvidence)
        .filter(MultimodalEvidence.event_id == int(event_id))
        .order_by(MultimodalEvidence.id.asc())
        .all()
    )
