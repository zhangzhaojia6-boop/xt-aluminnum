from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.system import AuditLog, User


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def record_audit(
    db: Session,
    *,
    user: User | None,
    action: str,
    module: str,
    entity_type: str,
    entity_id: str | int | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
    auto_commit: bool = True,
) -> AuditLog:
    record_id: int | None = None
    if entity_id is not None:
        try:
            record_id = int(entity_id)
        except (TypeError, ValueError):
            record_id = None

    log = AuditLog(
        user_id=user.id if user else None,
        user_name=user.name if user else "system",
        action=action,
        module=module,
        table_name=entity_type,
        record_id=record_id,
        old_value=None,
        new_value=_json_safe(detail) if detail is not None else None,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    if auto_commit:
        db.commit()
        db.refresh(log)
    else:
        db.flush()
    return log


def log_action(
    db: Session,
    user_id: int | None,
    user_name: str | None,
    action: str,
    module: str,
    table_name: str | None = None,
    record_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
    auto_commit: bool = True,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        user_name=user_name or "system",
        action=action,
        module=module,
        table_name=table_name,
        record_id=record_id,
        old_value=_json_safe(old_value) if old_value is not None else None,
        new_value=_json_safe(new_value) if new_value is not None else None,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    if auto_commit:
        db.commit()
        db.refresh(log)
    else:
        db.flush()
    return log


def record_entity_change(
    db: Session,
    *,
    user: User | None,
    module: str,
    entity_type: str,
    entity_id: int | None,
    action: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
    auto_commit: bool = True,
) -> AuditLog:
    return log_action(
        db,
        user_id=user.id if user else None,
        user_name=user.name if user else "system",
        action=action,
        module=module,
        table_name=entity_type,
        record_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
        reason=reason,
        auto_commit=auto_commit,
    )


def record_status_transition(
    db: Session,
    *,
    user: User | None,
    module: str,
    entity_type: str,
    entity_id: int,
    old_status: str | None,
    new_status: str,
    action: str,
    reason: str | None = None,
    extra: dict | None = None,
    auto_commit: bool = True,
) -> AuditLog:
    payload = {"old_status": old_status, "new_status": new_status}
    if extra:
        payload.update(extra)
    return record_entity_change(
        db,
        user=user,
        module=module,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value={"status": old_status} if old_status is not None else None,
        new_value=payload,
        reason=reason,
        auto_commit=auto_commit,
    )
