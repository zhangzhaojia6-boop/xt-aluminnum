from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_communication import (
    AgentChannelBinding,
    AgentEvent,
    AgentOperationApproval,
    AgentOutboxMessage,
    AgentProfile,
    CommunicationChannel,
    MultimodalEvidence,
)
from app.services import agent_knowledge_service


PENDING_EVENT_STATUSES = {'pending', 'open', 'new'}
PENDING_OPERATION_STATUSES = {'pending', 'pending_confirmation', 'confirmed'}
PENDING_OUTBOX_STATUSES = {'pending', 'retrying'}


def _count(db: Session, model, *criteria) -> int:
    query = db.query(func.count(model.id))
    for item in criteria:
        query = query.filter(item)
    return int(query.scalar() or 0)


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _mask_key(value: str | None) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    if len(raw) <= 6:
        return f'{raw[:1]}***'
    return f'{raw[:4]}***{raw[-2:]}'


def _payload_flag(payload: dict | None, key: str, default: bool = False) -> bool:
    if not isinstance(payload, dict):
        return default
    if key in payload:
        return bool(payload.get(key))
    nested = payload.get('payload')
    if isinstance(nested, dict) and key in nested:
        return bool(nested.get(key))
    return default


def _binding_count_by_agent(db: Session) -> dict[int, int]:
    rows = (
        db.query(AgentChannelBinding.agent_profile_id, func.count(AgentChannelBinding.id))
        .filter(AgentChannelBinding.is_active.is_(True))
        .group_by(AgentChannelBinding.agent_profile_id)
        .all()
    )
    return {int(agent_id): int(total or 0) for agent_id, total in rows if agent_id is not None}


def _binding_count_by_channel(db: Session) -> dict[int, int]:
    rows = (
        db.query(AgentChannelBinding.channel_id, func.count(AgentChannelBinding.id))
        .filter(AgentChannelBinding.is_active.is_(True))
        .group_by(AgentChannelBinding.channel_id)
        .all()
    )
    return {int(channel_id): int(total or 0) for channel_id, total in rows if channel_id is not None}


def build_agent_management_overview(db: Session, *, limit: int = 20) -> dict[str, Any]:
    row_limit = max(1, min(int(limit or 20), 100))
    agent_bindings = _binding_count_by_agent(db)
    channel_bindings = _binding_count_by_channel(db)

    agents = (
        db.query(AgentProfile)
        .order_by(AgentProfile.is_active.desc(), AgentProfile.updated_at.desc(), AgentProfile.id.desc())
        .limit(row_limit)
        .all()
    )
    channels = (
        db.query(CommunicationChannel)
        .order_by(CommunicationChannel.is_active.desc(), CommunicationChannel.updated_at.desc(), CommunicationChannel.id.desc())
        .limit(row_limit)
        .all()
    )
    events = db.query(AgentEvent).order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc()).limit(row_limit).all()
    evidence = (
        db.query(MultimodalEvidence)
        .order_by(MultimodalEvidence.created_at.desc(), MultimodalEvidence.id.desc())
        .limit(row_limit)
        .all()
    )
    approvals = (
        db.query(AgentOperationApproval)
        .order_by(AgentOperationApproval.created_at.desc(), AgentOperationApproval.id.desc())
        .limit(row_limit)
        .all()
    )
    outbox = (
        db.query(AgentOutboxMessage)
        .order_by(AgentOutboxMessage.created_at.desc(), AgentOutboxMessage.id.desc())
        .limit(row_limit)
        .all()
    )

    return {
        'safe_mode': True,
        'summary': {
            'agent_total': _count(db, AgentProfile),
            'active_agent_total': _count(db, AgentProfile, AgentProfile.is_active.is_(True)),
            'channel_total': _count(db, CommunicationChannel),
            'active_channel_total': _count(db, CommunicationChannel, CommunicationChannel.is_active.is_(True)),
            'pending_event_total': _count(db, AgentEvent, AgentEvent.status.in_(PENDING_EVENT_STATUSES)),
            'evidence_total': _count(db, MultimodalEvidence),
            'pending_operation_total': _count(
                db,
                AgentOperationApproval,
                AgentOperationApproval.status.in_(PENDING_OPERATION_STATUSES),
            ),
            'outbox_pending_total': _count(db, AgentOutboxMessage, AgentOutboxMessage.status.in_(PENDING_OUTBOX_STATUSES)),
            'knowledge_entry_total': len(agent_knowledge_service.list_knowledge_entries()),
        },
        'agents': [
            {
                'id': item.id,
                'code': item.code,
                'name': item.name,
                'agent_type': item.agent_type,
                'scope_type': item.scope_type,
                'workshop_id': item.workshop_id,
                'team_id': item.team_id,
                'is_active': item.is_active,
                'binding_total': agent_bindings.get(item.id, 0),
                'updated_at': _iso(item.updated_at),
            }
            for item in agents
        ],
        'channels': [
            {
                'id': item.id,
                'channel_type': item.channel_type,
                'channel_key_masked': _mask_key(item.channel_key),
                'name': item.name,
                'target_type': item.target_type,
                'target_key': item.target_key,
                'workshop_id': item.workshop_id,
                'team_id': item.team_id,
                'dry_run': item.dry_run,
                'is_active': item.is_active,
                'binding_total': channel_bindings.get(item.id, 0),
                'updated_at': _iso(item.updated_at),
            }
            for item in channels
        ],
        'events': [
            {
                'id': item.id,
                'event_type': item.event_type,
                'severity': item.severity,
                'status': item.status,
                'scope_type': item.scope_type,
                'workshop_id': item.workshop_id,
                'team_id': item.team_id,
                'source_type': item.source_type,
                'source_ref': item.source_ref,
                'business_date': _iso(item.business_date),
                'occurred_at': _iso(item.occurred_at),
                'created_at': _iso(item.created_at),
                'summary': (item.payload or {}).get('summary') if isinstance(item.payload, dict) else None,
            }
            for item in events
        ],
        'evidence': [
            {
                'id': item.id,
                'evidence_type': item.evidence_type,
                'event_id': item.event_id,
                'file_uri': item.file_uri,
                'recognized_text': item.recognized_text,
                'confirmation_status': item.confirmation_status,
                'metric_write_allowed': _payload_flag(item.payload, 'metric_write_allowed', False),
                'created_at': _iso(item.created_at),
            }
            for item in evidence
        ],
        'operation_approvals': [
            {
                'id': item.id,
                'operation_type': item.operation_type,
                'status': item.status,
                'requester_user_id': item.requester_user_id,
                'approver_user_id': item.approver_user_id,
                'channel_id': item.channel_id,
                'trace_id': item.trace_id,
                'metric_write_allowed': _payload_flag(item.preview_payload, 'metric_write_allowed', False),
                'report_publish_allowed': _payload_flag(item.preview_payload, 'report_publish_allowed', False),
                'actual_write': _payload_flag(item.result_payload, 'actual_write', False),
                'execution_status': (item.result_payload or {}).get('execution_status') if isinstance(item.result_payload, dict) else None,
                'created_at': _iso(item.created_at),
                'updated_at': _iso(item.updated_at),
            }
            for item in approvals
        ],
        'outbox': [
            {
                'id': item.id,
                'dispatch_key': item.dispatch_key,
                'agent_profile_id': item.agent_profile_id,
                'channel_id': item.channel_id,
                'event_id': item.event_id,
                'status': item.status,
                'message_type': item.message_type,
                'title': item.title,
                'business_date': _iso(item.business_date),
                'source_summary': item.source_summary,
                'trace_id': item.trace_id,
                'attempts': item.attempts,
                'last_error': item.last_error,
                'next_retry_at': _iso(item.next_retry_at),
                'sent_at': _iso(item.sent_at),
                'created_at': _iso(item.created_at),
            }
            for item in outbox
        ],
        'knowledge_entries': agent_knowledge_service.list_knowledge_entries()[:row_limit],
    }
