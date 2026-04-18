from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.workshop_templates import (
    NUMERIC_FIELD_NAMES,
    TIME_FIELD_NAMES,
    WORK_ORDER_ENTRY_FIELD_NAMES,
    WORK_ORDER_FIELD_NAMES,
    WORKSHOP_TEMPLATES,
    WORKSHOP_TYPE_ALIASES,
    WORKSHOP_TYPE_BY_WORKSHOP_CODE,
    get_workshop_template,
    get_workshop_template_definition,
    normalize_workshop_type,
    normalize_template_definition_payload,
    normalize_template_key,
    resolve_workshop_type,
    resolve_template_key,
)
from app.models.master import WorkshopTemplateConfig

__all__ = [
    'NUMERIC_FIELD_NAMES',
    'TIME_FIELD_NAMES',
    'WORK_ORDER_ENTRY_FIELD_NAMES',
    'WORK_ORDER_FIELD_NAMES',
    'WORKSHOP_TEMPLATES',
    'WORKSHOP_TYPE_ALIASES',
    'WORKSHOP_TYPE_BY_WORKSHOP_CODE',
    'get_workshop_template',
    'get_workshop_template_definition',
    'normalize_workshop_type',
    'normalize_template_definition_payload',
    'normalize_template_key',
    'resolve_workshop_type',
    'resolve_template_key',
    'upsert_workshop_template_config',
]


def upsert_workshop_template_config(
    db: Session,
    *,
    template_key: str,
    payload: dict,
) -> WorkshopTemplateConfig:
    canonical_key, _base_type = resolve_template_key(template_key=template_key)
    definition = normalize_template_definition_payload(canonical_key, payload, db=db)

    item = (
        db.query(WorkshopTemplateConfig)
        .filter(WorkshopTemplateConfig.template_key == canonical_key)
        .first()
    )
    if item is None:
        item = WorkshopTemplateConfig(template_key=canonical_key)
        db.add(item)

    item.display_name = definition['display_name']
    item.tempo = definition['tempo']
    item.supports_ocr = definition['supports_ocr']
    item.entry_fields = definition['entry_fields']
    item.extra_fields = definition['extra_fields']
    item.qc_fields = definition['qc_fields']
    item.readonly_fields = definition['readonly_fields']
    item.is_active = True
    db.commit()
    db.refresh(item)
    return item
