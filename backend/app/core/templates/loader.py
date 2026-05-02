from __future__ import annotations

from copy import deepcopy
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.field_permissions import READ_ALL, check_field_write, get_readable_fields, normalize_role
from app.models.master import WorkshopTemplateConfig


def _normalize_definition_field(field: dict[str, Any], *, section_name: str) -> dict[str, Any]:
    normalized = deepcopy(field)
    normalized['name'] = str(normalized.get('name') or '').strip()
    normalized['label'] = str(normalized.get('label') or normalized['name']).strip()
    normalized['type'] = _field_type(normalized['name'], normalized.get('type'))
    normalized['required'] = bool(normalized.get('required', False))
    normalized['unit'] = str(normalized.get('unit') or '').strip() or None
    normalized['hint'] = str(normalized.get('hint') or '').strip() or None
    normalized['compute'] = str(normalized.get('compute') or '').strip() or None
    normalized['enabled'] = bool(normalized.get('enabled', True))
    normalized['section'] = section_name
    return normalized

def _normalize_definition_section(fields: list[dict[str, Any]] | None, *, section_name: str) -> list[dict[str, Any]]:
    return [
        _normalize_definition_field(field, section_name=section_name)
        for field in (fields or [])
        if str(field.get('name') or '').strip()
    ]

def _split_supplemental_sections(fields: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    shift_fields: list[dict[str, Any]] = []
    extra_fields: list[dict[str, Any]] = []

    for field in fields or []:
        stored_section = str(field.get('section') or '').strip()
        if stored_section == 'shift_fields':
            shift_fields.append(field)
            continue
        extra_fields.append(field)

    return shift_fields, extra_fields

def _merge_supplemental_sections(
    *,
    shift_fields: list[dict[str, Any]] | None,
    extra_fields: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    merged = []
    merged.extend(_normalize_definition_section(shift_fields, section_name='shift_fields'))
    merged.extend(_normalize_definition_section(extra_fields, section_name='extra_fields'))
    return merged

def _load_template_definition_from_config(config: WorkshopTemplateConfig) -> dict[str, Any]:
    shift_fields, extra_fields = _split_supplemental_sections(config.extra_fields)
    return {
        'display_name': config.display_name,
        'tempo': config.tempo,
        'supports_ocr': bool(config.supports_ocr),
        'entry_fields': _normalize_definition_section(config.entry_fields, section_name='entry_fields'),
        'shift_fields': _normalize_definition_section(shift_fields, section_name='shift_fields'),
        'extra_fields': _normalize_definition_section(extra_fields, section_name='extra_fields'),
        'qc_fields': _normalize_definition_section(config.qc_fields, section_name='qc_fields'),
        'readonly_fields': _normalize_definition_section(config.readonly_fields, section_name='readonly_fields'),
    }

def _load_default_template_definition(base_type: str) -> dict[str, Any]:
    template = deepcopy(DEFAULT_WORKSHOP_TEMPLATES[base_type])
    return {
        'display_name': template['display_name'],
        'tempo': template['tempo'],
        'supports_ocr': bool(template.get('supports_ocr', False)),
        'entry_fields': _normalize_definition_section(template.get('entry_fields'), section_name='entry_fields'),
        'shift_fields': _normalize_definition_section(template.get('shift_fields'), section_name='shift_fields'),
        'extra_fields': _normalize_definition_section(template.get('extra_fields'), section_name='extra_fields'),
        'qc_fields': _normalize_definition_section(template.get('qc_fields'), section_name='qc_fields'),
        'readonly_fields': _normalize_definition_section(template.get('readonly_fields'), section_name='readonly_fields'),
    }

def get_workshop_template_definition(
    template_key: str,
    *,
    db: Session | None = None,
    workshop_type: str | None = None,
    workshop_code: str | None = None,
    workshop_name: str | None = None,
) -> dict[str, Any]:
    canonical_key, base_type = resolve_template_key(
        template_key=template_key,
        workshop_type=workshop_type,
        workshop_code=workshop_code,
        workshop_name=workshop_name,
    )

    config = None
    if db is not None and hasattr(db, 'query'):
        config = (
            db.query(WorkshopTemplateConfig)
            .filter(
                WorkshopTemplateConfig.template_key == canonical_key,
                WorkshopTemplateConfig.is_active.is_(True),
            )
            .first()
        )

    definition = _load_template_definition_from_config(config) if config is not None else _load_default_template_definition(base_type)
    return {
        'template_key': canonical_key,
        'workshop_type': base_type,
        'source_template_key': canonical_key if config is not None else base_type,
        'has_override': config is not None,
        **definition,
    }

def normalize_template_definition_payload(
    template_key: str,
    payload: dict[str, Any],
    *,
    db: Session | None = None,
) -> dict[str, Any]:
    definition = get_workshop_template_definition(template_key, db=db)
    return {
        'template_key': definition['template_key'],
        'workshop_type': definition['workshop_type'],
        'display_name': str(payload.get('display_name') or definition['display_name']).strip() or definition['display_name'],
        'tempo': str(payload.get('tempo') or definition['tempo']).strip() or definition['tempo'],
        'supports_ocr': bool(payload.get('supports_ocr', definition['supports_ocr'])),
        'entry_fields': _normalize_definition_section(payload.get('entry_fields'), section_name='entry_fields'),
        'shift_fields': _normalize_definition_section(payload.get('shift_fields'), section_name='shift_fields'),
        'extra_fields': _normalize_definition_section(payload.get('extra_fields'), section_name='extra_fields'),
        'qc_fields': _normalize_definition_section(payload.get('qc_fields'), section_name='qc_fields'),
        'readonly_fields': _normalize_definition_section(payload.get('readonly_fields'), section_name='readonly_fields'),
    }
