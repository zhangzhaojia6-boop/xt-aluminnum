from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from sqlalchemy.orm import Session

from app.core.redaction import redact_secret_text
from app.models.agent_communication import MultimodalEvidence
from app.models.hermes_factory_brain import HermesDingTalkSamplingRule


@dataclass(frozen=True, slots=True)
class DingTalkSamplingResult:
    matched: bool
    priority: str
    evidence_id: int | None
    rule_key: str | None


def sample_dingtalk_message(
    db: Session,
    *,
    channel_key: str,
    sender_user_id: str,
    message_text: str,
    file_name: str | None,
    message_time: datetime,
    content_type: str,
    trace_id: str,
) -> DingTalkSamplingResult:
    rule = (
        db.query(HermesDingTalkSamplingRule)
        .filter(
            HermesDingTalkSamplingRule.status == 'active',
            HermesDingTalkSamplingRule.channel_key == str(channel_key or '').strip(),
            HermesDingTalkSamplingRule.specialist_user_id == str(sender_user_id or '').strip(),
        )
        .order_by(HermesDingTalkSamplingRule.id.asc())
        .first()
    )
    if rule is None:
        return DingTalkSamplingResult(matched=False, priority='low', evidence_id=None, rule_key=None)
    if content_type not in list(rule.content_types or []):
        return DingTalkSamplingResult(matched=False, priority='low', evidence_id=None, rule_key=None)
    if not _has_time_window(rule):
        return DingTalkSamplingResult(matched=False, priority='low', evidence_id=None, rule_key=None)

    payload = {
        'trace_id': trace_id,
        'channel_key': redact_secret_text(channel_key),
        'sender_user_id': redact_secret_text(sender_user_id),
        'message_time': message_time.isoformat(),
        'content_type': content_type,
        'file_name': redact_secret_text(file_name or ''),
        'file_hash': _hash_file_name(file_name),
        'sampling_rule_key': rule.rule_key,
        'sampling_priority': rule.priority,
        'time_window': rule.time_window_payload or {},
    }
    evidence = MultimodalEvidence(
        evidence_type='dingtalk_file' if file_name else 'dingtalk_text',
        recognized_text=redact_secret_text(message_text),
        confirmation_status='specialist_sampled',
        payload=payload,
    )
    db.add(evidence)
    db.flush()
    return DingTalkSamplingResult(matched=True, priority=rule.priority, evidence_id=evidence.id, rule_key=rule.rule_key)


def _has_time_window(rule: HermesDingTalkSamplingRule) -> bool:
    payload = rule.time_window_payload or {}
    return bool(payload.get('mode')) and bool(payload.get('days'))


def _hash_file_name(file_name: str | None) -> str | None:
    clean = str(file_name or '').strip()
    if not clean:
        return None
    return sha256(clean.encode('utf-8')).hexdigest()
