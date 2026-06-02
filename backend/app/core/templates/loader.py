from __future__ import annotations

from copy import deepcopy
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.field_permissions import READ_ALL, check_field_write, get_readable_fields, normalize_role
from app.models.master import WorkshopTemplateConfig


QUALITY_ENTRY_FIELD_NAMES = {
    'quality_note',
    'quality_issue_type',
    'quality_issue_card_no',
    'quality_issue_desc',
    'quality_issue_photo_path',
}


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
        and not (section_name == 'entry_fields' and str(field.get('name') or '').strip() in QUALITY_ENTRY_FIELD_NAMES)
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

_REQUIRED_ENTRY_FIELDS_BY_BASE_TYPE = {
    'casting': ('output_weight',),
}

def _ensure_required_entry_fields(definition: dict[str, Any], base_type: str) -> dict[str, Any]:
    required_names = _REQUIRED_ENTRY_FIELDS_BY_BASE_TYPE.get(base_type)
    if not required_names:
        return definition

    default_fields = _normalize_definition_section(
        DEFAULT_WORKSHOP_TEMPLATES[base_type].get('entry_fields'),
        section_name='entry_fields',
    )
    default_by_name = {field['name']: field for field in default_fields}
    default_order = [field['name'] for field in default_fields]
    entry_fields = [dict(field) for field in definition.get('entry_fields', [])]
    existing_names = {field.get('name') for field in entry_fields}

    for field_name in required_names:
        if field_name in existing_names or field_name not in default_by_name:
            continue
        insertion_index = len(entry_fields)
        found_predecessor = False
        for predecessor in reversed(default_order[:default_order.index(field_name)]):
            for index, field in enumerate(entry_fields):
                if field.get('name') == predecessor:
                    insertion_index = index + 1
                    found_predecessor = True
                    break
            if found_predecessor:
                break
        entry_fields.insert(insertion_index, dict(default_by_name[field_name]))
        existing_names.add(field_name)

    if entry_fields == definition.get('entry_fields', []):
        return definition
    repaired = dict(definition)
    repaired['entry_fields'] = entry_fields
    return repaired

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
        if config is None and base_type != canonical_key:
            config = (
                db.query(WorkshopTemplateConfig)
                .filter(
                    WorkshopTemplateConfig.template_key == base_type,
                    WorkshopTemplateConfig.is_active.is_(True),
                )
                .first()
            )

    definition = _load_template_definition_from_config(config) if config is not None else _load_default_template_definition(base_type)
    definition = _ensure_required_entry_fields(definition, base_type)
    return {
        'template_key': canonical_key,
        'workshop_type': base_type,
        'source_template_key': config.template_key if config is not None else base_type,
        'has_override': config is not None and config.template_key == canonical_key,
        **definition,
    }

def normalize_template_definition_payload(
    template_key: str,
    payload: dict[str, Any],
    *,
    db: Session | None = None,
) -> dict[str, Any]:
    definition = get_workshop_template_definition(template_key, db=db)
    normalized = {
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
    return _ensure_required_entry_fields(normalized, definition['workshop_type'])
