from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentEvent, CommunicationChannel
from app.services import agent_communication_service


class ActiveReportingError(RuntimeError):
    pass


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
        title=f'【全厂总览】{business_date.isoformat()}',
        content=_build_report_content('全厂主动汇报', metrics=metrics, anomalies=safe_anomalies),
        business_date=business_date,
        source_summary='factory_active_report',
        trace_id=safe_trace_id,
        event_id=event.id,
        payload={
            'report_scope': 'factory',
            'metrics': metrics,
            'anomalies': safe_anomalies,
        },
    )
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
        title=f'【{workshop_name}车间主动汇报】{business_date.isoformat()}',
        content=_build_report_content(f'{workshop_name}车间主动汇报', metrics=metrics, anomalies=safe_anomalies),
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
    )
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


def _build_report_content(title: str, *, metrics: dict[str, object], anomalies: list[dict[str, object]]) -> str:
    lines = [f'### {title}', '', '#### 核心数据']
    if metrics:
        lines.extend(f'- {key}：{value}' for key, value in metrics.items())
    else:
        lines.append('- 暂无核心数据')

    lines.extend(['', '#### 异常状态'])
    if anomalies:
        lines.extend(f"- {item.get('title', '异常待核查')}：{item.get('value', '-')}" for item in anomalies)
    else:
        lines.append('- 暂无待核查异常')
    lines.extend(['', '来源：数据中枢主动汇报'])
    return '\n'.join(lines)


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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
