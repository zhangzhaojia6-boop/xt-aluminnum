from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.agent_communication import (
    AgentChannelBinding,
    AgentOutboxMessage,
    AgentProfile,
    AgentRateLimit,
    CommunicationChannel,
    ExternalMessageLog,
)
from app.services import dingtalk_service


class AgentCommunicationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    status: str
    detail: str
    outbox_message_id: int


@dataclass(frozen=True, slots=True)
class DryRunSmokeOutcome:
    status: str
    detail: str
    outbox_message_id: int
    channel_id: int
    channel_type: str
    channel_key: str
    channel_name: str
    log_total: int


@dataclass(frozen=True, slots=True)
class RateLimitOutcome:
    allowed: bool
    detail: str
    hit_count: int


@dataclass(frozen=True, slots=True)
class ProviderSendResult:
    detail: str
    provider_message_id: str | None = None
    response_payload: dict | None = None


MAX_DISPATCH_ATTEMPTS = 3
RETRY_DELAY_MINUTES = 5
DEDUP_WINDOW_MINUTES = 30


def _clean(value: str | None) -> str:
    return str(value or '').strip()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _commit_refresh(db: Session, model):
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def register_agent(
    db: Session,
    *,
    code: str,
    name: str,
    agent_type: str = 'reporting',
    scope_type: str = 'factory',
    workshop_id: int | None = None,
    team_id: int | None = None,
    config_payload: dict | None = None,
) -> AgentProfile:
    agent_code = _clean(code)
    if not agent_code:
        raise AgentCommunicationError('agent_code_required')

    agent = db.query(AgentProfile).filter(AgentProfile.code == agent_code).first()
    if agent is None:
        agent = AgentProfile(code=agent_code, name=name, agent_type=agent_type, scope_type=scope_type)

    agent.name = name
    agent.agent_type = agent_type
    agent.scope_type = scope_type
    agent.workshop_id = workshop_id
    agent.team_id = team_id
    agent.config_payload = config_payload
    agent.is_active = True
    return _commit_refresh(db, agent)


def register_channel(
    db: Session,
    *,
    channel_type: str,
    channel_key: str,
    name: str,
    target_type: str,
    target_key: str | None = None,
    workshop_id: int | None = None,
    team_id: int | None = None,
    dry_run: bool = True,
    secret_ref: str | None = None,
    metadata_payload: dict | None = None,
) -> CommunicationChannel:
    clean_type = _clean(channel_type)
    clean_key = _clean(channel_key)
    if not clean_type or not clean_key:
        raise AgentCommunicationError('channel_type_and_key_required')

    channel = (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_type == clean_type,
            CommunicationChannel.channel_key == clean_key,
        )
        .first()
    )
    if channel is None:
        channel = CommunicationChannel(channel_type=clean_type, channel_key=clean_key, name=name, target_type=target_type)

    channel.name = name
    channel.target_type = target_type
    channel.target_key = target_key
    channel.workshop_id = workshop_id
    channel.team_id = team_id
    channel.dry_run = bool(dry_run)
    channel.secret_ref = secret_ref
    channel.metadata_payload = metadata_payload
    channel.is_active = True
    return _commit_refresh(db, channel)


def bind_agent_to_channel(
    db: Session,
    *,
    agent_code: str,
    channel_key: str,
    channel_type: str = 'dingtalk_group',
    min_severity: str = 'info',
) -> AgentChannelBinding:
    agent = _get_active_agent(db, agent_code)
    channel = _get_active_channel(db, channel_key=channel_key, channel_type=channel_type)

    binding = (
        db.query(AgentChannelBinding)
        .filter(
            AgentChannelBinding.agent_profile_id == agent.id,
            AgentChannelBinding.channel_id == channel.id,
        )
        .first()
    )
    if binding is None:
        binding = AgentChannelBinding(agent_profile_id=agent.id, channel_id=channel.id)

    binding.is_active = True
    binding.min_severity = min_severity
    return _commit_refresh(db, binding)


def queue_bound_message(
    db: Session,
    *,
    agent_code: str,
    channel_key: str,
    title: str,
    content: str,
    channel_type: str = 'dingtalk_group',
    business_date=None,
    source_summary: str | None = None,
    trace_id: str | None = None,
    event_id: int | None = None,
    payload: dict | None = None,
    dedupe_key: str | None = None,
    dedupe_window_minutes: int = DEDUP_WINDOW_MINUTES,
    now: datetime | None = None,
) -> AgentOutboxMessage:
    agent = _get_active_agent(db, agent_code)
    channel = _get_active_channel(db, channel_key=channel_key, channel_type=channel_type)
    binding = (
        db.query(AgentChannelBinding)
        .filter(
            AgentChannelBinding.agent_profile_id == agent.id,
            AgentChannelBinding.channel_id == channel.id,
            AgentChannelBinding.is_active.is_(True),
        )
        .first()
    )
    if binding is None:
        raise AgentCommunicationError('agent_channel_not_bound')

    clean_dedupe_key = _clean(dedupe_key) or None
    now_value = _naive_utc(now or _utcnow())
    dedupe_expires_at = None
    if clean_dedupe_key:
        existing = (
            db.query(AgentOutboxMessage)
            .filter(
                AgentOutboxMessage.agent_profile_id == agent.id,
                AgentOutboxMessage.channel_id == channel.id,
                AgentOutboxMessage.dedupe_key == clean_dedupe_key,
                AgentOutboxMessage.dedupe_expires_at.is_not(None),
                AgentOutboxMessage.dedupe_expires_at > now_value,
            )
            .order_by(AgentOutboxMessage.id.desc())
            .first()
        )
        if existing is not None:
            return existing
        dedupe_expires_at = now_value + timedelta(minutes=max(1, int(dedupe_window_minutes or DEDUP_WINDOW_MINUTES)))

    message = AgentOutboxMessage(
        dispatch_key=f'agent:{agent.code}:{channel.channel_type}:{channel.id}:{uuid4().hex}',
        agent_profile_id=agent.id,
        channel_id=channel.id,
        status='pending',
        message_type='markdown',
        title=title,
        content=content,
        business_date=business_date,
        source_summary=source_summary,
        trace_id=trace_id or uuid4().hex,
        event_id=event_id,
        payload=payload,
        dedupe_key=clean_dedupe_key,
        dedupe_expires_at=dedupe_expires_at,
    )
    return _commit_refresh(db, message)


def dispatch_outbox_message(
    db: Session,
    outbox_message_id: int,
    *,
    sender=None,
) -> DispatchOutcome:
    message = db.get(AgentOutboxMessage, int(outbox_message_id))
    if message is None:
        raise AgentCommunicationError('outbox_message_not_found')
    if message.status == 'dead_letter':
        return DispatchOutcome(status='dead_letter', detail=message.last_error or 'dead_letter_no_retry', outbox_message_id=message.id)
    if (
        message.status == 'retrying'
        and message.next_retry_at is not None
        and _naive_utc(message.next_retry_at) > _naive_utc(_utcnow())
    ):
        return DispatchOutcome(status='retrying', detail='retry_not_due', outbox_message_id=message.id)
    channel = db.get(CommunicationChannel, message.channel_id) if message.channel_id else None
    if channel is None or not channel.is_active:
        return _mark_retry_or_dead_letter(db, message, channel, 'channel_not_available')

    if channel.dry_run:
        message.status = 'dry_run'
        message.attempts += 1
        message.next_retry_at = None
        _write_external_log(
            db,
            message=message,
            channel=channel,
            status='dry_run',
            detail='dry-run only, message not sent',
        )
        db.commit()
        db.refresh(message)
        return DispatchOutcome(status='dry_run', detail='dry-run only, message not sent', outbox_message_id=message.id)

    send = sender or _default_sender(channel)
    try:
        ok, raw_detail = send(channel.channel_key, _build_dingtalk_markdown_payload(message))
        send_result = _normalize_provider_send_result(raw_detail)
    except Exception as exc:  # noqa: BLE001
        ok = False
        send_result = ProviderSendResult(detail=str(exc) or 'send_failed')

    if ok:
        message.attempts += 1
        message.status = 'sent'
        message.sent_at = _utcnow()
        message.next_retry_at = None
        _write_external_log(
            db,
            message=message,
            channel=channel,
            status=message.status,
            detail=send_result.detail,
            provider_message_id=send_result.provider_message_id,
            response_payload=send_result.response_payload,
        )
        db.commit()
        db.refresh(message)
        return DispatchOutcome(status=message.status, detail=send_result.detail, outbox_message_id=message.id)
    return _mark_retry_or_dead_letter(
        db,
        message,
        channel,
        send_result.detail,
        provider_message_id=send_result.provider_message_id,
        response_payload=send_result.response_payload,
    )


def dispatch_due_outbox_messages(
    db: Session,
    *,
    limit: int = 50,
    sender=None,
    now: datetime | None = None,
) -> list[DispatchOutcome]:
    now_value = _naive_utc(now or _utcnow())
    row_limit = min(100, max(1, int(limit or 50)))
    due_retry_filter = (
        (AgentOutboxMessage.status == 'retrying')
        & (
            AgentOutboxMessage.next_retry_at.is_(None)
            | (AgentOutboxMessage.next_retry_at <= now_value)
        )
    )
    rows = (
        db.query(AgentOutboxMessage.id)
        .filter((AgentOutboxMessage.status == 'pending') | due_retry_filter)
        .order_by(AgentOutboxMessage.id.asc())
        .limit(row_limit)
        .all()
    )
    return [
        dispatch_outbox_message(db, int(row_id), sender=sender)
        for (row_id,) in rows
    ]


def run_dry_run_smoke_test(db: Session) -> DryRunSmokeOutcome:
    agent = register_agent(
        db,
        code='agent_management_smoke',
        name='通讯自检 Agent',
        agent_type='governance',
        scope_type='factory',
        config_payload={'managed_by': 'agent_management_dry_run_smoke'},
    )
    channel = register_channel(
        db,
        channel_type='dingtalk_group',
        channel_key='agent-management-dry-run-channel',
        name='通讯自检演练通道',
        target_type='factory',
        target_key='factory',
        dry_run=True,
        metadata_payload={'managed_by': 'agent_management_dry_run_smoke'},
    )
    bind_agent_to_channel(
        db,
        agent_code=agent.code,
        channel_key=channel.channel_key,
        channel_type=channel.channel_type,
        min_severity='info',
    )
    message = queue_bound_message(
        db,
        agent_code=agent.code,
        channel_key=channel.channel_key,
        channel_type=channel.channel_type,
        title='通讯链路演练',
        content='【全厂｜通讯自检】状态：绿；结论：dry-run 演练消息；关键数字：0 条真实外发；原因：验证 outbox 到外发日志链路；建议动作：确认日志可查；数据来源：系统自检；可回复命令：通讯自检。',
        source_summary='agent_management_dry_run_smoke',
        trace_id=f'agent-management-smoke-{uuid4().hex}',
        payload={'smoke_test': True, 'dry_run': True},
    )
    outcome = dispatch_outbox_message(db, message.id)
    logs = list_external_logs(db, outbox_message_id=message.id)
    return DryRunSmokeOutcome(
        status=outcome.status,
        detail=outcome.detail,
        outbox_message_id=outcome.outbox_message_id,
        channel_id=channel.id,
        channel_type=channel.channel_type,
        channel_key=channel.channel_key,
        channel_name=channel.name,
        log_total=len(logs),
    )


def list_external_logs(db: Session, *, outbox_message_id: int) -> list[ExternalMessageLog]:
    return (
        db.query(ExternalMessageLog)
        .filter(ExternalMessageLog.outbox_message_id == int(outbox_message_id))
        .order_by(ExternalMessageLog.id.asc())
        .all()
    )


def record_rate_limit_hit(
    db: Session,
    *,
    scope_key: str,
    event_key: str,
    window_started_at: datetime,
    window_seconds: int,
) -> RateLimitOutcome:
    clean_scope = _clean(scope_key)
    clean_event = _clean(event_key)
    if not clean_scope or not clean_event:
        raise AgentCommunicationError('rate_limit_key_required')

    window_start = _naive_utc(window_started_at)
    existing = (
        db.query(AgentRateLimit)
        .filter(AgentRateLimit.scope_key == clean_scope, AgentRateLimit.event_key == clean_event)
        .first()
    )
    if existing is not None and _naive_utc(existing.window_expires_at) > window_start:
        existing.hit_count += 1
        db.commit()
        db.refresh(existing)
        return RateLimitOutcome(allowed=False, detail='rate_limited', hit_count=existing.hit_count)

    expires_at = window_start + timedelta(seconds=int(window_seconds))
    if existing is None:
        existing = AgentRateLimit(
            scope_key=clean_scope,
            event_key=clean_event,
            window_started_at=window_start,
            window_expires_at=expires_at,
            hit_count=1,
        )
    else:
        existing.window_started_at = window_start
        existing.window_expires_at = expires_at
        existing.hit_count = 1
    _commit_refresh(db, existing)
    return RateLimitOutcome(allowed=True, detail='allowed', hit_count=1)


def _get_active_agent(db: Session, agent_code: str) -> AgentProfile:
    agent = db.query(AgentProfile).filter(AgentProfile.code == _clean(agent_code), AgentProfile.is_active.is_(True)).first()
    if agent is None:
        raise AgentCommunicationError('agent_not_found')
    return agent


def _get_active_channel(db: Session, *, channel_key: str, channel_type: str) -> CommunicationChannel:
    channel = (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_type == _clean(channel_type),
            CommunicationChannel.channel_key == _clean(channel_key),
            CommunicationChannel.is_active.is_(True),
        )
        .first()
    )
    if channel is None:
        raise AgentCommunicationError('channel_not_found')
    return channel


def _build_dingtalk_markdown_payload(message: AgentOutboxMessage) -> dict:
    return {
        'msgtype': 'markdown',
        'markdown': {
            'title': message.title,
            'text': message.content,
        },
    }


def _default_sender(channel: CommunicationChannel):
    if channel.channel_type == 'dingtalk_group':
        return dingtalk_service.send_group_message
    if channel.channel_type == 'dingtalk_work_notice':
        return dingtalk_service.send_work_notification
    raise AgentCommunicationError(f'unsupported_channel_type:{channel.channel_type}')


def _normalize_provider_send_result(value) -> ProviderSendResult:
    if isinstance(value, dict):
        detail = _clean(
            value.get('detail')
            or value.get('message')
            or value.get('errmsg')
            or value.get('status')
            or 'provider_response'
        )
        provider_message_id = _clean(
            value.get('provider_message_id') or value.get('message_id') or value.get('msg_id')
        ) or None
        response_payload = value.get('response_payload')
        if response_payload is None:
            response_payload = {
                str(key): item
                for key, item in value.items()
                if key not in {'detail', 'provider_message_id', 'message_id', 'msg_id'}
            }
        if response_payload is not None and not isinstance(response_payload, dict):
            response_payload = {'value': response_payload}
        return ProviderSendResult(
            detail=detail or 'provider_response',
            provider_message_id=provider_message_id,
            response_payload=response_payload,
        )
    return ProviderSendResult(detail=_clean(str(value or '')) or 'send_failed')


def _mark_retry_or_dead_letter(
    db: Session,
    message: AgentOutboxMessage,
    channel: CommunicationChannel | None,
    detail: str,
    provider_message_id: str | None = None,
    response_payload: dict | None = None,
) -> DispatchOutcome:
    message.attempts += 1
    message.last_error = detail
    if message.attempts >= MAX_DISPATCH_ATTEMPTS:
        message.status = 'dead_letter'
        message.next_retry_at = None
    else:
        message.status = 'retrying'
        message.next_retry_at = _utcnow() + timedelta(minutes=RETRY_DELAY_MINUTES)
    _write_external_log(
        db,
        message=message,
        channel=channel,
        status=message.status,
        detail=detail,
        provider_message_id=provider_message_id,
        response_payload=response_payload,
    )
    db.commit()
    db.refresh(message)
    return DispatchOutcome(status=message.status, detail=detail, outbox_message_id=message.id)


def _write_external_log(
    db: Session,
    *,
    message: AgentOutboxMessage,
    channel: CommunicationChannel | None,
    status: str,
    detail: str,
    provider_message_id: str | None = None,
    response_payload: dict | None = None,
) -> ExternalMessageLog:
    log = ExternalMessageLog(
        outbox_message_id=message.id,
        channel_type=channel.channel_type if channel is not None else 'unknown',
        channel_key=channel.channel_key if channel is not None else None,
        status=status,
        detail=detail,
        provider_message_id=provider_message_id,
        response_payload=response_payload,
    )
    db.add(log)
    return log
