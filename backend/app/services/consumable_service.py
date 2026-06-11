from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.templates import MACHINE_OPERATOR_CONSUMABLE_FIELDS
from app.core.templates.resolver import resolve_workshop_type
from app.models.consumable import DailyConsumableLog
from app.models.master import Workshop
from app.models.system import User


WORKSHOPS_WITH_CONSUMABLES = list(MACHINE_OPERATOR_CONSUMABLE_FIELDS.keys())

INGOT_DAILY_FIELDS = [
    {
        'name': 'ingot_block_count',
        'label': '铸锭块数',
        'type': 'number',
        'unit': '块',
        'required': False,
        'role_write': ['consumable_stat'],
        'role_read': ['consumable_stat', 'admin', 'manager'],
    },
    {
        'name': 'ingot_input_tons',
        'label': '铸锭投料量',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['consumable_stat'],
        'role_read': ['consumable_stat', 'admin', 'manager'],
    },
    {
        'name': 'ingot_output_tons',
        'label': '铸锭下机量',
        'type': 'number',
        'unit': '吨',
        'required': False,
        'role_write': ['consumable_stat'],
        'role_read': ['consumable_stat', 'admin', 'manager'],
    },
    {
        'name': 'ingot_exception_note',
        'label': '异常说明',
        'type': 'text',
        'required': False,
        'role_write': ['consumable_stat'],
        'role_read': ['consumable_stat', 'admin', 'manager'],
    },
]


def get_consumable_fields(workshop_type: str) -> list[dict[str, Any]]:
    return MACHINE_OPERATOR_CONSUMABLE_FIELDS.get(workshop_type, [])


def _is_ingot_workshop(workshop: Workshop) -> bool:
    code = str(workshop.code or '').upper()
    name = str(workshop.name or '')
    return code == 'ZD' or '铸锭' in name


def get_consumable_fields_for_workshop(workshop: Workshop, workshop_type: str) -> list[dict[str, Any]]:
    fields = [dict(field) for field in get_consumable_fields(workshop_type)]
    if _is_ingot_workshop(workshop):
        fields.extend(dict(field) for field in INGOT_DAILY_FIELDS)
    return fields


def list_workshops_with_consumables(db: Session) -> list[dict[str, Any]]:
    workshops = (
        db.query(Workshop)
        .filter(Workshop.is_active.is_(True))
        .order_by(Workshop.code)
        .all()
    )
    items: list[dict[str, Any]] = []
    for ws in workshops:
        try:
            ws_type = resolve_workshop_type(
                workshop_type=None,
                workshop_code=ws.code,
                workshop_name=ws.name,
            )
        except HTTPException:
            continue
        fields = get_consumable_fields_for_workshop(ws, ws_type)
        if not fields:
            continue
        items.append({
            'workshop_id': ws.id,
            'workshop_code': ws.code,
            'workshop_name': ws.name,
            'workshop_type': ws_type,
            'fields': fields,
        })
    return items


def _resolve_workshop_or_404(db: Session, workshop_id: int) -> Workshop:
    workshop = db.query(Workshop).filter(Workshop.id == workshop_id).first()
    if workshop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='workshop not found')
    return workshop


def get_daily_log(
    db: Session,
    *,
    workshop_id: int,
    business_date: date,
) -> dict[str, Any]:
    workshop = _resolve_workshop_or_404(db, workshop_id)
    workshop_type = resolve_workshop_type(
        workshop_type=None,
        workshop_code=workshop.code,
        workshop_name=workshop.name,
    )
    fields = get_consumable_fields_for_workshop(workshop, workshop_type)
    if not fields:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='workshop has no consumables')

    log = (
        db.query(DailyConsumableLog)
        .filter(
            DailyConsumableLog.workshop_id == workshop_id,
            DailyConsumableLog.business_date == business_date,
        )
        .first()
    )

    return {
        'workshop_id': workshop.id,
        'workshop_code': workshop.code,
        'workshop_name': workshop.name,
        'workshop_type': workshop_type,
        'business_date': business_date.isoformat(),
        'fields': fields,
        'payload': dict(log.payload or {}) if log else {},
        'note': log.note if log else None,
        'updated_at': log.updated_at.isoformat() if log and log.updated_at else None,
        'updated_by_user_id': log.updated_by_user_id if log else None,
    }


def upsert_daily_log(
    db: Session,
    *,
    workshop_id: int,
    business_date: date,
    payload: dict[str, Any],
    note: str | None,
    current_user: User,
) -> dict[str, Any]:
    workshop = _resolve_workshop_or_404(db, workshop_id)
    workshop_type = resolve_workshop_type(
        workshop_type=None,
        workshop_code=workshop.code,
        workshop_name=workshop.name,
    )
    fields = get_consumable_fields_for_workshop(workshop, workshop_type)
    if not fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='workshop has no consumables')

    allowed = {f['name'] for f in fields}
    cleaned: dict[str, Any] = {}
    for key, value in (payload or {}).items():
        if key not in allowed:
            continue
        if value in (None, ''):
            continue
        cleaned[key] = value

    log = (
        db.query(DailyConsumableLog)
        .filter(
            DailyConsumableLog.workshop_id == workshop_id,
            DailyConsumableLog.business_date == business_date,
        )
        .first()
    )
    if log is None:
        log = DailyConsumableLog(
            workshop_id=workshop_id,
            workshop_type=workshop_type,
            business_date=business_date,
            payload=cleaned,
            note=note,
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id,
        )
        db.add(log)
    else:
        log.workshop_type = workshop_type
        log.payload = cleaned
        log.note = note
        log.updated_by_user_id = current_user.id

    db.commit()
    db.refresh(log)

    return {
        'workshop_id': workshop.id,
        'workshop_code': workshop.code,
        'workshop_name': workshop.name,
        'workshop_type': workshop_type,
        'business_date': business_date.isoformat(),
        'fields': fields,
        'payload': dict(log.payload or {}),
        'note': log.note,
        'updated_at': log.updated_at.isoformat() if log.updated_at else None,
        'updated_by_user_id': log.updated_by_user_id,
    }
