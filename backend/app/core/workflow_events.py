from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


SUPPORTED_WORKFLOW_EVENTS = frozenset({
    'entry_saved',
    'entry_submitted',
    'attendance_confirmed',
    'report_reviewed',
    'report_published',
})


def _normalize_optional_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_occurred_at(occurred_at: datetime | None) -> str:
    normalized = occurred_at or datetime.now(timezone.utc)
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    return normalized.isoformat()


def build_workflow_event(
    *,
    event_type: str,
    actor_role: str | None,
    actor_id: int | None,
    scope_type: str | None,
    workshop_id: int | None,
    team_id: int | None,
    shift_id: int | None,
    entity_type: str,
    entity_id: int | None,
    status: str | None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    if event_type not in SUPPORTED_WORKFLOW_EVENTS:
        raise ValueError(f'unsupported workflow event: {event_type}')
    if not entity_type:
        raise ValueError('entity_type is required')

    return {
        'event_type': event_type,
        'occurred_at': _normalize_occurred_at(occurred_at),
        'actor_role': actor_role or 'system',
        'actor_id': _normalize_optional_int(actor_id),
        'scope_type': scope_type or 'workshop',
        'workshop_id': _normalize_optional_int(workshop_id),
        'team_id': _normalize_optional_int(team_id),
        'shift_id': _normalize_optional_int(shift_id),
        'entity_type': entity_type,
        'entity_id': _normalize_optional_int(entity_id),
        'status': status or '',
        'payload': dict(payload or {}),
    }


def attach_workflow_event(payload: dict[str, Any] | None, workflow_event: dict[str, Any]) -> dict[str, Any]:
    merged = dict(payload or {})
    merged['workflow_event'] = workflow_event
    return merged
