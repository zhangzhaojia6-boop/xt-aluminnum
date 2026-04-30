from __future__ import annotations


ROLE_ALIASES = {
    'factory_director': 'manager',
    'senior_manager': 'manager',
    'stat': 'statistician',
    'team_leader': 'shift_leader',
    'deputy_leader': 'shift_leader',
    'mobile_user': 'shift_leader',
    'EN': 'energy_stat',
    'MT': 'maintenance_lead',
    'HY': 'hydraulic_lead',
    'CS': 'consumable_stat',
    'QC': 'qc',
    'WG': 'weigher',
    'UM': 'utility_manager',
    'IK': 'inventory_keeper',
    'CT': 'contracts',
}

READ_ALL = '*'

FIELD_OWNERSHIP = {
    'work_orders': {
        'tracking_card_no': {'write': [], 'read': [READ_ALL]},
        'process_route_code': {'write': [], 'read': [READ_ALL]},
        'contract_no': {'write': ['contracts'], 'read': ['contracts', 'admin', 'manager', 'statistician']},
        'customer_name': {'write': ['contracts'], 'read': ['contracts', 'admin', 'manager']},
        'contract_weight': {'write': ['contracts'], 'read': ['contracts', 'admin', 'manager', 'statistician']},
        'alloy_grade': {'write': ['contracts', 'shift_leader'], 'read': [READ_ALL]},
        'current_station': {'write': [], 'read': [READ_ALL]},
        'overall_status': {'write': [], 'read': [READ_ALL]},
        'previous_stage_output': {'write': [], 'read': [READ_ALL]},
    },
    'work_order_entries': {
        'machine_id': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'shift_id': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'business_date': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'entry_type': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'on_machine_time': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'off_machine_time': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'input_weight': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'output_weight': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'input_spec': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'output_spec': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'material_state': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'scrap_weight': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'spool_weight': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'operator_notes': {'write': ['shift_leader'], 'read': [READ_ALL]},
        'verified_input_weight': {'write': ['weigher'], 'read': [READ_ALL]},
        'verified_output_weight': {'write': ['weigher'], 'read': [READ_ALL]},
        'qc_grade': {'write': ['qc'], 'read': [READ_ALL]},
        'qc_notes': {'write': ['qc'], 'read': [READ_ALL]},
        'energy_kwh': {'write': ['energy_stat'], 'read': ['energy_stat', 'admin', 'manager', 'statistician']},
        'gas_m3': {'write': ['energy_stat'], 'read': ['energy_stat', 'admin', 'manager', 'statistician']},
        'extra_payload': {'write': ['shift_leader', 'contracts', 'utility_manager', 'inventory_keeper', 'consumable_stat'], 'read': [READ_ALL]},
        'qc_payload': {'write': ['qc'], 'read': [READ_ALL]},
        'yield_rate': {'write': [], 'read': [READ_ALL]},
    },
    'field_amendments': {},
}

ALWAYS_READABLE_FIELDS = {
    'work_orders': {
        'id',
        'tracking_card_no',
        'process_route_code',
        'alloy_grade',
        'current_station',
        'overall_status',
        'previous_stage_output',
        'created_by',
        'created_at',
        'updated_at',
    },
    'work_order_entries': {
        'id',
        'work_order_id',
        'workshop_id',
        'machine_id',
        'shift_id',
        'business_date',
        'weigher_user_id',
        'weighed_at',
        'qc_user_id',
        'qc_at',
        'entry_type',
        'entry_status',
        'extra_payload',
        'qc_payload',
        'locked_fields',
        'submitted_at',
        'verified_at',
        'approved_at',
        'created_by',
        'created_by_user_id',
        'created_by_user_name',
        'created_at',
        'updated_at',
    },
    'field_amendments': {
        'id',
        'table_name',
        'record_id',
        'field_name',
        'old_value',
        'new_value',
        'reason',
        'requested_by',
        'requested_at',
        'approved_by',
        'approved_at',
        'status',
    },
}


def normalize_role(user_role: str | None) -> str:
    raw_role = (user_role or '').strip() or 'user'
    return ROLE_ALIASES.get(raw_role, raw_role)


def _role_in(rule_roles: list[str], user_role: str) -> bool:
    normalized_role = normalize_role(user_role)
    normalized_rules = {normalize_role(item) for item in rule_roles}
    return READ_ALL in normalized_rules or normalized_role in normalized_rules


def get_writable_fields(table: str, user_role: str) -> list[str]:
    rules = FIELD_OWNERSHIP.get(table, {})
    return [field for field, access in rules.items() if _role_in(access.get('write', []), user_role)]


def get_readable_fields(table: str, user_role: str) -> list[str]:
    rules = FIELD_OWNERSHIP.get(table, {})
    readable = {
        field
        for field, access in rules.items()
        if _role_in(access.get('read', []), user_role)
    }
    readable.update(ALWAYS_READABLE_FIELDS.get(table, set()))
    return sorted(readable)


def check_field_write(table: str, field: str, user_role: str) -> bool:
    rules = FIELD_OWNERSHIP.get(table, {})
    access = rules.get(field)
    if access is None:
        return False
    return _role_in(access.get('write', []), user_role)
