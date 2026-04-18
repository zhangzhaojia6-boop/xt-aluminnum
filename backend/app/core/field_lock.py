from __future__ import annotations

from datetime import datetime, timezone

from app.core.field_permissions import get_writable_fields, normalize_role


ENTRY_STATUS_BY_ROLE = {
    'shift_leader': 'submitted',
    'weigher': 'verified',
    'qc': 'approved',
    'energy_stat': 'approved',
    'contracts': 'submitted',
    'inventory_keeper': 'submitted',
    'utility_manager': 'submitted',
}


def get_fields_to_lock(table: str, user_role: str) -> list[str]:
    return sorted(get_writable_fields(table, user_role))


def next_entry_status_for_role(user_role: str, *, current_status: str) -> str:
    normalized_role = normalize_role(user_role)
    next_status = ENTRY_STATUS_BY_ROLE.get(normalized_role)
    if next_status is None:
        raise ValueError(f'role {normalized_role} cannot submit work order entries')

    allowed_current_statuses = {
        'shift_leader': {'draft', 'submitted'},
        'weigher': {'submitted', 'verified'},
        'qc': {'verified', 'approved'},
        'energy_stat': {'verified', 'approved'},
        'contracts': {'draft', 'submitted'},
        'inventory_keeper': {'draft', 'submitted'},
        'utility_manager': {'draft', 'submitted'},
    }
    if current_status not in allowed_current_statuses[normalized_role]:
        raise ValueError(f'entry status {current_status} cannot transition for role {normalized_role}')
    return next_status


def normalize_locked_fields(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def is_field_locked(record, field_name: str) -> bool:
    return field_name in set(normalize_locked_fields(getattr(record, 'locked_fields', None)))


def apply_entry_submit(record, *, user_role: str) -> list[str]:
    locked = set(normalize_locked_fields(getattr(record, 'locked_fields', None)))
    locked.update(get_fields_to_lock('work_order_entries', user_role))
    locked_fields = sorted(locked)
    now = datetime.now(timezone.utc)
    next_status = next_entry_status_for_role(user_role, current_status=getattr(record, 'entry_status', 'draft') or 'draft')

    record.locked_fields = locked_fields
    record.entry_status = next_status
    if next_status == 'submitted':
        record.submitted_at = now
    elif next_status == 'verified':
        record.verified_at = now
    elif next_status == 'approved':
        record.approved_at = now
    return locked_fields
