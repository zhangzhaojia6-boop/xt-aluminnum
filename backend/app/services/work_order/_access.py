from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timezone
from decimal import Decimal
import logging
from types import SimpleNamespace
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session
from app.adapters.mes_adapter import CardInfo, get_mes_adapter
from app.core.event_bus import event_bus
from app.core.field_lock import apply_entry_submit, is_field_locked
from app.core.field_permissions import check_field_write, get_readable_fields, normalize_role
from app.core.idempotency import work_order_entry_idempotency_store
from app.core.workflow_events import attach_workflow_event, build_workflow_event
from app.core.scope import (
    build_scope_summary,
    can_view_all_work_order_entries,
    can_view_all_work_order_headers,
    can_view_work_order_entries,
    resolve_work_order_entry_workshop_scope,
)
from app.core.workshop_templates import (
    WORK_ORDER_ENTRY_FIELD_NAMES,
    WORK_ORDER_FIELD_NAMES,
    get_workshop_template,
    resolve_template_key,
    resolve_workshop_type,
)
from app.models.master import Equipment, Workshop
from app.models.production import FieldAmendment, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import ocr_service
from app.services.audit_service import record_entity_change
from app.services.equipment_service import get_bound_machine_for_user


def _ensure_workshop(workshop_id: int, db: Session) -> Workshop:
    workshop = db.get(Workshop, workshop_id)
    if workshop is None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'workshop not found')
    return workshop

def _ensure_machine(machine_id: int | None, *, workshop_id: int, db: Session) -> Equipment | None:
    if machine_id is None:
        return None
    machine = db.get(Equipment, machine_id)
    if machine is None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'machine not found')
    if machine.workshop_id != workshop_id:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'machine does not belong to workshop')
    return machine

def _ensure_shift(shift_id: int | None, db: Session) -> ShiftConfig | None:
    if shift_id is None:
        return None
    shift = db.get(ShiftConfig, shift_id)
    if shift is None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'shift not found')
    return shift

def _ensure_work_order(work_order_id: int, db: Session) -> WorkOrder:
    entity = db.get(WorkOrder, work_order_id)
    if entity is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, 'work order not found')
    return entity

def _ensure_entry(entry_id: int, db: Session) -> WorkOrderEntry:
    entity = db.get(WorkOrderEntry, entry_id)
    if entity is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, 'work order entry not found')
    return entity

def _ensure_amendment(amendment_id: int, db: Session) -> FieldAmendment:
    entity = db.get(FieldAmendment, amendment_id)
    if entity is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, 'field amendment not found')
    return entity

def _ensure_header_access(db: Session, work_order: WorkOrder, current_user: User) -> None:
    summary = build_scope_summary(current_user)
    if can_view_all_work_order_headers(summary):
        return
    if work_order.created_by == current_user.id:
        return
    bound_machine = get_bound_machine_for_user(db, user_id=current_user.id)
    if summary.workshop_id is None:
        raise _http_error(status.HTTP_403_FORBIDDEN, 'work order access denied')
    visible_query = db.query(WorkOrderEntry.id).filter(
        WorkOrderEntry.work_order_id == work_order.id,
        WorkOrderEntry.workshop_id == summary.workshop_id,
    )
    if bound_machine is not None:
        visible_query = visible_query.filter(WorkOrderEntry.machine_id == bound_machine.id)
    visible_entry = visible_query.first()
    if visible_entry is None:
        raise _http_error(status.HTTP_403_FORBIDDEN, 'work order access denied')

def _ensure_entry_access(entry: WorkOrderEntry, current_user: User) -> None:
    summary = build_scope_summary(current_user)
    if not can_view_work_order_entries(summary):
        raise _http_error(status.HTTP_403_FORBIDDEN, 'work order entry access denied')
    if can_view_all_work_order_entries(summary):
        return
    if entry.workshop_id != resolve_work_order_entry_workshop_scope(summary):
        raise _http_error(status.HTTP_403_FORBIDDEN, 'work order entry access denied')

def _ensure_write_target_scope(current_user: User, *, workshop_id: int, shift_id: int | None) -> None:
    summary = build_scope_summary(current_user)
    if getattr(summary, 'is_admin', False) or getattr(summary, 'is_reviewer', False):
        return
    if getattr(summary, 'role', None) and can_view_all_work_order_entries(summary):
        return
    summary_workshop_id = getattr(summary, 'workshop_id', None)
    if summary_workshop_id is None:
        summary_workshop_id = getattr(current_user, 'workshop_id', None)
    if summary_workshop_id is None or int(summary_workshop_id) != int(workshop_id):
        raise _http_error(status.HTTP_403_FORBIDDEN, 'workshop scope denied')
    assigned_shift_ids = getattr(summary, 'assigned_shift_ids', None) or []
    if shift_id is not None and assigned_shift_ids and int(shift_id) not in assigned_shift_ids:
        raise _http_error(status.HTTP_403_FORBIDDEN, 'shift scope denied')

def _ensure_machine_scope(
    db: Session,
    *,
    current_user: User,
    target_machine_id: int | None,
) -> Equipment | None:
    summary = build_scope_summary(current_user)
    if getattr(summary, 'is_admin', False):
        return None
    bound_machine = get_bound_machine_for_user(db, user_id=current_user.id)
    if bound_machine is None:
        return None
    if bound_machine.operational_status != 'running':
        raise _http_error(status.HTTP_403_FORBIDDEN, '该机台已停机')
    if target_machine_id is None or int(target_machine_id) != int(bound_machine.id):
        raise _http_error(status.HTTP_403_FORBIDDEN, '无权操作此机台')
    return bound_machine

def _ensure_entry_write_access(
    db: Session,
    entry: WorkOrderEntry,
    current_user: User,
    *,
    override_reason: str | None = None,
) -> bool:
    _ensure_entry_access(entry, current_user)
    _ensure_machine_scope(db, current_user=current_user, target_machine_id=entry.machine_id)
    _ensure_write_target_scope(current_user, workshop_id=entry.workshop_id, shift_id=entry.shift_id)
    if not get_readable_fields('work_order_entries', current_user.role):
        raise _http_error(status.HTTP_403_FORBIDDEN, 'work order entry access denied')
    summary = build_scope_summary(current_user)
    normalized_reason = _normalize_override_reason(override_reason)
    privileged_override = bool((summary.is_admin or summary.is_reviewer) and normalized_reason)
    creator_user_id = _entry_creator_user_id(entry)
    owner_only_self_update = creator_user_id == getattr(current_user, 'id', None) and normalize_role(current_user.role) in OWNER_ONLY_ENTRY_ROLES

    if creator_user_id is not None and creator_user_id != getattr(current_user, 'id', None):
        if not (summary.is_admin or summary.is_reviewer):
            raise _http_error(status.HTTP_403_FORBIDDEN, 'only the creator or reviewer/admin can modify this entry')
        if normalized_reason is None:
            raise _http_error(status.HTTP_403_FORBIDDEN, 'override_reason is required for non-creator modification')

    if entry.entry_status in ENTRY_LOCKED_STATUSES and not (privileged_override or owner_only_self_update):
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            'submitted or approved entries require reviewer/admin override with reason',
        )
    return privileged_override or owner_only_self_update
