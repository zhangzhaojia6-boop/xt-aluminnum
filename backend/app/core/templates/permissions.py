from __future__ import annotations

from copy import deepcopy
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.field_permissions import READ_ALL, check_field_write, get_readable_fields, normalize_role
from app.models.master import WorkshopTemplateConfig


def _listify(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]

def _field_type(field_name: str, explicit_type: str | None = None) -> str:
    if explicit_type:
        return explicit_type
    if field_name in TIME_FIELD_NAMES:
        return 'time'
    if field_name in NUMERIC_FIELD_NAMES:
        return 'number'
    return 'text'

def _field_target(section_name: str, field_name: str) -> str:
    if field_name in WORK_ORDER_FIELD_NAMES:
        return 'work_order'
    if section_name == 'qc_fields':
        return 'qc'
    if field_name in WORK_ORDER_ENTRY_FIELD_NAMES:
        return 'entry'
    return 'extra'

def _default_write_roles(section_name: str, field_name: str, target: str) -> list[str]:
    if target == 'work_order':
        return []
    if target == 'entry':
        if field_name in {'energy_kwh', 'gas_m3'}:
            return ['energy_stat']
        return []
    if target == 'qc':
        return ['qc']
    return ['shift_leader']

def _default_read_roles(section_name: str, target: str, field_name: str) -> list[str]:
    if section_name == 'shift_fields':
        return ['shift_leader', 'admin', 'manager']
    if target in {'extra', 'qc'}:
        return [READ_ALL]
    if target in {'work_order', 'entry'}:
        return []
    return [READ_ALL]

def _is_readable(target: str, field_name: str, read_roles: list[str], user_role: str) -> bool:
    normalized_role = normalize_role(user_role)
    normalized_rules = {normalize_role(item) for item in read_roles}
    if READ_ALL in normalized_rules or normalized_role in normalized_rules:
        return True
    if target == 'work_order':
        return field_name in set(get_readable_fields('work_orders', user_role))
    if target == 'entry':
        return field_name in set(get_readable_fields('work_order_entries', user_role))
    return False

def _is_writable(target: str, field_name: str, write_roles: list[str], user_role: str) -> bool:
    normalized_role = normalize_role(user_role)
    normalized_rules = {normalize_role(item) for item in write_roles}
    if READ_ALL in normalized_rules or normalized_role in normalized_rules:
        return True
    if target == 'work_order':
        return check_field_write('work_orders', field_name, user_role)
    if target == 'entry':
        return check_field_write('work_order_entries', field_name, user_role)
    return False

def _normalize_field(
    section_name: str,
    field: dict[str, Any],
    user_role: str,
    *,
    force_readonly: bool = False,
) -> tuple[dict[str, Any], bool, bool]:
    normalized = deepcopy(field)
    field_name = normalized['name']
    target = _field_target(section_name, field_name)
    write_roles = _listify(normalized.get('role_write')) or _default_write_roles(section_name, field_name, target)
    read_roles = _listify(normalized.get('role_read')) or _default_read_roles(section_name, target, field_name)

    normalized['type'] = _field_type(field_name, normalized.get('type'))
    normalized['target'] = target
    normalized['section'] = section_name
    normalized['role_write'] = write_roles
    normalized['role_read'] = read_roles
    normalized['compute'] = normalized.get('compute')

    readable = _is_readable(target, field_name, read_roles, user_role)
    if force_readonly:
        normalized['editable'] = False
        normalized['readonly'] = readable
        return normalized, False, readable

    writable = _is_writable(target, field_name, write_roles, user_role)
    normalized['editable'] = writable
    normalized['readonly'] = readable and not writable
    return normalized, writable, readable

def get_workshop_template(workshop_type: str, *, user_role: str, db: Session | None = None) -> dict[str, Any]:
    template = get_workshop_template_definition(workshop_type, db=db)

    effective_role = normalize_role(user_role) or user_role
    is_power_user = effective_role in _POWER_ROLES or user_role in _POWER_ROLES

    readonly_fields: list[dict[str, Any]] = []
    result = {
        'template_key': template['template_key'],
        'workshop_type': template['workshop_type'],
        'display_name': template['display_name'],
        'tempo': template['tempo'],
        'supports_ocr': bool(template.get('supports_ocr', False)),
        'entry_fields': [],
        'shift_fields': [],
        'extra_fields': [],
        'qc_fields': [],
        'readonly_fields': readonly_fields,
    }

    for section_name in ['entry_fields', 'shift_fields', 'extra_fields', 'qc_fields']:
        for field in template.get(section_name, []):
            if not field.get('enabled', True):
                continue
            normalized, writable, readable = _normalize_field(section_name, field, user_role)
            normalized['enabled'] = True
            if is_power_user:
                normalized['editable'] = True
                normalized['readonly'] = False
                result[section_name].append(normalized)
            elif writable:
                result[section_name].append(normalized)
            elif readable:
                readonly_fields.append(normalized)

    for field in template.get('readonly_fields', []):
        if not field.get('enabled', True):
            continue
        normalized, _writable, readable = _normalize_field('readonly_fields', field, user_role, force_readonly=True)
        normalized['enabled'] = True
        if readable:
            readonly_fields.append(normalized)

    return result
