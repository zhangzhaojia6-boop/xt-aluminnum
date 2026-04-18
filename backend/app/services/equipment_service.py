from __future__ import annotations

import re
import secrets
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_password_hash
from app.models.master import Equipment, Workshop
from app.models.system import User
from app.services.audit_service import record_entity_change


VALID_MACHINE_STATUSES = {"running", "stopped", "maintenance"}
VALID_SHIFT_MODES = {"two", "three"}
FIELD_NAME_RE = re.compile(r"[^0-9A-Z_-]+")


def _http_error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


def generate_random_pin(length: int = 6) -> str:
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def _normalize_machine_code(workshop_code: str, code: str) -> str:
    normalized_workshop = FIELD_NAME_RE.sub("", (workshop_code or "").strip().upper())
    normalized_code = FIELD_NAME_RE.sub("", (code or "").strip().upper())
    if not normalized_workshop:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "车间编码无效")
    if not normalized_code:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "机台编码不能为空")
    if normalized_code.startswith(f"{normalized_workshop}-"):
        return normalized_code
    return f"{normalized_workshop}-{normalized_code}"


def _normalize_qr_code(equipment_code: str) -> str:
    return f"XT-{equipment_code}"


def _normalize_shift_mode(value: str | None) -> str:
    mode = (value or "three").strip().lower()
    if mode not in VALID_SHIFT_MODES:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "班制配置无效")
    return mode


def _normalize_assigned_shift_ids(shift_mode: str, assigned_shift_ids: list[int] | None) -> list[int]:
    if assigned_shift_ids:
        normalized = sorted({int(item) for item in assigned_shift_ids})
    elif shift_mode == "three":
        normalized = [1, 2, 3]
    else:
        normalized = [1, 2]

    expected = 3 if shift_mode == "three" else 2
    if len(normalized) != expected:
        raise _http_error(status.HTTP_400_BAD_REQUEST, f"{'三' if expected == 3 else '两'}班制必须配置{expected}个班次")
    return normalized


def _normalize_operational_status(value: str | None) -> str:
    status_value = (value or "stopped").strip().lower()
    if status_value not in VALID_MACHINE_STATUSES:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "机台运行状态无效")
    return status_value


def _normalize_custom_fields(values: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for item in values or []:
        name = FIELD_NAME_RE.sub("_", str(item.get("name") or "").strip().upper()).strip("_").lower()
        label = str(item.get("label") or "").strip()
        field_type = str(item.get("type") or "number").strip().lower() or "number"
        unit = str(item.get("unit") or "").strip()
        if not name or not label:
            continue
        fields.append({"name": name, "label": label, "type": field_type, "unit": unit})
    return fields


def _ensure_workshop(db: Session, workshop_id: int) -> Workshop:
    workshop = db.get(Workshop, workshop_id)
    if workshop is None or not workshop.is_active:
        raise _http_error(status.HTTP_404_NOT_FOUND, "未找到该车间")
    return workshop


def _ensure_equipment(db: Session, equipment_id: int) -> Equipment:
    equipment = db.get(Equipment, equipment_id)
    if equipment is None or not equipment.is_active:
        raise _http_error(status.HTTP_404_NOT_FOUND, "未找到该机台")
    return equipment


def _ensure_unique_machine_identity(
    db: Session,
    *,
    equipment_code: str,
    username: str,
    qr_code: str,
    exclude_equipment_id: int | None = None,
    exclude_user_id: int | None = None,
) -> None:
    equipment_query = db.query(Equipment).filter(Equipment.code == equipment_code)
    if exclude_equipment_id is not None:
        equipment_query = equipment_query.filter(Equipment.id != exclude_equipment_id)
    if equipment_query.first() is not None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "机台编码已存在")

    qr_query = db.query(Equipment).filter(Equipment.qr_code == qr_code)
    if exclude_equipment_id is not None:
        qr_query = qr_query.filter(Equipment.id != exclude_equipment_id)
    if qr_query.first() is not None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "机台二维码已存在")

    user_query = db.query(User).filter(User.username == username)
    if exclude_user_id is not None:
        user_query = user_query.filter(User.id != exclude_user_id)
    if user_query.first() is not None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "机台账号已存在")


def _machine_user_active(operational_status: str) -> bool:
    return operational_status == "running"


def get_bound_machine_for_user(db: Session, *, user_id: int) -> Equipment | None:
    if user_id is None:
        return None
    if not hasattr(db, 'query'):
        return None
    return db.query(Equipment).filter(Equipment.bound_user_id == user_id, Equipment.is_active.is_(True)).first()


def build_machine_info(equipment: Equipment, workshop: Workshop | None = None) -> dict[str, Any]:
    workshop_name = workshop.name if workshop else None
    workshop_id = workshop.id if workshop else equipment.workshop_id
    return {
        "machine_id": equipment.id,
        "machine_code": equipment.code,
        "machine_name": equipment.name,
        "workshop_id": workshop_id,
        "workshop_name": workshop_name,
        "qr_code": equipment.qr_code,
    }


def create_machine_with_account(
    db: Session,
    *,
    workshop_id: int,
    code: str,
    name: str,
    machine_type: str,
    shift_mode: str = "three",
    assigned_shift_ids: list[int] | None = None,
    custom_fields: list[dict[str, Any]] | None = None,
    operational_status: str = "stopped",
    operator: User | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    workshop = _ensure_workshop(db, workshop_id)
    equipment_code = _normalize_machine_code(workshop.code, code)
    username = equipment_code
    qr_code = _normalize_qr_code(equipment_code)
    shift_mode_value = _normalize_shift_mode(shift_mode)
    operational_status_value = _normalize_operational_status(operational_status)
    assigned_shift_value = _normalize_assigned_shift_ids(shift_mode_value, assigned_shift_ids)
    custom_fields_value = _normalize_custom_fields(custom_fields)

    _ensure_unique_machine_identity(db, equipment_code=equipment_code, username=username, qr_code=qr_code)

    equipment = Equipment(
        code=equipment_code,
        name=str(name).strip(),
        workshop_id=workshop.id,
        equipment_type=machine_type,
        operational_status=operational_status_value,
        shift_mode=shift_mode_value,
        assigned_shift_ids=assigned_shift_value,
        custom_fields=custom_fields_value,
        qr_code=qr_code,
        sort_order=0,
        is_active=True,
    )
    db.add(equipment)
    db.flush()

    pin = generate_random_pin(6)
    user = User(
        username=username,
        password_hash=get_password_hash(pin),
        pin_code=pin,
        name=f"{workshop.name} {equipment.name}",
        role="shift_leader",
        workshop_id=workshop.id,
        team_id=None,
        data_scope_type="self_workshop",
        assigned_shift_ids=assigned_shift_value,
        is_mobile_user=True,
        is_reviewer=False,
        is_manager=False,
        is_active=_machine_user_active(operational_status_value),
    )
    db.add(user)
    db.flush()

    equipment.bound_user_id = user.id
    db.flush()

    record_entity_change(
        db,
        user=operator,
        module="master",
        entity_type="equipment",
        entity_id=equipment.id,
        action="create_with_account",
        new_value={
            "code": equipment.code,
            "name": equipment.name,
            "operational_status": equipment.operational_status,
            "shift_mode": equipment.shift_mode,
            "assigned_shift_ids": equipment.assigned_shift_ids,
            "qr_code": equipment.qr_code,
            "bound_user_id": equipment.bound_user_id,
        },
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    record_entity_change(
        db,
        user=operator,
        module="auth",
        entity_type="users",
        entity_id=user.id,
        action="machine_account_create",
        new_value={
            "username": user.username,
            "role": user.role,
            "workshop_id": user.workshop_id,
            "is_active": user.is_active,
        },
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    db.commit()
    db.refresh(equipment)

    return {
        "equipment_id": equipment.id,
        "username": username,
        "pin": pin,
        "qr_code": qr_code,
        "workshop_name": workshop.name,
        "machine_name": equipment.name,
    }


def reset_machine_pin(
    db: Session,
    *,
    equipment_id: int,
    operator: User | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    equipment = _ensure_equipment(db, equipment_id)
    if equipment.bound_user_id is None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "该机台未绑定账号")
    user = db.get(User, equipment.bound_user_id)
    if user is None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "该机台未绑定有效账号")

    old_value = {"pin_code": user.pin_code}
    pin = generate_random_pin(6)
    user.pin_code = pin
    user.password_hash = get_password_hash(pin)
    db.flush()
    record_entity_change(
        db,
        user=operator,
        module="auth",
        entity_type="users",
        entity_id=user.id,
        action="machine_pin_reset",
        old_value=old_value,
        new_value={"pin_code": pin},
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    db.commit()
    return {"username": user.username, "new_pin": pin}


def toggle_machine_status(
    db: Session,
    *,
    equipment_id: int,
    operational_status: str,
    operator: User | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    equipment = _ensure_equipment(db, equipment_id)
    next_status = _normalize_operational_status(operational_status)
    old_status = equipment.operational_status
    equipment.operational_status = next_status
    if equipment.bound_user_id is not None:
        user = db.get(User, equipment.bound_user_id)
        if user is not None:
            user.is_active = _machine_user_active(next_status)
    db.flush()
    record_entity_change(
        db,
        user=operator,
        module="master",
        entity_type="equipment",
        entity_id=equipment.id,
        action="machine_toggle_status",
        old_value={"operational_status": old_status},
        new_value={"operational_status": next_status},
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    db.commit()
    db.refresh(equipment)
    return {
        "id": equipment.id,
        "operational_status": equipment.operational_status,
        "is_active": bool(equipment.bound_user_id and db.get(User, equipment.bound_user_id).is_active)
        if equipment.bound_user_id
        else False,
    }


def update_machine(
    db: Session,
    *,
    equipment_id: int,
    payload: dict[str, Any],
    operator: User | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Equipment:
    equipment = _ensure_equipment(db, equipment_id)
    original = {
        "name": equipment.name,
        "equipment_type": equipment.equipment_type,
        "spec": equipment.spec,
        "shift_mode": equipment.shift_mode,
        "assigned_shift_ids": equipment.assigned_shift_ids,
        "custom_fields": equipment.custom_fields,
        "operational_status": equipment.operational_status,
    }
    if "name" in payload and payload["name"] is not None:
        equipment.name = str(payload["name"]).strip()
    if "equipment_type" in payload:
        equipment.equipment_type = payload["equipment_type"]
    if "spec" in payload:
        equipment.spec = payload["spec"]
    if "custom_fields" in payload:
        equipment.custom_fields = _normalize_custom_fields(payload["custom_fields"])
    if "shift_mode" in payload or "assigned_shift_ids" in payload:
        shift_mode = _normalize_shift_mode(payload.get("shift_mode", equipment.shift_mode))
        assigned_shift_ids = _normalize_assigned_shift_ids(shift_mode, payload.get("assigned_shift_ids"))
        equipment.shift_mode = shift_mode
        equipment.assigned_shift_ids = assigned_shift_ids
        if equipment.bound_user_id is not None:
            user = db.get(User, equipment.bound_user_id)
            if user is not None:
                user.assigned_shift_ids = assigned_shift_ids
    if "operational_status" in payload and payload["operational_status"] is not None:
        next_status = _normalize_operational_status(payload["operational_status"])
        equipment.operational_status = next_status
        if equipment.bound_user_id is not None:
            user = db.get(User, equipment.bound_user_id)
            if user is not None:
                user.is_active = _machine_user_active(next_status)
    db.flush()
    record_entity_change(
        db,
        user=operator,
        module="master",
        entity_type="equipment",
        entity_id=equipment.id,
        action="update",
        old_value=original,
        new_value={
            "name": equipment.name,
            "equipment_type": equipment.equipment_type,
            "spec": equipment.spec,
            "shift_mode": equipment.shift_mode,
            "assigned_shift_ids": equipment.assigned_shift_ids,
            "custom_fields": equipment.custom_fields,
            "operational_status": equipment.operational_status,
        },
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    db.commit()
    db.refresh(equipment)
    return equipment
