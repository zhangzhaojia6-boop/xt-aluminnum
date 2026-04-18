from __future__ import annotations

from dataclasses import dataclass, field

from app.models.system import User


VALID_SCOPE_TYPES = {'self_team', 'self_workshop', 'assigned', 'all'}
MOBILE_ROLES = {
    'team_leader',
    'deputy_leader',
    'mobile_user',
    'shift_leader',
    'weigher',
    'qc',
    'energy_stat',
    'maintenance_lead',
    'hydraulic_lead',
    'contracts',
    'inventory_keeper',
    'utility_manager',
}
REVIEWER_ROLES = {'statistician', 'workshop_director', 'reviewer', 'stat'}
MANAGER_ROLES = {'factory_director', 'senior_manager', 'manager'}
WORK_ORDER_GLOBAL_ENTRY_ROLES = {'admin', 'statistician', 'stat', 'manager', 'factory_director', 'senior_manager'}
WORK_ORDER_GLOBAL_HEADER_ROLES = WORK_ORDER_GLOBAL_ENTRY_ROLES | {'contracts'}
WORK_ORDER_LOCAL_ENTRY_ROLES = {
    'shift_leader',
    'weigher',
    'qc',
    'energy_stat',
    'team_leader',
    'maintenance_lead',
    'hydraulic_lead',
    'contracts',
    'inventory_keeper',
    'utility_manager',
}


@dataclass(slots=True)
class ScopeSummary:
    user_id: int | None
    role: str
    workshop_id: int | None
    team_id: int | None
    data_scope_type: str
    assigned_shift_ids: list[int] = field(default_factory=list)
    is_mobile_user: bool = False
    is_reviewer: bool = False
    is_manager: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'


def build_scope_summary(user: User) -> ScopeSummary:
    role = (getattr(user, 'role', None) or '').strip() or 'user'
    data_scope_type = (getattr(user, 'data_scope_type', None) or '').strip().lower() or 'self_team'
    if data_scope_type not in VALID_SCOPE_TYPES:
        data_scope_type = 'self_team'
    if role == 'admin':
        data_scope_type = 'all'
    elif role in MANAGER_ROLES and data_scope_type == 'self_team':
        data_scope_type = 'self_workshop' if getattr(user, 'workshop_id', None) else 'all'
    elif role in REVIEWER_ROLES and data_scope_type == 'self_team' and getattr(user, 'team_id', None) is None:
        data_scope_type = 'self_workshop'
    assigned_shift_ids = []
    raw_shift_ids = getattr(user, 'assigned_shift_ids', None) or []
    for value in raw_shift_ids:
        try:
            assigned_shift_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    is_mobile_user = bool(getattr(user, 'is_mobile_user', False)) or role in MOBILE_ROLES
    is_reviewer = bool(getattr(user, 'is_reviewer', False)) or role in REVIEWER_ROLES or role == 'admin'
    is_manager = bool(getattr(user, 'is_manager', False)) or role in MANAGER_ROLES or role == 'admin'

    return ScopeSummary(
        user_id=getattr(user, 'id', None),
        role=role,
        workshop_id=getattr(user, 'workshop_id', None),
        team_id=getattr(user, 'team_id', None),
        data_scope_type=data_scope_type,
        assigned_shift_ids=assigned_shift_ids,
        is_mobile_user=is_mobile_user,
        is_reviewer=is_reviewer,
        is_manager=is_manager,
    )


def scope_to_dict(summary: ScopeSummary) -> dict:
    return {
        'user_id': summary.user_id,
        'role': summary.role,
        'workshop_id': summary.workshop_id,
        'team_id': summary.team_id,
        'data_scope_type': summary.data_scope_type,
        'assigned_shift_ids': summary.assigned_shift_ids,
        'is_mobile_user': summary.is_mobile_user,
        'is_reviewer': summary.is_reviewer,
        'is_manager': summary.is_manager,
    }


def can_view_all_work_order_headers(summary: ScopeSummary) -> bool:
    return summary.role in WORK_ORDER_GLOBAL_HEADER_ROLES or summary.is_admin


def can_view_all_work_order_entries(summary: ScopeSummary) -> bool:
    return summary.role in WORK_ORDER_GLOBAL_ENTRY_ROLES or summary.is_admin


def can_view_work_order_entries(summary: ScopeSummary) -> bool:
    return (
        summary.role in WORK_ORDER_GLOBAL_ENTRY_ROLES
        or summary.role in WORK_ORDER_LOCAL_ENTRY_ROLES
        or summary.is_admin
        or summary.is_reviewer
        or summary.is_manager
    )


def resolve_work_order_entry_workshop_scope(summary: ScopeSummary) -> int | None:
    if not can_view_work_order_entries(summary):
        return None
    if can_view_all_work_order_entries(summary):
        return None
    if summary.role in WORK_ORDER_LOCAL_ENTRY_ROLES:
        return summary.workshop_id
    if summary.data_scope_type == 'self_workshop':
        return summary.workshop_id
    return summary.workshop_id
