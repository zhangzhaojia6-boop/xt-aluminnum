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


TRACKING_CARD_PREFIX_RE = re.compile(r'^([0-9A-Z]{1,8}?)(?=(?:\d{4,})|[-_/]|$)')
ENTRY_METADATA_FIELDS = {'machine_id', 'shift_id', 'business_date', 'entry_type'}
JSON_PAYLOAD_FIELDS = {'extra_payload', 'qc_payload'}
ENTRY_LOCKED_STATUSES = {'submitted', 'approved'}
ENTRY_METADATA_ROLE_ALLOWLIST = {'shift_leader', 'contracts', 'inventory_keeper', 'utility_manager'}
OWNER_ONLY_ENTRY_ROLES = {'contracts', 'inventory_keeper', 'utility_manager'}
logger = logging.getLogger(__name__)


def _http_error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _model_to_dict(entity) -> dict[str, Any]:
    if hasattr(entity, '__table__'):
        return {column.name: getattr(entity, column.name) for column in entity.__table__.columns}
    if hasattr(entity, '__dict__'):
        return {key: value for key, value in vars(entity).items() if not key.startswith('_')}
    return {}


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _normalize_override_reason(value: str | None) -> str | None:
    normalized = (value or '').strip()
    return normalized or None


def _normalize_tracking_card_no(value: str) -> str:
    normalized = (value or '').strip().upper()
    if not normalized:
        raise _http_error(status.HTTP_400_BAD_REQUEST, 'tracking_card_no is required')
    return normalized


def _entry_create_idempotency_scope(operator: User) -> str:
    return f'work_order_entry_create:{operator.id}'


def _entry_create_idempotency_fingerprint(*, work_order_id: int, payload: dict[str, Any]) -> str:
    normalized_payload = _json_ready({'work_order_id': work_order_id, 'payload': payload})
    return json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def parse_process_route_code(tracking_card_no: str) -> str:
    normalized = _normalize_tracking_card_no(tracking_card_no)
    match = TRACKING_CARD_PREFIX_RE.match(normalized)
    if match:
        return match.group(1)
    return normalized[:8]


def _lookup_mes_card_info(tracking_card_no: str) -> CardInfo | None:
    try:
        return get_mes_adapter().get_tracking_card_info(tracking_card_no)
    except Exception:  # noqa: BLE001
        logger.warning('MES tracking card lookup failed for %s', tracking_card_no, exc_info=True)
        return None


def _apply_mes_card_info(entity: WorkOrder, *, tracking_card_no: str) -> None:
    card_info = _lookup_mes_card_info(tracking_card_no)
    if card_info is None:
        return
    if card_info.process_route_code:
        entity.process_route_code = card_info.process_route_code
    if card_info.alloy_grade:
        entity.alloy_grade = card_info.alloy_grade


def _push_mes_completion_if_needed(*, work_order: WorkOrder, entry: WorkOrderEntry) -> bool:
    if getattr(work_order, 'overall_status', None) != 'completed':
        return False
    output_weight = _to_float(entry.verified_output_weight)
    if output_weight is None:
        output_weight = _to_float(entry.output_weight)
    try:
        return bool(
            get_mes_adapter().push_completion(
                work_order.tracking_card_no,
                output_weight,
                _to_float(entry.yield_rate),
            )
        )
    except Exception:  # noqa: BLE001
        logger.warning('MES completion push failed for %s', work_order.tracking_card_no, exc_info=True)
        return False


def _calculate_yield_rate(entry: WorkOrderEntry) -> float | None:
    input_weight = _to_float(entry.verified_input_weight) or _to_float(entry.input_weight)
    output_weight = _to_float(entry.verified_output_weight) or _to_float(entry.output_weight)
    if input_weight is None or output_weight is None or input_weight <= 0:
        return None
    return round((output_weight / input_weight) * 100, 4)


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


def _entry_creator_user_id(entry: WorkOrderEntry) -> int | None:
    return getattr(entry, 'created_by_user_id', None) or getattr(entry, 'created_by', None)


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


def _ensure_amendment_approval_access(current_user: User) -> None:
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.is_manager or summary.is_reviewer:
        return
    raise _http_error(status.HTTP_403_FORBIDDEN, 'amendment approval denied')


def _coerce_column_value(model_class, field_name: str, raw_value: Any) -> Any:
    mapper = sa_inspect(model_class)
    column = mapper.columns.get(field_name)
    if column is None:
        raise _http_error(status.HTTP_400_BAD_REQUEST, f'field {field_name} does not exist')
    if raw_value is None:
        return None
    python_type = None
    try:
        python_type = column.type.python_type
    except NotImplementedError:
        python_type = None
    if python_type in {int, float, str, bool}:
        return python_type(raw_value)
    if python_type is Decimal:
        return Decimal(str(raw_value))
    if python_type is date:
        return date.fromisoformat(str(raw_value))
    if python_type is datetime:
        return datetime.fromisoformat(str(raw_value))
    if python_type is time:
        return time.fromisoformat(str(raw_value))
    if python_type in {dict, list}:
        if isinstance(raw_value, str):
            return json.loads(raw_value)
        return raw_value
    return raw_value


def _apply_work_order_fields(entity: WorkOrder, payload: dict[str, Any], *, user_role: str) -> None:
    for field_name, value in payload.items():
        if field_name == 'tracking_card_no':
            continue
        if value is None:
            continue
        if not check_field_write('work_orders', field_name, user_role):
            raise _http_error(status.HTTP_403_FORBIDDEN, f'cannot modify field {field_name}')
        setattr(entity, field_name, value)


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
        *template['extra_fields'],
        *template['qc_fields'],
        *template['readonly_fields'],
    ]
    visible_names = {field['name'] for field in visible_fields if field.get('target') == target}
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
        *template['extra_fields'],
        *template['qc_fields'],
    ]
    editable_names = {field['name'] for field in editable_fields if field.get('target') == target and field.get('editable')}
    unknown = sorted(set(values.keys()) - editable_names)
    if unknown:
        raise _http_error(status.HTTP_403_FORBIDDEN, f'cannot modify template fields: {", ".join(unknown)}')
    return values


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
    payload_fingerprint = _entry_create_idempotency_fingerprint(work_order_id=work_order_id, payload=payload)
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

    _apply_entry_fields(entity, payload, user_role=operator.role, privileged_override=privileged_override)
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
