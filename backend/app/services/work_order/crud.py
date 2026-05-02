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


def _apply_work_order_fields(entity: WorkOrder, payload: dict[str, Any], *, user_role: str) -> None:
    for field_name, value in payload.items():
        if field_name == 'tracking_card_no':
            continue
        if value is None:
            continue
        if not check_field_write('work_orders', field_name, user_role):
            raise _http_error(status.HTTP_403_FORBIDDEN, f'cannot modify field {field_name}')
        setattr(entity, field_name, value)

def _recompute_work_order_rollups(db: Session, work_order: WorkOrder) -> None:
    entries = (
        db.query(WorkOrderEntry)
        .filter(WorkOrderEntry.work_order_id == work_order.id)
        .order_by(WorkOrderEntry.business_date.asc(), WorkOrderEntry.id.asc())
        .all()
    )
    if not entries:
        work_order.current_station = None
        work_order.overall_status = 'created'
        work_order.previous_stage_output = None
        return

    latest_entry = max(entries, key=_entry_sort_key)
    latest_workshop = db.get(Workshop, latest_entry.workshop_id)
    work_order.current_station = latest_workshop.name if latest_workshop else str(latest_entry.workshop_id)

    completed_entries = [entry for entry in entries if entry.entry_type == 'completed']
    if completed_entries:
        latest_completed = max(completed_entries, key=_entry_sort_key)
        completed_workshop = db.get(Workshop, latest_completed.workshop_id)
        work_order.previous_stage_output = build_previous_stage_output(
            SimpleNamespace(
                workshop_name=completed_workshop.name if completed_workshop else str(latest_completed.workshop_id),
                verified_output_weight=latest_completed.verified_output_weight,
                output_weight=latest_completed.output_weight,
                output_spec=latest_completed.output_spec,
                approved_at=latest_completed.approved_at,
                verified_at=latest_completed.verified_at,
                submitted_at=latest_completed.submitted_at,
                updated_at=latest_completed.updated_at,
            )
        )
    else:
        work_order.previous_stage_output = None

    if all(entry.entry_type == 'completed' for entry in entries):
        work_order.overall_status = 'completed'
    else:
        work_order.overall_status = 'in_progress'

def _serialize_work_order(
    db: Session,
    entity: WorkOrder,
    *,
    user_role: str,
    entries: list[WorkOrderEntry] | None = None,
) -> dict[str, Any]:
    payload = _model_to_dict(entity)
    payload['contract_weight'] = _to_float(payload.get('contract_weight'))
    payload = mask_table_payload('work_orders', payload, user_role=user_role)
    payload['entries'] = [_serialize_entry(db, item, user_role=user_role) for item in entries or []]
    return payload

def create_work_order(
    db: Session,
    *,
    payload: dict[str, Any],
    operator: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    tracking_card_no = _normalize_tracking_card_no(payload['tracking_card_no'])
    existing = db.query(WorkOrder).filter(WorkOrder.tracking_card_no == tracking_card_no).first()
    if existing is not None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'tracking card already exists')

    entity = WorkOrder(
        tracking_card_no=tracking_card_no,
        process_route_code=parse_process_route_code(tracking_card_no),
        overall_status='created',
        created_by=operator.id,
    )
    _apply_mes_card_info(entity, tracking_card_no=tracking_card_no)
    _apply_work_order_fields(entity, payload, user_role=operator.role)
    db.add(entity)
    db.flush()
    record_entity_change(
        db,
        user=operator,
        module='work_orders',
        entity_type='work_orders',
        entity_id=entity.id,
        action='create',
        new_value=_json_ready(_model_to_dict(entity)),
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    return _serialize_work_order(db, entity, user_role=operator.role)

def update_work_order(
    db: Session,
    *,
    work_order_id: int,
    payload: dict[str, Any],
    operator: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    entity = _ensure_work_order(work_order_id, db)
    _ensure_header_access(db, entity, operator)

    original = _model_to_dict(entity)
    _apply_work_order_fields(entity, payload, user_role=operator.role)
    record_entity_change(
        db,
        user=operator,
        module='work_orders',
        entity_type='work_orders',
        entity_id=entity.id,
        action='update',
        old_value=_json_ready(original),
        new_value=_json_ready(_model_to_dict(entity)),
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    entries = list_entries_for_work_order(db, work_order=entity, current_user=operator)
    return _serialize_work_order(db, entity, user_role=operator.role, entries=entries)

def list_work_orders(
    db: Session,
    *,
    current_user: User,
    workshop_id: int | None = None,
    business_date: date | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    summary = build_scope_summary(current_user)
    bound_machine = get_bound_machine_for_user(db, user_id=current_user.id)
    query = db.query(WorkOrder)
    if status:
        query = query.filter(WorkOrder.overall_status == status)

    visible_work_order_ids = None
    if can_view_all_work_order_headers(summary):
        if workshop_id or business_date:
            entry_query = db.query(WorkOrderEntry.work_order_id).distinct()
            if workshop_id is not None:
                entry_query = entry_query.filter(WorkOrderEntry.workshop_id == workshop_id)
            if business_date is not None:
                entry_query = entry_query.filter(WorkOrderEntry.business_date == business_date)
            if bound_machine is not None:
                entry_query = entry_query.filter(WorkOrderEntry.machine_id == bound_machine.id)
            visible_work_order_ids = [row.work_order_id for row in entry_query.all()]
            query = query.filter(or_(WorkOrder.id.in_(visible_work_order_ids), WorkOrder.created_by == current_user.id))
    else:
        scoped_workshop_id = resolve_work_order_entry_workshop_scope(summary)
        if workshop_id is not None and scoped_workshop_id is not None and workshop_id != scoped_workshop_id:
            raise _http_error(status.HTTP_403_FORBIDDEN, 'workshop scope denied')
        if scoped_workshop_id is None:
            return []
        entry_query = db.query(WorkOrderEntry.work_order_id).distinct().filter(WorkOrderEntry.workshop_id == scoped_workshop_id)
        if business_date is not None:
            entry_query = entry_query.filter(WorkOrderEntry.business_date == business_date)
        if bound_machine is not None:
            entry_query = entry_query.filter(WorkOrderEntry.machine_id == bound_machine.id)
        visible_work_order_ids = [row.work_order_id for row in entry_query.all()]
        query = query.filter(or_(WorkOrder.id.in_(visible_work_order_ids), WorkOrder.created_by == current_user.id))

    rows = query.order_by(WorkOrder.updated_at.desc(), WorkOrder.id.desc()).all()
    return [_serialize_work_order(db, item, user_role=current_user.role) for item in rows]

def get_work_order_by_tracking_card(db: Session, *, tracking_card_no: str, current_user: User) -> dict[str, Any]:
    entity = db.query(WorkOrder).filter(WorkOrder.tracking_card_no == _normalize_tracking_card_no(tracking_card_no)).first()
    if entity is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, 'work order not found')
    _ensure_header_access(db, entity, current_user)
    entries = list_entries_for_work_order(db, work_order=entity, current_user=current_user)
    return _serialize_work_order(db, entity, user_role=current_user.role, entries=entries)

def list_entries_for_work_order(db: Session, *, work_order: WorkOrder, current_user: User) -> list[WorkOrderEntry]:
    summary = build_scope_summary(current_user)
    if not can_view_work_order_entries(summary):
        return []
    query = db.query(WorkOrderEntry).filter(WorkOrderEntry.work_order_id == work_order.id)
    bound_machine = get_bound_machine_for_user(db, user_id=current_user.id)
    workshop_scope = resolve_work_order_entry_workshop_scope(summary)
    if workshop_scope is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_scope)
    if bound_machine is not None:
        query = query.filter(WorkOrderEntry.machine_id == bound_machine.id)
    return query.order_by(WorkOrderEntry.business_date.asc(), WorkOrderEntry.id.asc()).all()
