from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentEvent,
    AgentOutboxMessage,
    AgentProfile,
    CommunicationChannel,
)
from app.services import agent_communication_service

AGENT_CODE = 'hermes_gateway'
CHANNEL_TYPE = 'dingtalk_work_notice'
DEDUP_WINDOW_MINUTES = 30


class HermesOutboundError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HermesOutboundOutcome:
    status: str
    event_id: int | None
    outbox_message_id: int
    duplicate: bool


def relay_proactive_message(
    db: Session,
    *,
    target_user_id: str,
    content: str,
    title: str = '鑫泰铝业智能大脑',
    trace_id: str | None = None,
    dedupe_key: str | None = None,
    source_ref: str | None = None,
    sender=None,
) -> HermesOutboundOutcome:
    clean_target = _required_text(target_user_id, 'target_user_id_required', max_length=128)
    clean_content = _required_text(content, 'content_required', max_length=20_000)
    clean_title = _required_text(title, 'title_required', max_length=128)
    clean_trace_id = _optional_text(trace_id, 'trace_id_too_long', max_length=128)
    clean_source_ref = _optional_text(source_ref, 'source_ref_too_long', max_length=128)

    content_digest = hashlib.sha256(f'{clean_target}\x1f{clean_content}'.encode()).hexdigest()
    clean_dedupe_key = _optional_text(dedupe_key, 'dedupe_key_too_long', max_length=160)
    clean_dedupe_key = clean_dedupe_key or f'hermes-outbound:{content_digest}'
    clean_trace_id = clean_trace_id or f'hermes-outbound:{content_digest}'

    agent, channel = _ensure_outbound_infrastructure(db, target_user_id=clean_target)
    existing = (
        db.query(AgentOutboxMessage)
        .filter(
            AgentOutboxMessage.agent_profile_id == agent.id,
            AgentOutboxMessage.channel_id == channel.id,
            AgentOutboxMessage.dedupe_key == clean_dedupe_key,
            AgentOutboxMessage.status.in_({'pending', 'retrying', 'sent', 'dry_run'}),
            AgentOutboxMessage.dedupe_expires_at.is_not(None),
            AgentOutboxMessage.dedupe_expires_at > datetime.now(timezone.utc).replace(tzinfo=None),
        )
        .order_by(AgentOutboxMessage.id.desc())
        .first()
    )
    if existing is not None:
        return HermesOutboundOutcome(
            status=existing.status,
            event_id=existing.event_id,
            outbox_message_id=existing.id,
            duplicate=True,
        )

    event = AgentEvent(
        event_type='hermes_proactive_message',
        severity='info',
        status='queued',
        scope_type='factory',
        source_type='hermes_gateway',
        source_ref=clean_source_ref or content_digest[:32],
        payload={
            'trace_id': clean_trace_id,
            'target_hash': hashlib.sha256(clean_target.encode('utf-8')).hexdigest(),
            'delivery_channel': CHANNEL_TYPE,
        },
    )
    db.add(event)
    db.flush()

    message = agent_communication_service.queue_bound_message(
        db,
        agent_code=agent.code,
        channel_key=channel.channel_key,
        channel_type=channel.channel_type,
        title=clean_title,
        content=clean_content,
        source_summary='hermes_gateway_proactive_outbound',
        trace_id=clean_trace_id,
        event_id=event.id,
        payload={'transport': 'hermes_gateway', 'source_ref': clean_source_ref},
        dedupe_key=clean_dedupe_key,
        dedupe_window_minutes=DEDUP_WINDOW_MINUTES,
        commit=False,
    )
    if message.event_id != event.id:
        event.status = 'suppressed'
        event.payload = {
            **dict(event.payload or {}),
            'delivery_status': message.status,
            'outbox_message_id': message.id,
            'duplicate': True,
        }
        db.commit()
        return HermesOutboundOutcome(
            status=message.status,
            event_id=event.id,
            outbox_message_id=message.id,
            duplicate=True,
        )
    outcome = agent_communication_service.dispatch_outbox_message(
        db,
        message.id,
        sender=sender,
    )
    event.status = 'completed' if outcome.status == 'sent' else outcome.status
    event.payload = {
        **dict(event.payload or {}),
        'delivery_status': outcome.status,
        'outbox_message_id': message.id,
    }
    db.commit()
    return HermesOutboundOutcome(
        status=outcome.status,
        event_id=event.id,
        outbox_message_id=message.id,
        duplicate=False,
    )


def _ensure_outbound_infrastructure(
    db: Session,
    *,
    target_user_id: str,
) -> tuple[AgentProfile, CommunicationChannel]:
    agent = db.query(AgentProfile).filter(AgentProfile.code == AGENT_CODE).one_or_none()
    if agent is None:
        agent = AgentProfile(
            code=AGENT_CODE,
            name='鑫泰铝业智能大脑',
            agent_type='factory_brain',
            scope_type='factory',
        )
        db.add(agent)
    agent.name = '鑫泰铝业智能大脑'
    agent.agent_type = 'factory_brain'
    agent.scope_type = 'factory'
    agent.is_active = True
    agent.config_payload = {
        **dict(agent.config_payload or {}),
        'delivery': 'audited_outbox',
        'direct_dingtalk_send': False,
    }
    db.flush()

    target_hash = hashlib.sha256(target_user_id.encode('utf-8')).hexdigest()
    channel_key = f'hermes-work-notice:{target_hash[:32]}'
    channel = (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_type == CHANNEL_TYPE,
            CommunicationChannel.channel_key == channel_key,
        )
        .one_or_none()
    )
    if channel is None:
        channel = CommunicationChannel(
            channel_type=CHANNEL_TYPE,
            channel_key=channel_key,
            name='Hermes 主动工作通知',
            target_type='user',
        )
        db.add(channel)
    channel.name = 'Hermes 主动工作通知'
    channel.target_type = 'user'
    channel.target_key = target_user_id
    channel.dry_run = bool(settings.DINGTALK_NOTIFY_DRY_RUN)
    channel.is_active = True
    channel.metadata_payload = {
        'managed_by': 'hermes_outbound_service',
        'delivery': 'proactive_user_message',
        'delivery_mode': 'robot_direct_with_work_notice_fallback',
        'target_hash': target_hash,
    }
    db.flush()

    binding = (
        db.query(AgentChannelBinding)
        .filter(
            AgentChannelBinding.agent_profile_id == agent.id,
            AgentChannelBinding.channel_id == channel.id,
        )
        .one_or_none()
    )
    if binding is None:
        binding = AgentChannelBinding(
            agent_profile_id=agent.id,
            channel_id=channel.id,
            min_severity='info',
        )
        db.add(binding)
    binding.is_active = True
    binding.min_severity = 'info'
    db.flush()
    return agent, channel


def _required_text(value: str | None, error: str, *, max_length: int) -> str:
    cleaned = str(value or '').strip()
    if not cleaned:
        raise HermesOutboundError(error)
    if len(cleaned) > max_length:
        raise HermesOutboundError(error.replace('_required', '_too_long'))
    return cleaned


def _optional_text(value: str | None, error: str, *, max_length: int) -> str:
    cleaned = str(value or '').strip()
    if len(cleaned) > max_length:
        raise HermesOutboundError(error)
    return cleaned
