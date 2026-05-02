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


def build_previous_stage_output(entry) -> dict[str, Any] | None:
    if entry is None:
        return None
    completed_at = (
        getattr(entry, 'approved_at', None)
        or getattr(entry, 'verified_at', None)
        or getattr(entry, 'submitted_at', None)
        or getattr(entry, 'completed_at', None)
        or getattr(entry, 'updated_at', None)
    )
    verified_output = _to_float(getattr(entry, 'verified_output_weight', None))
    output_weight = verified_output if verified_output is not None else _to_float(getattr(entry, 'output_weight', None))
    return {
        'workshop': getattr(entry, 'workshop_name', None),
        'output_weight': output_weight,
        'output_spec': getattr(entry, 'output_spec', None),
        'completed_at': completed_at.isoformat() if isinstance(completed_at, datetime) else None,
    }

def split_entry_form_payload(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entry_values: dict[str, Any] = {}
    work_order_values: dict[str, Any] = {}
    extra_values: dict[str, Any] = {}
    qc_values: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if key in {'extra_payload', 'qc_payload'}:
            continue
        if key in WORK_ORDER_FIELD_NAMES:
            work_order_values[key] = value
        elif key in WORK_ORDER_ENTRY_FIELD_NAMES or key in ENTRY_METADATA_FIELDS:
            entry_values[key] = value
        elif key in {'si', 'fe', 'cu', 'mn', 'mg', 'zn', 'ti', 'ga'}:
            qc_values[key] = value
        else:
            extra_values[key] = value
    return {
        'entry_values': entry_values,
        'work_order_values': work_order_values,
        'extra_values': extra_values,
        'qc_values': qc_values,
    }

def mask_table_payload(table: str, payload: dict[str, Any], *, user_role: str) -> dict[str, Any]:
    readable = set(get_readable_fields(table, user_role))
    masked: dict[str, Any] = {}
    for key, value in payload.items():
        masked[key] = value if key in readable else None
    return masked

def filter_entry_payloads_for_scope(entries: list[dict[str, Any]], *, current_user: User) -> list[dict[str, Any]]:
    summary = build_scope_summary(current_user)
    if not can_view_work_order_entries(summary):
        return []
    if can_view_all_work_order_entries(summary):
        return list(entries)
    workshop_scope = resolve_work_order_entry_workshop_scope(summary)
    return [item for item in entries if item.get('workshop_id') == workshop_scope]

def _apply_entry_fields(
    entity: WorkOrderEntry,
    payload: dict[str, Any],
    *,
    user_role: str,
    privileged_override: bool = False,
) -> None:
    normalized_role = normalize_role(user_role)
    for field_name, value in payload.items():
        if field_name in JSON_PAYLOAD_FIELDS:
            if not privileged_override and is_field_locked(entity, field_name):
                raise _http_error(status.HTTP_400_BAD_REQUEST, f'field {field_name} is locked')
            setattr(entity, field_name, value or {})
            continue
        if field_name in {'workshop_id'}:
            continue
        if field_name in ENTRY_METADATA_FIELDS:
            if not privileged_override and normalized_role not in ENTRY_METADATA_ROLE_ALLOWLIST:
                raise _http_error(status.HTTP_403_FORBIDDEN, f'cannot modify field {field_name}')
            if not privileged_override and is_field_locked(entity, field_name):
                raise _http_error(status.HTTP_400_BAD_REQUEST, f'field {field_name} is locked')
            setattr(entity, field_name, value)
            continue
        if not privileged_override and not check_field_write('work_order_entries', field_name, normalized_role):
            raise _http_error(status.HTTP_403_FORBIDDEN, f'cannot modify field {field_name}')
        if not privileged_override and is_field_locked(entity, field_name):
            raise _http_error(status.HTTP_400_BAD_REQUEST, f'field {field_name} is locked')
        setattr(entity, field_name, value)

def _entry_sort_key(entry: WorkOrderEntry) -> tuple:
    return (
        entry.business_date or date.min,
        entry.approved_at or entry.verified_at or entry.submitted_at or entry.updated_at or entry.created_at or datetime.min.replace(tzinfo=timezone.utc),
        entry.id or 0,
    )

def _find_owner_only_entry(
    db: Session,
    *,
    work_order_id: int,
    workshop_id: int,
    shift_id: int | None,
    business_date: date,
) -> WorkOrderEntry | None:
    return (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.work_order_id == work_order_id,
            WorkOrderEntry.workshop_id == workshop_id,
            WorkOrderEntry.shift_id == shift_id,
            WorkOrderEntry.business_date == business_date,
        )
        .order_by(WorkOrderEntry.id.desc())
        .first()
    )

def _resolve_entry_workshop_type(db: Session, entity: WorkOrderEntry) -> str | None:
    # Keep a narrow compatibility shim for tests and callers that patch this symbol.
    if not hasattr(db, 'get'):
        return None
    workshop = db.get(Workshop, entity.workshop_id)
    if workshop is None:
        return None
    return getattr(workshop, 'workshop_type', None)

def _resolve_entry_template_key(db: Session, entity: WorkOrderEntry) -> str | None:
    workshop_type = _resolve_entry_workshop_type(db, entity)
    workshop = db.get(Workshop, entity.workshop_id) if hasattr(db, 'get') else None
    workshop_code = getattr(workshop, 'code', None)
    workshop_name = getattr(workshop, 'name', None)
    if workshop_type is None and workshop_code is None and workshop_name is None:
        return None
    try:
        return resolve_template_key(
            workshop_type=workshop_type,
            workshop_code=workshop_code,
            workshop_name=workshop_name,
        )[0]
    except HTTPException:
        return None

def _filter_template_payload_values(
    payload: dict[str, Any] | None,
    *,
    template_key: str | None,
    db: Session,
    user_role: str,
    target: str,
) -> dict[str, Any]:
    values = payload or {}
    if not values or template_key is None:
        return values
    template = get_workshop_template(template_key, user_role=user_role, db=db)
    visible_fields = [
        *template['entry_fields'],
        *template.get('shift_fields', []),
        *template['extra_fields'],
        *template['qc_fields'],
        *template['readonly_fields'],
    ]
    visible_names = {field['name'] for field in visible_fields if field.get('target') == target}
    visible_names.add('machine_energy_records')
    return {key: value for key, value in values.items() if key in visible_names}

def _normalize_template_section_payload(
    payload: dict[str, Any] | None,
    *,
    template_key: str | None,
    db: Session,
    user_role: str,
    target: str,
) -> dict[str, Any]:
    values = payload or {}
    if not values:
        return {}
    if template_key is None:
        return values
    template = get_workshop_template(template_key, user_role=user_role, db=db)
    editable_fields = [
        *template['entry_fields'],
        *template.get('shift_fields', []),
        *template['extra_fields'],
        *template['qc_fields'],
    ]
    editable_names = {field['name'] for field in editable_fields if field.get('target') == target and field.get('editable')}
    editable_names.add('machine_energy_records')
    unknown = sorted(set(values.keys()) - editable_names)
    if unknown:
        raise _http_error(status.HTTP_403_FORBIDDEN, f'cannot modify template fields: {", ".join(unknown)}')
    return values

def _readonly_fields_by_target(
    db: Session,
    template_key: str | None,
    user_role: str,
) -> dict[str, set[str]]:
    if not template_key:
        return {}
    template = get_workshop_template(template_key, user_role=user_role, db=db)
    readonly_names: dict[str, set[str]] = {
        'entry': set(),
        'shift': set(),
        'extra': set(),
        'qc': set(),
        'work_order': set(),
    }
    for field in template.get('readonly_fields', []):
        target = field.get('target')
        field_name = field.get('name')
        if target and field_name:
            readonly_names.setdefault(target, set()).add(field_name)
    return readonly_names

def _strip_readonly_payload_fields(
    payload: dict[str, Any],
    *,
    db: Session,
    user_role: str,
    template_key: str | None,
) -> dict[str, Any]:
    if not payload:
        return {}
    readonly_fields = _readonly_fields_by_target(db, template_key=template_key, user_role=user_role)
    if not readonly_fields:
        return dict(payload)

    sanitized = dict(payload)

    for field_name in set(sanitized.keys()) & set(readonly_fields.get('entry', set())):
        sanitized.pop(field_name, None)

    if 'extra_payload' in sanitized and isinstance(sanitized.get('extra_payload'), dict):
        extra_payload = dict(sanitized['extra_payload'])
        for field_name in set(extra_payload.keys()) & set(readonly_fields.get('extra', set())):
            extra_payload.pop(field_name, None)
        sanitized['extra_payload'] = extra_payload
    if 'qc_payload' in sanitized and isinstance(sanitized.get('qc_payload'), dict):
        qc_payload = dict(sanitized['qc_payload'])
        for field_name in set(qc_payload.keys()) & set(readonly_fields.get('qc', set())):
            qc_payload.pop(field_name, None)
        sanitized['qc_payload'] = qc_payload

    return sanitized

def _recalculate_readonly_derived_fields(
    db: Session,
    entity: WorkOrderEntry,
    *,
    template_key: str | None,
    user_role: str,
) -> None:
    if not template_key:
        return
    template = get_workshop_template(template_key, user_role=user_role, db=db)
    for field in template.get('readonly_fields', []):
        name = field.get('name')
        compute = field.get('compute')
        target = field.get('target')
        if not name or not compute:
            continue
        if target == 'work_order':
            continue
        if target == 'entry':
            if name == 'yield_rate':
                entity.yield_rate = _calculate_yield_rate(entity)
                continue
            computed = _safe_decimal_compute(
                compute,
                context={
                    'input_weight': _to_float(entity.verified_input_weight) or _to_float(entity.input_weight),
                    'output_weight': _to_float(entity.verified_output_weight) or _to_float(entity.output_weight),
                    'spool_weight': _to_float(entity.spool_weight),
                },
            )
            if computed is None:
                continue
            setattr(entity, name, computed)
            continue

        if target in {'extra', 'qc'}:
            raw_payload = getattr(entity, f'{target}_payload', None) or {}
            if not isinstance(raw_payload, dict):
                raw_payload = {}

            context = {
                'input_weight': _to_float(entity.verified_input_weight) or _to_float(entity.input_weight),
                'output_weight': _to_float(entity.verified_output_weight) or _to_float(entity.output_weight),
                'spool_weight': _to_float(entity.spool_weight),
            }
            context.update(raw_payload)

            computed = _safe_decimal_compute(compute, context=context)
            if computed is None:
                continue

            raw_payload[name] = computed
            setattr(entity, f'{target}_payload', raw_payload)

def _safe_decimal_compute(expression: str, *, context: dict[str, Any]) -> float | None:
    if expression == 'output_weight / input_weight * 100':
        output_weight = context.get('output_weight')
        input_weight = context.get('input_weight')
        if output_weight is None or input_weight in (None, 0):
            return None
        return round((float(output_weight) / float(input_weight)) * 100, 4)

    if expression == 'input_weight - output_weight - spool_weight':
        output_weight = context.get('output_weight')
        input_weight = context.get('input_weight')
        spool_weight = context.get('spool_weight') or 0
        if output_weight is None or input_weight is None:
            return None
        return round(float(input_weight) - float(output_weight) - float(spool_weight), 4)

    if expression == 'finished_inventory_weight - consignment_weight':
        finished_inventory_weight = context.get('finished_inventory_weight')
        consignment_weight = context.get('consignment_weight')
        if finished_inventory_weight is None or consignment_weight is None:
            return None
        return round(float(finished_inventory_weight) - float(consignment_weight), 4)

    return None

def _serialize_entry(db: Session, entity: WorkOrderEntry, *, user_role: str) -> dict[str, Any]:
    payload = _model_to_dict(entity)
    payload['yield_rate'] = _to_float(payload.get('yield_rate'))
    payload['input_weight'] = _to_float(payload.get('input_weight'))
    payload['output_weight'] = _to_float(payload.get('output_weight'))
    payload['verified_input_weight'] = _to_float(payload.get('verified_input_weight'))
    payload['verified_output_weight'] = _to_float(payload.get('verified_output_weight'))
    payload['scrap_weight'] = _to_float(payload.get('scrap_weight'))
    payload['spool_weight'] = _to_float(payload.get('spool_weight'))
    payload['energy_kwh'] = _to_float(payload.get('energy_kwh'))
    payload['gas_m3'] = _to_float(payload.get('gas_m3'))
    template_key = _resolve_entry_template_key(db, entity)
    payload['extra_payload'] = _filter_template_payload_values(
        payload.get('extra_payload'),
        template_key=template_key,
        db=db,
        user_role=user_role,
        target='extra',
    )
    payload['qc_payload'] = _filter_template_payload_values(
        payload.get('qc_payload'),
        template_key=template_key,
        db=db,
        user_role=user_role,
        target='qc',
    )
    creator_user_id = payload.get('created_by_user_id') or payload.get('created_by')
    creator = db.get(User, creator_user_id) if creator_user_id else None
    payload['created_by_user_id'] = creator_user_id
    payload['created_by_user_name'] = creator.name if creator else None
    payload['locked_fields'] = payload.get('locked_fields') or []
    return mask_table_payload('work_order_entries', payload, user_role=user_role)

def _build_entry_event_payload(
    db: Session,
    *,
    entity: WorkOrderEntry,
    work_order: WorkOrder,
    user_role: str,
    actor: User | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    normalized_role = normalize_role(user_role)
    workshop = db.get(Workshop, entity.workshop_id) if hasattr(db, 'get') else None
    machine = db.get(Equipment, entity.machine_id) if entity.machine_id and hasattr(db, 'get') else None
    shift = db.get(ShiftConfig, entity.shift_id) if entity.shift_id and hasattr(db, 'get') else None
    input_weight = _to_float(entity.verified_input_weight)
    if input_weight is None:
        input_weight = _to_float(entity.input_weight)
    output_weight = _to_float(entity.verified_output_weight)
    if output_weight is None:
        output_weight = _to_float(entity.output_weight)

    base_payload = {
        'tracking_card_no': work_order.tracking_card_no,
        'work_order_id': work_order.id,
        'entry_id': entity.id,
        'business_date': entity.business_date.isoformat() if entity.business_date else None,
        'workshop_id': entity.workshop_id,
        'machine_id': entity.machine_id,
        'shift_id': entity.shift_id,
        'workshop': workshop.name if workshop else str(entity.workshop_id),
        'machine': machine.name if machine else (str(entity.machine_id) if entity.machine_id else None),
        'shift': shift.name if shift else (str(entity.shift_id) if entity.shift_id else None),
        'entry_status': entity.entry_status,
        'entry_type': entity.entry_type,
        'input_weight': input_weight,
        'output_weight': output_weight,
        'scrap_weight': _to_float(entity.scrap_weight),
        'yield_rate': _to_float(entity.yield_rate),
    }

    if entity.entry_status == 'submitted':
        workflow_event = build_workflow_event(
            event_type='entry_submitted',
            actor_role=normalized_role,
            actor_id=getattr(actor, 'id', None),
            scope_type='machine' if entity.machine_id else 'workshop',
            workshop_id=entity.workshop_id,
            team_id=None,
            shift_id=entity.shift_id,
            entity_type='work_order_entry',
            entity_id=entity.id,
            status=entity.entry_status,
            payload={
                'tracking_card_no': work_order.tracking_card_no,
                'entry_type': entity.entry_type,
                'machine_id': entity.machine_id,
                'business_date': base_payload['business_date'],
            },
            occurred_at=_utcnow(),
        )
        return 'entry_submitted', attach_workflow_event(base_payload, workflow_event)
    if normalized_role == 'weigher' and entity.entry_status in {'verified', 'approved'}:
        return 'entry_verified', {
            **base_payload,
            'verification_status': entity.entry_status,
        }
    return None, None

def _build_entry_saved_event_payload(
    db: Session,
    *,
    entity: WorkOrderEntry,
    work_order: WorkOrder,
    operator: User,
) -> dict[str, Any]:
    workshop = db.get(Workshop, entity.workshop_id) if hasattr(db, 'get') else None
    machine = db.get(Equipment, entity.machine_id) if entity.machine_id and hasattr(db, 'get') else None
    shift = db.get(ShiftConfig, entity.shift_id) if entity.shift_id and hasattr(db, 'get') else None
    base_payload = {
        'tracking_card_no': getattr(work_order, 'tracking_card_no', None),
        'work_order_id': work_order.id,
        'entry_id': entity.id,
        'business_date': entity.business_date.isoformat() if entity.business_date else None,
        'workshop_id': entity.workshop_id,
        'machine_id': entity.machine_id,
        'shift_id': entity.shift_id,
        'workshop': workshop.name if workshop else str(entity.workshop_id),
        'machine': machine.name if machine else (str(entity.machine_id) if entity.machine_id else None),
        'shift': shift.name if shift else (str(entity.shift_id) if entity.shift_id else None),
        'entry_status': entity.entry_status,
        'entry_type': entity.entry_type,
    }
    workflow_event = build_workflow_event(
        event_type='entry_saved',
        actor_role=normalize_role(operator.role),
        actor_id=getattr(operator, 'id', None),
        scope_type='machine' if entity.machine_id else 'workshop',
        workshop_id=entity.workshop_id,
        team_id=None,
        shift_id=entity.shift_id,
        entity_type='work_order_entry',
        entity_id=entity.id,
        status=entity.entry_status,
        payload={
            'tracking_card_no': getattr(work_order, 'tracking_card_no', None),
            'entry_type': entity.entry_type,
            'machine_id': entity.machine_id,
            'business_date': base_payload['business_date'],
        },
        occurred_at=_utcnow(),
    )
    return attach_workflow_event(base_payload, workflow_event)

def add_entry(
    db: Session,
    *,
    work_order_id: int,
    payload: dict[str, Any],
    operator: User,
    idempotency_key: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    work_order = _ensure_work_order(work_order_id, db)
    _ensure_header_access(db, work_order, operator)
    ocr_submission_id = payload.pop('ocr_submission_id', None)
    idempotency_scope = _entry_create_idempotency_scope(operator)

    if idempotency_key:
        cached = work_order_entry_idempotency_store.get(scope=idempotency_scope, key=idempotency_key)
        if cached is not None:
            try:
                existing_entry = _ensure_entry(int(cached.value['entry_id']), db)
            except HTTPException:
                work_order_entry_idempotency_store.delete(scope=idempotency_scope, key=idempotency_key)
            else:
                _ensure_entry_access(existing_entry, operator)
                return _serialize_entry(db, existing_entry, user_role=operator.role)

    bound_machine = _ensure_machine_scope(db, current_user=operator, target_machine_id=payload.get('machine_id'))
    if bound_machine is not None:
        payload['machine_id'] = bound_machine.id
        payload['workshop_id'] = bound_machine.workshop_id

    workshop_id = int(payload['workshop_id'])
    summary = build_scope_summary(operator)
    workshop_scope = resolve_work_order_entry_workshop_scope(summary)
    if workshop_scope is None:
        raise _http_error(status.HTTP_403_FORBIDDEN, 'work order entry access denied')
    if workshop_scope is not None and not can_view_all_work_order_entries(summary) and workshop_id != workshop_scope:
        raise _http_error(status.HTTP_403_FORBIDDEN, 'workshop scope denied')
    _ensure_write_target_scope(operator, workshop_id=workshop_id, shift_id=payload.get('shift_id'))

    workshop = _ensure_workshop(workshop_id, db)
    template_key = resolve_template_key(
        workshop_type=getattr(workshop, 'workshop_type', None),
        workshop_code=workshop.code,
        workshop_name=workshop.name,
    )[0]
    _ensure_machine(payload.get('machine_id'), workshop_id=workshop_id, db=db)
    _ensure_shift(payload.get('shift_id'), db)
    payload['extra_payload'] = _normalize_template_section_payload(
        payload.get('extra_payload'),
        template_key=template_key,
        db=db,
        user_role=operator.role,
        target='extra',
    )
    payload['qc_payload'] = _normalize_template_section_payload(
        payload.get('qc_payload'),
        template_key=template_key,
        db=db,
        user_role=operator.role,
        target='qc',
    )
    payload = _strip_readonly_payload_fields(
        payload,
        db=db,
        user_role=operator.role,
        template_key=template_key,
    )
    payload_fingerprint = _entry_create_idempotency_fingerprint(work_order_id=work_order_id, payload=payload)

    normalized_role = normalize_role(operator.role)
    if normalized_role in OWNER_ONLY_ENTRY_ROLES:
        existing_owner_entry = _find_owner_only_entry(
            db,
            work_order_id=work_order.id,
            workshop_id=workshop.id,
            shift_id=payload.get('shift_id'),
            business_date=payload['business_date'],
        )
        if existing_owner_entry is not None:
            original = _model_to_dict(existing_owner_entry)
            allow_locked_update = (
                _entry_creator_user_id(existing_owner_entry) == getattr(operator, 'id', None)
                and existing_owner_entry.entry_status in ENTRY_LOCKED_STATUSES
            )
            _apply_entry_fields(
                existing_owner_entry,
                payload,
                user_role=operator.role,
                privileged_override=allow_locked_update,
            )
            _recalculate_readonly_derived_fields(
                db,
                existing_owner_entry,
                template_key=template_key,
                user_role=operator.role,
            )
            existing_owner_entry.yield_rate = _calculate_yield_rate(existing_owner_entry)
            record_entity_change(
                db,
                user=operator,
                module='work_orders',
                entity_type='work_order_entries',
                entity_id=existing_owner_entry.id,
                action='update',
                old_value=_json_ready(original),
                new_value=_json_ready(_model_to_dict(existing_owner_entry)),
                ip_address=ip_address,
                user_agent=user_agent,
                auto_commit=False,
            )
            db.commit()
            db.refresh(existing_owner_entry)
            return _serialize_entry(db, existing_owner_entry, user_role=operator.role)

    entity = WorkOrderEntry(
        work_order_id=work_order.id,
        workshop_id=workshop.id,
        machine_id=payload.get('machine_id'),
        shift_id=payload.get('shift_id'),
        business_date=payload['business_date'],
        entry_type=payload.get('entry_type') or 'in_progress',
        entry_status='draft',
        created_by=operator.id,
        created_by_user_id=operator.id,
        locked_fields=[],
    )
    _apply_entry_fields(entity, payload, user_role=operator.role)
    _recalculate_readonly_derived_fields(
        db,
        entity,
        template_key=template_key,
        user_role=operator.role,
    )
    entity.yield_rate = _calculate_yield_rate(entity)
    db.add(entity)
    db.flush()
    if ocr_submission_id is not None:
        ocr_service.link_submission_to_entry(db, submission_id=int(ocr_submission_id), entry_id=entity.id, operator=operator)
    work_order.current_station = workshop.name
    work_order.overall_status = 'in_progress'
    record_entity_change(
        db,
        user=operator,
        module='work_orders',
        entity_type='work_order_entries',
        entity_id=entity.id,
        action='create',
        new_value=_json_ready(_model_to_dict(entity)),
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    db.refresh(work_order)
    if idempotency_key:
        work_order_entry_idempotency_store.put(
            scope=idempotency_scope,
            key=idempotency_key,
            fingerprint=payload_fingerprint,
            value={'entry_id': entity.id},
        )
    event_bus.publish(
        'entry_saved',
        _build_entry_saved_event_payload(db, entity=entity, work_order=work_order, operator=operator),
    )
    return _serialize_entry(db, entity, user_role=operator.role)

def update_entry(
    db: Session,
    *,
    entry_id: int,
    payload: dict[str, Any],
    operator: User,
    override_reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    entity = _ensure_entry(entry_id, db)
    override_reason = _normalize_override_reason(override_reason or payload.pop('override_reason', None))
    privileged_override = _ensure_entry_write_access(db, entity, operator, override_reason=override_reason)

    original = _model_to_dict(entity)
    template_key = _resolve_entry_template_key(db, entity)
    if 'machine_id' in payload:
        _ensure_machine(payload.get('machine_id'), workshop_id=entity.workshop_id, db=db)
    if 'shift_id' in payload:
        _ensure_shift(payload.get('shift_id'), db)
    _ensure_write_target_scope(
        operator,
        workshop_id=entity.workshop_id,
        shift_id=payload.get('shift_id', entity.shift_id),
    )
    if 'extra_payload' in payload:
        payload['extra_payload'] = _normalize_template_section_payload(
            payload.get('extra_payload'),
            template_key=template_key,
            db=db,
            user_role=operator.role,
            target='extra',
        )
    if 'qc_payload' in payload:
        payload['qc_payload'] = _normalize_template_section_payload(
            payload.get('qc_payload'),
            template_key=template_key,
            db=db,
            user_role=operator.role,
            target='qc',
        )
    payload = _strip_readonly_payload_fields(
        payload,
        db=db,
        user_role=operator.role,
        template_key=template_key,
    )

    _apply_entry_fields(entity, payload, user_role=operator.role, privileged_override=privileged_override)
    _recalculate_readonly_derived_fields(
        db,
        entity,
        template_key=template_key,
        user_role=operator.role,
    )
    if normalize_role(operator.role) == 'weigher':
        entity.weigher_user_id = operator.id
        entity.weighed_at = entity.weighed_at or _utcnow()
    if normalize_role(operator.role) == 'qc':
        entity.qc_user_id = operator.id
        entity.qc_at = entity.qc_at or _utcnow()

    entity.yield_rate = _calculate_yield_rate(entity)
    work_order = _ensure_work_order(entity.work_order_id, db)
    _recompute_work_order_rollups(db, work_order)
    record_entity_change(
        db,
        user=operator,
        module='work_orders',
        entity_type='work_order_entries',
        entity_id=entity.id,
        action='update',
        old_value=_json_ready(original),
        new_value=_json_ready(_model_to_dict(entity)),
        ip_address=ip_address,
        user_agent=user_agent,
        reason=override_reason,
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    event_bus.publish(
        'entry_saved',
        _build_entry_saved_event_payload(db, entity=entity, work_order=work_order, operator=operator),
    )
    return _serialize_entry(db, entity, user_role=operator.role)

def submit_entry(
    db: Session,
    *,
    entry_id: int,
    operator: User,
    override_reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    entity = _ensure_entry(entry_id, db)
    override_reason = _normalize_override_reason(override_reason)
    _ensure_entry_write_access(db, entity, operator, override_reason=override_reason)

    original = _model_to_dict(entity)
    try:
        apply_entry_submit(entity, user_role=operator.role)
    except ValueError as exc:
        raise _http_error(status.HTTP_403_FORBIDDEN, str(exc))
    if normalize_role(operator.role) == 'weigher':
        entity.weigher_user_id = operator.id
        entity.weighed_at = entity.verified_at or entity.weighed_at or _utcnow()
    if normalize_role(operator.role) == 'qc':
        entity.qc_user_id = operator.id
        entity.qc_at = entity.approved_at or entity.qc_at or _utcnow()

    entity.yield_rate = _calculate_yield_rate(entity)
    work_order = _ensure_work_order(entity.work_order_id, db)
    _recompute_work_order_rollups(db, work_order)
    record_entity_change(
        db,
        user=operator,
        module='work_orders',
        entity_type='work_order_entries',
        entity_id=entity.id,
        action='submit',
        old_value=_json_ready(original),
        new_value=_json_ready(_model_to_dict(entity)),
        ip_address=ip_address,
        user_agent=user_agent,
        reason=override_reason,
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    event_type, event_payload = _build_entry_event_payload(
        db,
        entity=entity,
        work_order=work_order,
        user_role=operator.role,
        actor=operator,
    )
    if event_type and event_payload:
        event_bus.publish(event_type, event_payload)
    _push_mes_completion_if_needed(work_order=work_order, entry=entity)
    return _serialize_entry(db, entity, user_role=operator.role)
