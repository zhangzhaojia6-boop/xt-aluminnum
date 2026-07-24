from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentEvent, CommunicationChannel
from app.services import agent_communication_service


class ActiveReportingError(RuntimeError):
    pass


UNCHANGED_STATE_DEDUPE_MINUTES = 24 * 60


@dataclass(frozen=True, slots=True)
class ActiveReportOutcome:
    status: str
    detail: str
    event_id: int | None
    outbox_message_id: int | None
    severity: str


def queue_factory_overview(
    db: Session,
    *,
    business_date: date,
    channel_key: str,
    metrics: dict[str, object],
    anomalies: list[dict[str, object]] | None = None,
    trace_id: str | None = None,
    occurred_at: datetime | None = None,
    window_seconds: int = 1800,
) -> ActiveReportOutcome:
    channel = _get_channel(db, channel_key=channel_key)
    if channel.target_type != 'management':
        raise ActiveReportingError('channel_scope_mismatch')

    safe_trace_id = trace_id or uuid4().hex
    safe_anomalies = list(anomalies or [])
    severity = _highest_severity(safe_anomalies)
    event = _create_event(
        db,
        event_type='factory_overview_report',
        severity=severity,
        scope_type='factory',
        business_date=business_date,
        occurred_at=occurred_at,
        source_summary='factory_active_report',
        trace_id=safe_trace_id,
        channel_key=channel.channel_key,
        metrics=metrics,
        anomalies=safe_anomalies,
    )

    rate = agent_communication_service.record_rate_limit_hit(
        db,
        scope_key='factory:management',
        event_key=f'factory_overview:{business_date.isoformat()}',
        window_started_at=occurred_at or _utcnow(),
        window_seconds=window_seconds,
    )
    if not rate.allowed:
        event.status = 'suppressed'
        event.payload = {**(event.payload or {}), 'rate_limit_detail': rate.detail}
        db.commit()
        db.refresh(event)
        return ActiveReportOutcome(
            status='suppressed',
            detail=rate.detail,
            event_id=event.id,
            outbox_message_id=None,
            severity=event.severity,
        )

    message = agent_communication_service.queue_bound_message(
        db,
        agent_code='factory_dispatch',
        channel_key=channel.channel_key,
        title=f'全厂情况 {business_date.isoformat()}',
        content=_build_report_content(
            scope_label='全厂',
            time_label=_format_time_label(occurred_at, business_date),
            metrics=metrics,
            anomalies=safe_anomalies,
        ),
        business_date=business_date,
        source_summary='factory_active_report',
        trace_id=safe_trace_id,
        event_id=event.id,
        payload={
            'report_scope': 'factory',
            'metrics': metrics,
            'anomalies': safe_anomalies,
        },
        dedupe_key=_build_dedupe_key(
            event_type='factory_overview_report',
            scope_type='factory',
            workshop_id=None,
            business_date=business_date,
            channel_key=channel.channel_key,
            anomalies=safe_anomalies,
        ),
        dedupe_window_minutes=UNCHANGED_STATE_DEDUPE_MINUTES,
        now=occurred_at,
    )
    if message.event_id != event.id:
        return _mark_event_deduped(db, event, message)
    event.status = 'queued'
    db.commit()
    db.refresh(event)
    db.refresh(message)
    return ActiveReportOutcome(
        status='queued',
        detail='queued',
        event_id=event.id,
        outbox_message_id=message.id,
        severity=event.severity,
    )


def queue_workshop_status(
    db: Session,
    *,
    business_date: date,
    channel_key: str,
    workshop_id: int,
    workshop_name: str,
    metrics: dict[str, object],
    anomalies: list[dict[str, object]] | None = None,
    trace_id: str | None = None,
    occurred_at: datetime | None = None,
    window_seconds: int = 1800,
) -> ActiveReportOutcome:
    channel = _get_channel(db, channel_key=channel_key)
    if channel.target_type != 'workshop' or channel.workshop_id != int(workshop_id):
        raise ActiveReportingError('channel_scope_mismatch')

    safe_trace_id = trace_id or uuid4().hex
    safe_anomalies = list(anomalies or [])
    severity = _highest_severity(safe_anomalies)
    event = _create_event(
        db,
        event_type='workshop_status_report',
        severity=severity,
        scope_type='workshop',
        workshop_id=workshop_id,
        business_date=business_date,
        occurred_at=occurred_at,
        source_summary='workshop_active_report',
        trace_id=safe_trace_id,
        channel_key=channel.channel_key,
        metrics=metrics,
        anomalies=safe_anomalies,
    )

    rate = agent_communication_service.record_rate_limit_hit(
        db,
        scope_key=f'workshop:{workshop_id}',
        event_key=f'workshop_status:{workshop_id}:{business_date.isoformat()}',
        window_started_at=occurred_at or _utcnow(),
        window_seconds=window_seconds,
    )
    if not rate.allowed:
        event.status = 'suppressed'
        event.payload = {**(event.payload or {}), 'rate_limit_detail': rate.detail}
        db.commit()
        db.refresh(event)
        return ActiveReportOutcome(
            status='suppressed',
            detail=rate.detail,
            event_id=event.id,
            outbox_message_id=None,
            severity=event.severity,
        )

    message = agent_communication_service.queue_bound_message(
        db,
        agent_code='workshop_status',
        channel_key=channel.channel_key,
        title=f'{workshop_name}车间情况 {business_date.isoformat()}',
        content=_build_report_content(
            scope_label=f'{workshop_name}车间',
            time_label=_format_time_label(occurred_at, business_date),
            metrics=metrics,
            anomalies=safe_anomalies,
        ),
        business_date=business_date,
        source_summary='workshop_active_report',
        trace_id=safe_trace_id,
        event_id=event.id,
        payload={
            'report_scope': 'workshop',
            'workshop_id': workshop_id,
            'workshop_name': workshop_name,
            'metrics': metrics,
            'anomalies': safe_anomalies,
        },
        dedupe_key=_build_dedupe_key(
            event_type='workshop_status_report',
            scope_type='workshop',
            workshop_id=workshop_id,
            business_date=business_date,
            channel_key=channel.channel_key,
            anomalies=safe_anomalies,
        ),
        dedupe_window_minutes=UNCHANGED_STATE_DEDUPE_MINUTES,
        now=occurred_at,
    )
    if message.event_id != event.id:
        return _mark_event_deduped(db, event, message)
    event.status = 'queued'
    db.commit()
    db.refresh(event)
    db.refresh(message)
    return ActiveReportOutcome(
        status='queued',
        detail='queued',
        event_id=event.id,
        outbox_message_id=message.id,
        severity=event.severity,
    )


def detect_basic_anomalies(snapshot: dict[str, object]) -> list[dict[str, object]]:
    anomalies: list[dict[str, object]] = []
    missing_count = _to_float(snapshot.get('missing_report_count'))
    if missing_count > 0:
        anomalies.append(
            {
                'type': 'missing_report',
                'severity': 'warning',
                'title': '存在缺报',
                'value': _format_number(missing_count),
            }
        )

    production_gap = _to_float(snapshot.get('production_gap_tons'))
    if production_gap > 0:
        anomalies.append(
            {
                'type': 'production_gap',
                'severity': 'warning',
                'title': '产量差异待核查',
                'value': f'{_format_number(production_gap)} 吨',
            }
        )

    sync_status = str(snapshot.get('mes_sync_status') or '').strip().lower()
    if sync_status and sync_status not in {'ok', 'fresh', 'normal'}:
        anomalies.append(
            {
                'type': 'mes_sync_stale',
                'severity': 'warning',
                'title': 'MES 数据同步异常',
                'value': sync_status,
            }
        )

    stopped_minutes = _to_float(snapshot.get('stopped_machine_minutes'))
    if stopped_minutes >= 30:
        anomalies.append(
            {
                'type': 'machine_stop',
                'severity': 'critical',
                'title': '设备停机时间偏长',
                'value': f'{_format_number(stopped_minutes)} 分钟',
            }
        )
    return anomalies


def _create_event(
    db: Session,
    *,
    event_type: str,
    severity: str,
    scope_type: str,
    business_date: date,
    occurred_at: datetime | None,
    source_summary: str,
    trace_id: str,
    channel_key: str,
    metrics: dict[str, object],
    anomalies: list[dict[str, object]],
    workshop_id: int | None = None,
) -> AgentEvent:
    event = AgentEvent(
        event_type=event_type,
        severity=severity,
        status='pending',
        scope_type=scope_type,
        workshop_id=workshop_id,
        source_type='agent_active_reporting',
        source_ref=trace_id,
        business_date=business_date,
        occurred_at=occurred_at or _utcnow(),
        payload={
            'source_summary': source_summary,
            'trace_id': trace_id,
            'channel_key': channel_key,
            'metrics': metrics,
            'anomalies': anomalies,
        },
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _get_channel(db: Session, *, channel_key: str, channel_type: str = 'dingtalk_group') -> CommunicationChannel:
    channel = (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_key == str(channel_key).strip(),
            CommunicationChannel.channel_type == channel_type,
            CommunicationChannel.is_active.is_(True),
        )
        .first()
    )
    if channel is None:
        raise ActiveReportingError('channel_not_found')
    return channel


def _build_report_content(
    *,
    scope_label: str,
    time_label: str,
    metrics: dict[str, object],
    anomalies: list[dict[str, object]],
) -> str:
    metric_text = _metric_summary(metrics)
    anomaly_text = _anomaly_summary(anomalies)
    if not anomalies:
        return f'{scope_label} {time_label} 运行正常。当前：{metric_text}。'
    action = _recommended_action(anomalies)
    return (
        f'{scope_label} {time_label} 有{len(anomalies)}项需要看一下：'
        f'{anomaly_text}。{action} 当前：{metric_text}。'
    )


def _highest_severity(anomalies: list[dict[str, object]]) -> str:
    order = {'info': 0, 'warning': 1, 'critical': 2}
    level = 0
    for item in anomalies:
        level = max(level, order.get(str(item.get('severity') or 'warning'), 1))
    for name, value in order.items():
        if value == level:
            return name
    return 'info'


def _to_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f'{value:.2f}'.rstrip('0').rstrip('.')


def _format_time_label(occurred_at: datetime | None, business_date: date) -> str:
    if occurred_at is None:
        return business_date.isoformat()
    value = occurred_at.astimezone(timezone.utc) if occurred_at.tzinfo is not None else occurred_at
    return value.strftime('%Y-%m-%d %H:%M')


def _metric_summary(metrics: dict[str, object]) -> str:
    if not metrics:
        return '暂无核心数据'
    return '；'.join(f'{key}：{value}' for key, value in metrics.items())


def _anomaly_summary(anomalies: list[dict[str, object]]) -> str:
    if not anomalies:
        return '暂无待核查异常'
    return '；'.join(f"{item.get('title', '异常待核查')}：{item.get('value', '-')}" for item in anomalies)


def _recommended_action(anomalies: list[dict[str, object]]) -> str:
    if not anomalies:
        return '继续观察，按计划生产'
    severe = any(str(item.get('severity') or '').strip().lower() == 'critical' for item in anomalies)
    if severe:
        return '请责任人立即确认原因和恢复时间'
    return '请责任人核查异常并在群内反馈'


def _mark_event_deduped(db: Session, event: AgentEvent, message) -> ActiveReportOutcome:
    event.status = 'suppressed'
    event.payload = {
        **(event.payload or {}),
        'dedupe_detail': 'outbox_deduped',
        'deduped_outbox_message_id': message.id,
    }
    db.commit()
    db.refresh(event)
    db.refresh(message)
    return ActiveReportOutcome(
        status='suppressed',
        detail='outbox_deduped',
        event_id=event.id,
        outbox_message_id=message.id,
        severity=event.severity,
    )


def _build_dedupe_key(
    *,
    event_type: str,
    scope_type: str,
    workshop_id: int | None,
    business_date: date,
    channel_key: str,
    anomalies: list[dict[str, object]],
) -> str:
    if scope_type == 'workshop':
        scope_key = f'workshop:{int(workshop_id or 0)}'
    else:
        scope_key = 'factory'
    raw_key = ':'.join(
        [
            _clean_component(event_type),
            scope_key,
            business_date.isoformat(),
            _clean_component(channel_key),
            _anomaly_signature(anomalies),
        ]
    )
    if len(raw_key) <= 150:
        return raw_key
    digest = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()[:16]
    return f'{raw_key[:133]}:{digest}'


def _anomaly_signature(anomalies: list[dict[str, object]]) -> str:
    parts = []
    for item in anomalies:
        anomaly_type = _clean_component(str(item.get('type') or 'unknown'))
        severity = _clean_component(str(item.get('severity') or 'warning'))
        title = _clean_component(str(item.get('title') or item.get('value') or 'unknown'))
        parts.append(f'{anomaly_type}:{severity}:{title}')
    return '+'.join(sorted(parts)) if parts else 'normal'


def _clean_component(value: object) -> str:
    return str(value or '').strip().replace('\n', ' ').replace('\r', ' ') or 'unknown'


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
