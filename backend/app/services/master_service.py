from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.models.master import Employee, Equipment, MasterCodeAlias, Team, Workshop
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.audit_service import record_audit


ENTITY_TABLES = {
    'workshop': Workshop,
    'team': Team,
    'shift': ShiftConfig,
    'equipment': Equipment,
    'employee': Employee,
}


def _normalize_text(value: object | None) -> str:
    if value is None:
        return ''
    return str(value).strip()


def list_aliases(
    db: Session,
    *,
    entity_type: str | None = None,
    source_type: str | None = None,
    is_active: bool | None = None,
) -> list[MasterCodeAlias]:
    query = db.query(MasterCodeAlias)
    if entity_type:
        query = query.filter(MasterCodeAlias.entity_type == entity_type)
    if source_type:
        query = query.filter(MasterCodeAlias.source_type == source_type)
    if is_active is not None:
        query = query.filter(MasterCodeAlias.is_active.is_(is_active))
    return query.order_by(MasterCodeAlias.entity_type.asc(), MasterCodeAlias.id.desc()).all()


def create_alias(
    db: Session,
    *,
    payload: dict,
    operator: User | None,
) -> MasterCodeAlias:
    alias = MasterCodeAlias(**payload)
    db.add(alias)
    db.commit()
    db.refresh(alias)
    record_audit(
        db,
        user=operator,
        action='create_alias',
        module='master',
        entity_type='master_code_aliases',
        entity_id=alias.id,
        detail={'entity_type': alias.entity_type, 'canonical_code': alias.canonical_code, 'alias_code': alias.alias_code},
    )
    return alias


def update_alias(
    db: Session,
    *,
    alias_id: int,
    payload: dict,
    operator: User | None,
) -> MasterCodeAlias:
    alias = db.get(MasterCodeAlias, alias_id)
    if not alias:
        raise ValueError('alias not found')
    for key, value in payload.items():
        setattr(alias, key, value)
    db.commit()
    db.refresh(alias)
    record_audit(
        db,
        user=operator,
        action='update_alias',
        module='master',
        entity_type='master_code_aliases',
        entity_id=alias.id,
        detail={'entity_type': alias.entity_type, 'canonical_code': alias.canonical_code, 'alias_code': alias.alias_code},
    )
    return alias


def delete_alias(
    db: Session,
    *,
    alias_id: int,
    operator: User | None,
) -> None:
    alias = db.get(MasterCodeAlias, alias_id)
    if not alias:
        raise ValueError('alias not found')
    db.delete(alias)
    db.commit()
    record_audit(
        db,
        user=operator,
        action='delete_alias',
        module='master',
        entity_type='master_code_aliases',
        entity_id=alias.id,
        detail={'entity_type': alias.entity_type, 'canonical_code': alias.canonical_code, 'alias_code': alias.alias_code},
    )


def resolve_canonical_code(
    db: Session,
    *,
    entity_type: str,
    value: object | None,
    source_type: str | None = None,
) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None

    model = ENTITY_TABLES.get(entity_type)
    if model is None:
        return None

    if entity_type == 'employee':
        existing = db.query(model).filter(model.employee_no == text).first()
    else:
        existing = db.query(model).filter(model.code == text).first()
    if existing:
        return text

    alias_query = db.query(MasterCodeAlias).filter(
        MasterCodeAlias.entity_type == entity_type,
        MasterCodeAlias.is_active.is_(True),
    )
    if source_type:
        alias_query = alias_query.filter(
            (MasterCodeAlias.source_type == source_type) | (MasterCodeAlias.source_type.is_(None))
        )

    alias = alias_query.filter(MasterCodeAlias.alias_code == text).first()
    if alias:
        return alias.canonical_code

    alias = alias_query.filter(MasterCodeAlias.alias_name == text).first()
    if alias:
        return alias.canonical_code

    return None


def resolve_codes(
    db: Session,
    *,
    entity_type: str,
    values: Iterable[object],
    source_type: str | None = None,
) -> dict[object, str | None]:
    return {value: resolve_canonical_code(db, entity_type=entity_type, value=value, source_type=source_type) for value in values}


def is_valid_code(
    db: Session,
    *,
    entity_type: str,
    code: object | None,
) -> bool:
    text = _normalize_text(code)
    if not text:
        return False
    model = ENTITY_TABLES.get(entity_type)
    if model is None:
        return False
    if entity_type == 'employee':
        return db.query(model).filter(model.employee_no == text).first() is not None
    return db.query(model).filter(model.code == text).first() is not None
