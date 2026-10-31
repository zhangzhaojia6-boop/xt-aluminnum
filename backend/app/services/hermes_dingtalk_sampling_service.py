from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.active_workshops import is_active_production_workshop_name, normalize_workshop_name
from app.core.business_time import local_now, resolve_production_business_date
from app.core.redaction import redact_secret_text
from app.models.agent_communication import MultimodalEvidence
from app.models.hermes_factory_brain import HermesDingTalkSamplingRule
from app.services.dingtalk_verified_fact_extractor import (
    extract_verified_file_fact_updates,
    extract_verified_text_fact_updates,
)

REGISTERED_FILE_MODE = 'registered_file'
REGISTERED_MESSAGE_MODE = 'registered_message'


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

    time_window = rule.time_window_payload or {}
    workshop_name = normalize_workshop_name(time_window.get('workshop_name') or time_window.get('workshop'))
    if not is_active_production_workshop_name(workshop_name):
        workshop_name = ''
    clean_message_text = str(message_text or '').strip()
    payload = {
        'source': 'dingtalk',
        'trace_id': trace_id,
        'business_date': (
            resolve_production_business_date(message_time, workshop_name=workshop_name).isoformat()
            if workshop_name
            else None
        ),
        'workshop_name': workshop_name or None,
        'parse_status': 'text_captured' if clean_message_text else 'text_unavailable',
        'group_id': redact_secret_text(channel_key),
        'conversation_id': redact_secret_text(channel_key),
        'dingtalk_sender_id': redact_secret_text(sender_user_id),
        'event_time': message_time.isoformat(),
        'channel_key': redact_secret_text(channel_key),
        'sender_user_id': redact_secret_text(sender_user_id),
        'message_time': message_time.isoformat(),
        'content_type': content_type,
        'file_name': redact_secret_text(file_name or ''),
        'file_hash': _hash_file_name(file_name),
        'sampling_rule_key': rule.rule_key,
        'sampling_priority': rule.priority,
        'time_window': time_window,
        'file_text' if file_name else 'message_text': redact_secret_text(clean_message_text),
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


def adopt_registered_file_evidence(
    db: Session,
    *,
    evidence_id: int,
    file_name: str,
    content: bytes,
) -> str | None:
    evidence = db.get(MultimodalEvidence, int(evidence_id))
    if evidence is None or evidence.confirmation_status != 'machine_only':
        return None
    payload = dict(evidence.payload or {})
    if payload.get('parse_status') != 'text_captured':
        return None
    rule = _registered_rule(
        db,
        payload=payload,
        mode=REGISTERED_FILE_MODE,
        content_type='file',
        pattern_key='file_name_pattern',
        subject=file_name,
    )
    if rule is None:
        return None
    business_date = _workbook_modified_date(content)
    if business_date is None:
        return None
    fact_updates = extract_verified_file_fact_updates(
        file_name=file_name,
        content=content,
        business_date=business_date,
        file_sha256=sha256(content).hexdigest(),
    )
    if not fact_updates:
        return None
    payload.update(
        {
            'business_date': business_date.isoformat(),
            'fact_updates': fact_updates,
            'sampling_rule_key': rule.rule_key,
            'sampling_priority': rule.priority,
        }
    )
    evidence.payload = payload
    evidence.confirmation_status = 'specialist_sampled'
    db.flush()
    return rule.rule_key


def adopt_registered_message_evidence(db: Session, *, evidence_id: int) -> str | None:
    evidence = db.get(MultimodalEvidence, int(evidence_id))
    if evidence is None or evidence.confirmation_status != 'machine_only':
        return None
    payload = dict(evidence.payload or {})
    text = str(payload.get('message_text') or '')
    if payload.get('parse_status') != 'text_captured' or not text or payload.get('superseded_by_evidence_id'):
        return None
    rule = _registered_rule(
        db,
        payload=payload,
        mode=REGISTERED_MESSAGE_MODE,
        content_type='text',
        pattern_key='message_pattern',
        subject=text,
    )
    if rule is None:
        return None
    message_time = _event_time(payload)
    if message_time is None:
        return None
    business_date = resolve_production_business_date(message_time)
    fact_updates = extract_verified_text_fact_updates(
        text=text,
        business_date=business_date,
        content_sha256=sha256(text.encode('utf-8')).hexdigest(),
    )
    if not fact_updates:
        return None

    same_day = [
        other
        for other in db.query(MultimodalEvidence).filter(MultimodalEvidence.confirmation_status == 'specialist_sampled').all()
        if other.id != evidence.id
        and (other.payload or {}).get('sampling_rule_key') == rule.rule_key
        and (other.payload or {}).get('business_date') == business_date.isoformat()
    ]
    later = [other for other in same_day if (_event_time(other.payload or {}) or message_time) > message_time]
    if later:
        evidence.payload = {**payload, 'superseded_by_evidence_id': later[0].id}
        db.flush()
        return None
    for earlier in same_day:
        earlier_payload = dict(earlier.payload or {})
        earlier_payload['superseded_fact_updates'] = earlier_payload.pop('fact_updates', None)
        earlier_payload['superseded_by_evidence_id'] = evidence.id
        earlier.payload = earlier_payload
        earlier.confirmation_status = 'machine_only'

    payload.update(
        {
            'business_date': business_date.isoformat(),
            'fact_updates': fact_updates,
            'sampling_rule_key': rule.rule_key,
            'sampling_priority': rule.priority,
        }
    )
    evidence.payload = payload
    evidence.confirmation_status = 'specialist_sampled'
    db.flush()
    return rule.rule_key


def _registered_rule(
    db: Session,
    *,
    payload: dict,
    mode: str,
    content_type: str,
    pattern_key: str,
    subject: str,
) -> HermesDingTalkSamplingRule | None:
    rules = (
        db.query(HermesDingTalkSamplingRule)
        .filter(
            HermesDingTalkSamplingRule.status == 'active',
            HermesDingTalkSamplingRule.channel_key == str(payload.get('group_id') or '').strip(),
            HermesDingTalkSamplingRule.specialist_user_id
            == str(payload.get('dingtalk_sender_id') or payload.get('senderStaffId') or '').strip(),
        )
        .order_by(HermesDingTalkSamplingRule.id.asc())
        .all()
    )
    for rule in rules:
        window = rule.time_window_payload or {}
        pattern = str(window.get(pattern_key) or '').strip()
        if (
            window.get('mode') == mode
            and content_type in list(rule.content_types or [])
            and pattern
            and pattern in subject
        ):
            return rule
    return None


def _event_time(payload: dict) -> datetime | None:
    try:
        return local_now(datetime.fromisoformat(str(payload.get('event_time') or '').strip()))
    except ValueError:
        return None


def _workbook_modified_date(content: bytes) -> date | None:
    try:
        modified = load_workbook(BytesIO(content), read_only=True).properties.modified
    except Exception:  # noqa: BLE001
        return None
    return modified.date() if isinstance(modified, datetime) else None


def _has_time_window(rule: HermesDingTalkSamplingRule) -> bool:
    payload = rule.time_window_payload or {}
    return bool(payload.get('mode')) and bool(payload.get('days'))


def _hash_file_name(file_name: str | None) -> str | None:
    clean = str(file_name or '').strip()
    if not clean:
        return None
    return sha256(clean.encode('utf-8')).hexdigest()
