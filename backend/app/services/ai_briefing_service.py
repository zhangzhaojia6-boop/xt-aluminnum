from __future__ import annotations

from datetime import time
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.scope import ScopeSummary
from app.models.assistant import AiBriefingEvent
from app.services import ai_rules_service, factory_command_service


_SEVERITY_ORDER = {'info': 0, 'warning': 1, 'critical': 2}


def _max_severity(rules: list[dict[str, Any]]) -> str:
    severity = 'info'
    for rule in rules:
        candidate = str(rule.get('severity') or 'info')
        if _SEVERITY_ORDER.get(candidate, 0) > _SEVERITY_ORDER.get(severity, 0):
            severity = candidate
    return severity


def _title_for(briefing_type: str) -> str:
    return {
        'opening_shift': '开班简报',
        'hourly_inspection': '小时巡检',
        'exception_flash': '异常快报',
        'watchlist_update': '关注对象汇报',
        'handover': '交接摘要',
        'manager_briefing': '管理层简报',
    }.get(briefing_type, 'AI 汇报')


def _save_event(
    db: Session,
    *,
    briefing_type: str,
    severity: str,
    payload: dict[str, Any],
    owner_user_id: int | None = None,
    scope_key: str | None = None,
    delivery_suppressed: bool = False,
) -> dict[str, Any]:
    public_id = f'brief-{uuid4().hex[:12]}'
    event = {
        'id': public_id,
        'briefing_type': briefing_type,
        'severity': severity,
        'title': _title_for(briefing_type),
        'payload': payload,
        'owner_user_id': owner_user_id,
        'read': False,
        'follow_up_status': 'none',
        'scope_key': scope_key,
        'delivery_suppressed': delivery_suppressed,
    }
    if hasattr(db, 'add'):
        db.add(
            AiBriefingEvent(
                public_id=public_id,
                owner_user_id=owner_user_id,
                briefing_type=briefing_type,
                severity=severity,
                title=event['title'],
                scope_key=scope_key,
                payload=payload,
                delivery_suppressed=delivery_suppressed,
            )
        )
        if hasattr(db, 'flush'):
            db.flush()
    return event


def _call_scoped(func, db: Session, *, scope: ScopeSummary | None):
    try:
        return func(db, scope=scope)
    except TypeError:
        return func(db)


def generate_briefing(
    db: Session,
    *,
    briefing_type: str,
    hide_normal: bool = False,
    owner_user_id: int | None = None,
    scope: ScopeSummary | None = None,
) -> dict[str, Any]:
    overview = _call_scoped(factory_command_service.build_overview, db, scope=scope)
    machine_lines = _call_scoped(factory_command_service.list_machine_lines, db, scope=scope)
    rules = _call_scoped(ai_rules_service.evaluate_rules, db, scope=scope)
    priority_lines = sorted(machine_lines, key=lambda item: (item.get('stalled_count', 0), item.get('active_tons', 0)), reverse=True)[:5]
    payload = {
        'wip_tons': overview.get('wip_tons', 0),
        'abnormal_count': overview.get('abnormal_count', 0),
        'sync_state': overview.get('freshness', {}),
        'priority_machine_lines': priority_lines,
        'rules_fired': rules,
        'normal_items': [] if hide_normal else [{'key': 'factory_state', 'status': 'normal'}],
    }
    return _save_event(
        db,
        briefing_type=briefing_type,
        severity=_max_severity(rules),
        payload=payload,
        owner_user_id=owner_user_id,
    )


def generate_watchlist_briefing(
    db: Session,
    *,
    watch: Any,
    current_time: time | None = None,
    scope: ScopeSummary | None = None,
) -> dict[str, Any]:
    rules = [
        rule
        for rule in _call_scoped(ai_rules_service.evaluate_rules, db, scope=scope)
        if not getattr(watch, 'trigger_rules', None) or rule.get('key') in getattr(watch, 'trigger_rules', [])
    ]
    quiet = _is_quiet_hour(getattr(watch, 'quiet_hours', None), current_time=current_time)
    payload = {
        'watch_type': getattr(watch, 'watch_type', ''),
        'scope_key': getattr(watch, 'scope_key', ''),
        'rules_fired': rules,
    }
    return _save_event(
        db,
        briefing_type='watchlist_update',
        severity=_max_severity(rules),
        payload=payload,
        owner_user_id=getattr(watch, 'owner_user_id', None),
        scope_key=getattr(watch, 'scope_key', None),
        delivery_suppressed=quiet,
    )


def _is_quiet_hour(quiet_hours: dict[str, Any] | None, *, current_time: time | None = None) -> bool:
    if not quiet_hours:
        return False
    current = current_time or time(0, 0)
    start = _parse_time(quiet_hours.get('start'))
    end = _parse_time(quiet_hours.get('end'))
    if start is None or end is None:
        return False
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def _parse_time(value: Any) -> time | None:
    if not isinstance(value, str) or ':' not in value:
        return None
    hour_text, minute_text = value.split(':', 1)
    try:
        return time(int(hour_text), int(minute_text))
    except ValueError:
        return None
