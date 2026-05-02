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


def _ensure_amendment_approval_access(current_user: User) -> None:
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.is_manager or summary.is_reviewer:
        return
    raise _http_error(status.HTTP_403_FORBIDDEN, 'amendment approval denied')

def request_amendment(db: Session, *, payload: dict[str, Any], operator: User) -> dict[str, Any]:
    table_name = payload['table_name']
    record_id = int(payload['record_id'])
    field_name = payload['field_name']
    if table_name == 'work_orders':
        entity = _ensure_work_order(record_id, db)
        _ensure_header_access(db, entity, operator)
        model_class = WorkOrder
    elif table_name == 'work_order_entries':
        entity = _ensure_entry(record_id, db)
        _ensure_entry_access(entity, operator)
        if not is_field_locked(entity, field_name):
            raise _http_error(status.HTTP_400_BAD_REQUEST, 'field is not locked')
        model_class = WorkOrderEntry
    else:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'unsupported amendment table')

    _coerce_column_value(model_class, field_name, payload.get('new_value'))
    old_value = getattr(entity, field_name, None)
    amendment = FieldAmendment(
        table_name=table_name,
        record_id=record_id,
        field_name=field_name,
        old_value=None if old_value is None else str(old_value),
        new_value=None if payload.get('new_value') is None else str(payload.get('new_value')),
        reason=payload['reason'],
        requested_by=operator.id,
        status='pending',
    )
    db.add(amendment)
    db.flush()
    record_entity_change(
        db,
        user=operator,
        module='work_orders',
        entity_type='field_amendments',
        entity_id=amendment.id,
        action='request',
        new_value={'table_name': table_name, 'record_id': record_id, 'field_name': field_name},
        reason=amendment.reason,
        auto_commit=False,
    )
    db.commit()
    db.refresh(amendment)
    return _model_to_dict(amendment)

def approve_amendment(db: Session, *, amendment_id: int, operator: User) -> dict[str, Any]:
    _ensure_amendment_approval_access(operator)
    amendment = _ensure_amendment(amendment_id, db)
    if amendment.status != 'pending':
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'amendment is not pending')

    if amendment.table_name == 'work_orders':
        entity = _ensure_work_order(amendment.record_id, db)
        model_class = WorkOrder
    elif amendment.table_name == 'work_order_entries':
        entity = _ensure_entry(amendment.record_id, db)
        model_class = WorkOrderEntry
    else:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'unsupported amendment table')

    original_value = getattr(entity, amendment.field_name, None)
    coerced_value = _coerce_column_value(model_class, amendment.field_name, amendment.new_value)
    setattr(entity, amendment.field_name, coerced_value)
    if amendment.table_name == 'work_order_entries':
        entity.yield_rate = _calculate_yield_rate(entity)
        work_order = _ensure_work_order(entity.work_order_id, db)
        _recompute_work_order_rollups(db, work_order)

    amendment.status = 'approved'
    amendment.approved_by = operator.id
    amendment.approved_at = _utcnow()
    record_entity_change(
        db,
        user=operator,
        module='work_orders',
        entity_type=amendment.table_name,
        entity_id=amendment.record_id,
        action='amendment_apply',
        old_value=_json_ready({amendment.field_name: original_value}),
        new_value=_json_ready({amendment.field_name: coerced_value}),
        reason=amendment.reason,
        auto_commit=False,
    )
    record_entity_change(
        db,
        user=operator,
        module='work_orders',
        entity_type='field_amendments',
        entity_id=amendment.id,
        action='approve',
        new_value={'status': amendment.status},
        reason=amendment.reason,
        auto_commit=False,
    )
    db.commit()
    db.refresh(amendment)
    return _model_to_dict(amendment)
