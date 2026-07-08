from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from typing import Any

from app.core.redaction import redact_secret_text
from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.models.agent_communication import MultimodalEvidence
from app.models.system import User
from app.services.agent_multimodal_evidence_service import record_evidence


class Day1EvidenceError(RuntimeError):
    pass


FACT_KEYWORDS = ('日报', '产量', '每日产量', '库存', '发货', '入库', '在制', '电耗', '气耗', '成品率', '成本')
EXPLANATION_KEYWORDS = ('异常', '停机', '原因', '影响', '维修', '换辊', '故障')
INSTRUCTION_KEYWORDS = ('补录', '重发', '以这个为准', '改成', '修正', '替换')
SAFE_RECOGNIZED_TEXT_LIMIT = 120
FULL_TEXT_PAYLOAD_LIMIT = 50000


@dataclass(frozen=True, slots=True)
class Day1EvidenceClassification:
    evidence_kind: str
    evidence_grade: str
    include_in_daily_sample: bool
    matched_keywords: list[str]


def classify_dingtalk_evidence(text: str, *, file_name: str | None = None) -> Day1EvidenceClassification:
    clean_file_name = str(file_name or '').strip()
    haystack = f'{clean_file_name} {str(text or "")}'
    matched_keywords = [
        keyword
        for keyword in (*FACT_KEYWORDS, *EXPLANATION_KEYWORDS, *INSTRUCTION_KEYWORDS)
        if keyword in haystack
    ]

    if any(keyword in haystack for keyword in INSTRUCTION_KEYWORDS):
        return Day1EvidenceClassification('instruction', 'high', True, matched_keywords)
    if any(keyword in haystack for keyword in EXPLANATION_KEYWORDS):
        return Day1EvidenceClassification('explanation', 'medium', True, matched_keywords)
    if any(keyword in haystack for keyword in FACT_KEYWORDS):
        return Day1EvidenceClassification('fact', 'high', True, matched_keywords)
    if clean_file_name:
        return Day1EvidenceClassification('fact', 'medium', True, matched_keywords)
    return Day1EvidenceClassification('noise', 'low', False, matched_keywords)


def _clean_payload_text(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            clean = str(value).strip()
            if clean:
                return clean
    return None


def _build_safe_recognized_text(recognized_text: str) -> tuple[str | None, dict[str, Any]]:
    clean_text = str(recognized_text or '').strip()
    if not clean_text:
        return None, {
            'recognized_text_hash': None,
            'recognized_text_chars': 0,
            'recognized_text_truncated': False,
        }

    redacted_text = ' '.join(redact_secret_text(clean_text).split())
    truncated = len(clean_text) > SAFE_RECOGNIZED_TEXT_LIMIT or len(redacted_text) > SAFE_RECOGNIZED_TEXT_LIMIT
    snippet = redacted_text[:SAFE_RECOGNIZED_TEXT_LIMIT].rstrip()
    if truncated:
        snippet = f'{snippet}...'
    return snippet, {
        'recognized_text_hash': hashlib.sha1(clean_text.encode('utf-8')).hexdigest(),
        'recognized_text_chars': len(clean_text),
        'recognized_text_truncated': truncated,
    }


def _build_fact_text_payload(recognized_text: str, *, is_attachment: bool) -> dict[str, Any]:
    clean_text = str(recognized_text or '').strip()
    if not clean_text:
        return {}
    redacted_text = redact_secret_text(clean_text)
    if len(redacted_text) > FULL_TEXT_PAYLOAD_LIMIT:
        redacted_text = redacted_text[:FULL_TEXT_PAYLOAD_LIMIT].rstrip()
    return {'file_text' if is_attachment else 'message_text': redacted_text}


def record_day1_dingtalk_evidence(
    db: Session,
    *,
    payload: dict[str, Any],
    actor: User | None,
    business_date: date | None,
    channel: str,
    group_id: str | None,
    trace_id: str,
    recognized_text: str,
) -> MultimodalEvidence | None:
    file_name = _clean_payload_text(payload, 'fileName', 'file_name')
    raw_file_id = _clean_payload_text(payload, 'mediaId', 'fileId', 'file_id')

    classification = classify_dingtalk_evidence(recognized_text, file_name=file_name)

    file_hash = hashlib.sha1(raw_file_id.encode('utf-8')).hexdigest() if raw_file_id else None
    evidence_type = 'attachment' if file_name or raw_file_id else 'text'
    is_attachment = evidence_type == 'attachment'
    parse_status = 'text_captured' if str(recognized_text or '').strip() else 'text_unavailable'
    safe_recognized_text, recognized_text_metadata = _build_safe_recognized_text(recognized_text)
    evidence_payload = filter_sensitive_mapping(
        {
            'source': 'dingtalk',
            'day1_super_brain': True,
            'channel': channel,
            'group_id': group_id,
            'trace_id': trace_id,
            'business_date': business_date.isoformat() if business_date else None,
            'file_name': file_name,
            'file_hash': file_hash,
            'parse_status': parse_status,
            'evidence_kind': classification.evidence_kind,
            'evidence_grade': classification.evidence_grade,
            'include_in_daily_sample': classification.include_in_daily_sample,
            'matched_keywords': classification.matched_keywords,
            **recognized_text_metadata,
            **_build_fact_text_payload(recognized_text, is_attachment=is_attachment),
            'dingtalk_sender_id': _clean_payload_text(
                payload,
                'senderStaffId',
                'senderId',
                'senderUserId',
                'senderUnionId',
            ),
            'dingtalk_sender_union_id': _clean_payload_text(payload, 'senderUnionId'),
            'dingtalk_received_at': _clean_payload_text(payload, 'receivedAt', 'received_at'),
            'dingtalk_message_time': _clean_payload_text(
                payload,
                'messageTime',
                'msgCreateTime',
                'createTime',
            ),
        }
    )

    return record_evidence(
        db,
        evidence_type=evidence_type,
        file_uri=f'dingtalk://media/{raw_file_id}' if raw_file_id else None,
        source_user_id=getattr(actor, 'id', None) if actor is not None else None,
        recognized_text=safe_recognized_text,
        confirmation_status='machine_only',
        payload=evidence_payload,
        commit=False,
    )
