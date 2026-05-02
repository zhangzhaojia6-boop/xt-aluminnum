from __future__ import annotations

from copy import deepcopy
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.field_permissions import READ_ALL, check_field_write, get_readable_fields, normalize_role
from app.models.master import WorkshopTemplateConfig


def normalize_workshop_type(workshop_type: str | None) -> str | None:
    raw_value = (workshop_type or '').strip().lower()
    if not raw_value:
        return None
    return WORKSHOP_TYPE_ALIASES.get(raw_value, raw_value)

def normalize_template_key(template_key: str | None) -> str | None:
    raw_value = (template_key or '').strip()
    if not raw_value:
        return None

    normalized_type = normalize_workshop_type(raw_value)
    if normalized_type in DEFAULT_WORKSHOP_TEMPLATES:
        return normalized_type

    uppercase_value = raw_value.upper()
    if uppercase_value in WORKSHOP_TYPE_BY_WORKSHOP_CODE:
        return uppercase_value

    return uppercase_value

def resolve_template_key(
    *,
    template_key: str | None = None,
    workshop_type: str | None = None,
    workshop_code: str | None = None,
    workshop_name: str | None = None,
) -> tuple[str, str]:
    normalized_key = normalize_template_key(template_key)
    if normalized_key:
        if normalized_key in DEFAULT_WORKSHOP_TEMPLATES:
            return normalized_key, normalized_key
        if normalized_key in WORKSHOP_TYPE_BY_WORKSHOP_CODE:
            return normalized_key, resolve_workshop_type(
                workshop_type=WORKSHOP_TYPE_BY_WORKSHOP_CODE.get(normalized_key),
                workshop_code=normalized_key,
                workshop_name=workshop_name,
            )

    base_type = resolve_workshop_type(
        workshop_type=workshop_type,
        workshop_code=workshop_code,
        workshop_name=workshop_name,
    )
    if workshop_code and workshop_code.strip().upper() in WORKSHOP_TYPE_BY_WORKSHOP_CODE:
        return workshop_code.strip().upper(), base_type
    return base_type, base_type

def resolve_workshop_type(
    *,
    workshop_type: str | None = None,
    workshop_code: str | None,
    workshop_name: str | None,
) -> str:
    normalized_type = normalize_workshop_type(workshop_type)
    if normalized_type in WORKSHOP_TEMPLATES:
        return normalized_type

    code = (workshop_code or '').strip().upper()
    normalized_code = normalize_workshop_type((workshop_code or '').strip().lower())
    name = (workshop_name or '').strip()

    if normalized_code in WORKSHOP_TEMPLATES:
        return normalized_code

    mapped_type = WORKSHOP_TYPE_BY_WORKSHOP_CODE.get(code)
    if mapped_type in WORKSHOP_TEMPLATES:
        return mapped_type

    lowered_name = name.lower()
    if '2050' in code or '2050' in name or '1450' in code or '1450' in name or code.startswith('LZ'):
        return 'cold_roll'
    if code.startswith('ZR') or code == 'ZD' or '铸' in name:
        return 'casting'
    if code == 'RZ' or '热轧' in name:
        return 'hot_roll'
    if code.startswith('JZ') or '精整' in name:
        return 'finishing'
    if code == 'JQ' or '剪切' in name:
        return 'shearing'
    if code == 'CPK' or '成品库' in name or '库存' in name:
        return 'inventory'
    if code == 'ZXTF' or '退火' in name:
        return 'annealing'
    if 'cold' in lowered_name:
        return 'cold_roll'
    if 'finish' in lowered_name:
        return 'finishing'
    if 'shear' in lowered_name or 'cut' in lowered_name:
        return 'shearing'
    if 'hot' in lowered_name:
        return 'hot_roll'
    if 'inventory' in lowered_name or 'warehouse' in lowered_name:
        return 'inventory'
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='workshop template not found')
