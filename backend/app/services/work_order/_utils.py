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

FLOW_PAYLOAD_FIELDS = {
    'previous_workshop',
    'previous_process',
    'current_workshop',
    'current_process',
    'next_workshop',
    'next_process',
    'flow_source',
    'flow_confirmed_at',
}

ENTRY_LOCKED_STATUSES = {'submitted', 'approved'}

ENTRY_METADATA_ROLE_ALLOWLIST = {'shift_leader', 'contracts', 'inventory_keeper', 'utility_manager', 'energy_stat'}

OWNER_ONLY_ENTRY_ROLES = {'contracts', 'inventory_keeper', 'utility_manager', 'energy_stat'}

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


def _clean_flow_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_flow_source(value: Any) -> str:
    source = str(value or '').strip()
    if source in {'manual', 'manual_pending_match'}:
        return 'manual_pending_match'
    return source or 'mes_projection'


def _normalize_flow_payload(value: Any) -> dict[str, Any]:
    if value in (None, ''):
        return {}
    if not isinstance(value, dict):
        raise _http_error(status.HTTP_403_FORBIDDEN, 'flow payload must be an object')

    unknown = sorted(set(value.keys()) - FLOW_PAYLOAD_FIELDS)
    if unknown:
        raise _http_error(status.HTTP_403_FORBIDDEN, f'cannot modify flow fields: {", ".join(unknown)}')

    normalized = {
        key: cleaned
        for key, item in value.items()
        if (cleaned := _clean_flow_value(item)) not in (None, '')
    }
    if normalized:
        normalized['flow_source'] = _normalize_flow_source(normalized.get('flow_source'))
    return normalized


def _normalize_extra_payload_flow(values: dict[str, Any]) -> dict[str, Any]:
    if not values or 'flow' not in values:
        return values
    normalized = dict(values)
    normalized['flow'] = _normalize_flow_payload(normalized.get('flow'))
    return normalized

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

def _entry_creator_user_id(entry: WorkOrderEntry) -> int | None:
    return getattr(entry, 'created_by_user_id', None) or getattr(entry, 'created_by', None)

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
