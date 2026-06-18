from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.core.active_workshops import get_workshop_data_source_policy, normalize_workshop_name
from app.core.business_time import resolve_production_business_date
from app.core.scope import (
    build_scope_summary,
    can_view_all_work_order_entries,
    can_view_work_order_entries,
    resolve_work_order_entry_workshop_scope,
)
from app.core.workshop_templates import (
    DEFAULT_WORKSHOP_TEMPLATES,
    INVENTORY_OWNER_FIELDS,
    OVERHAUL_OWNER_FIELDS,
    QC_OWNER_FIELDS,
    RECOVERY_OWNER_FIELDS,
    SHIPMENT_OUTFLOW_OWNER_FIELDS,
    UTILITY_OWNER_FIELDS,
    resolve_workshop_type,
)
from app.models.attendance import AttendanceSchedule, EmployeeAttendanceDetail, ShiftAttendanceConfirmation
from app.models.energy import MachineEnergyRecord
from app.models.master import Equipment, MasterCodeAlias, MesTerminalBinding, Workshop
from app.models.mes import MesCoilSnapshot, MesMaterialRecord, MesWorkshopProcessRecord
from app.models.production import MobileShiftReport, ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import attendance_confirm_service
from app.services import master_service
from app.services import mes_machine_match_service
from app.services import mes_sync_service
from app.services.equipment_service import get_bound_machine_for_user, resolve_reporting_machine_from_candidates
from app.services.report import daily_overview_builder, mes_home_packaging_fact
from app.services.real_master_data import (
    OWNER_DAILY_ROLES,
    REPORTING_MACHINE_CODE_SET,
    REPORTING_MACHINE_WORKSHOP_CODES,
    REPORTING_ROLE_QR_CODE_SET,
)
from app.services.yield_matrix_canonical_service import build_yield_matrix_projection
from app.utils.tracking_cards import tracking_card_lookup_candidates, tracking_card_lookup_key

LOCAL_SHIFT_DATA_SOURCE = 'mobile_coil_agg'
LOCAL_SHIFT_DATA_STATUSES = {'pending', 'submitted', 'reviewed', 'confirmed'}
FORMAL_ENTRY_STATUSES = {'submitted', 'verified', 'approved'}
ACTIVE_DATE_LOOKBACK_HOURS = 36
OWNER_DAILY_ENTRY_TYPE = 'owner_daily'
OWNER_DAILY_ROLE_LABELS = {
    'consumable_stat': '内勤',
    'quality_owner': '质检内勤',
    'planning_owner': '计划内勤',
    'energy_chief': '总电工',
    'storage_owner': '成品库',
    'shipment_outflow_owner': '园区剪切',
    'recovery_owner': '回收',
    'overhaul_owner': '大修',
}
OWNER_DAILY_FIELD_META = {
    'plant_wide_yield_rate': ('全厂总成品率', '%'),
    'total_electricity_kwh': ('全厂用电', 'kWh'),
    'new_plant_electricity_kwh': ('新厂用电', 'kWh'),
    'park_electricity_kwh': ('园区用电', 'kWh'),
    'total_gas_m3': ('天然气总量', 'm3'),
    'cast_roll_gas_m3': ('铸轧天然气', 'm3'),
    'smelting_gas_m3': ('铸锭熔炼炉天然气', 'm3'),
    'heating_furnace_gas_m3': ('热轧加热炉天然气', 'm3'),
    'boiler_gas_m3': ('锅炉天然气', 'm3'),
    'groundwater_ton': ('地下水', '吨'),
    'tap_water_ton': ('自来水', '吨'),
    'park_inbound_daily': ('园区入库日合', '吨'),
    'new_plant_inbound_daily': ('新厂入库日合', '吨'),
    'park_outbound_daily': ('园区出库日合', '吨'),
    'new_plant_outbound_daily': ('新厂出库日合', '吨'),
    'consignment_weight': ('成品库寄存', '吨'),
}
STRUCTURED_EXTRA_PAYLOAD_KEYS = {'flow', 'locked_fields_snapshot'}
DIRECT_OWNER_FIELD_GROUPS = (
    QC_OWNER_FIELDS,
    UTILITY_OWNER_FIELDS,
    INVENTORY_OWNER_FIELDS,
    SHIPMENT_OUTFLOW_OWNER_FIELDS,
    RECOVERY_OWNER_FIELDS,
    OVERHAUL_OWNER_FIELDS,
)


def _owner_daily_effective_role(user: User, workshop: Workshop | None) -> str:
    role = str(getattr(user, 'role', '') or '')
    workshop_code = str(getattr(workshop, 'code', '') or '').upper()
    if role == 'consumable_stat' and workshop_code == 'HS':
        return 'recovery_owner'
    if role == 'consumable_stat' and workshop_code == 'CPK':
        return 'storage_owner'
    return role


def _owner_daily_group_key(user: User, workshop: Workshop | None) -> tuple[str, str]:
    workshop_key = str(getattr(workshop, 'code', '') or getattr(user, 'workshop_id', '') or getattr(user, 'id', ''))
    return (workshop_key.upper(), _owner_daily_effective_role(user, workshop))


def _build_fill_detail_field_meta() -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    meta = dict(OWNER_DAILY_FIELD_META)
    field_types: dict[str, str] = {}
    for key in OWNER_DAILY_FIELD_META:
        field_types[key] = 'number'
    for fields in DIRECT_OWNER_FIELD_GROUPS:
        for field in fields:
            name = str(field.get('name') or '').strip()
            if not name:
                continue
            meta.setdefault(name, (str(field.get('label') or name), str(field.get('unit') or '')))
            field_types.setdefault(name, str(field.get('type') or ''))
    for template in DEFAULT_WORKSHOP_TEMPLATES.values():
        for section_name in ('entry_fields', 'shift_fields', 'extra_fields', 'qc_fields', 'readonly_fields'):
            for field in template.get(section_name, []):
                name = str(field.get('name') or '').strip()
                if not name:
                    continue
                label = str(field.get('label') or name)
                unit = str(field.get('unit') or '')
                meta.setdefault(name, (label, unit))
                field_types.setdefault(name, str(field.get('type') or ''))
    meta.setdefault('quality_issue', ('质量问题', ''))
    return meta, field_types


FILL_DETAIL_FIELD_META, FILL_DETAIL_FIELD_TYPES = _build_fill_detail_field_meta()


def _workshop_field_context(workshop: Workshop | None) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    meta = dict(FILL_DETAIL_FIELD_META)
    field_types = dict(FILL_DETAIL_FIELD_TYPES)
    if workshop is None:
        return meta, field_types
    try:
        template_key = resolve_workshop_type(
            workshop_type=getattr(workshop, 'workshop_type', None),
            workshop_code=getattr(workshop, 'code', None),
            workshop_name=getattr(workshop, 'name', None),
        )
    except Exception:
        template_key = None
    template = DEFAULT_WORKSHOP_TEMPLATES.get(template_key or '')
    if not template:
        return meta, field_types
    for section_name in ('entry_fields', 'shift_fields', 'extra_fields', 'qc_fields', 'readonly_fields'):
        for field in template.get(section_name, []):
            name = str(field.get('name') or '').strip()
            if not name:
                continue
            meta[name] = (str(field.get('label') or name), str(field.get('unit') or ''))
            field_types[name] = str(field.get('type') or '')
    return meta, field_types


def _to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _payload_float(value: Any) -> float | None:
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _quality_issue_text(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    parts = [
        value.get('issue_type'),
        value.get('issue_note'),
        value.get('photo_name'),
    ]
    text = ' '.join(str(item).strip() for item in parts if item not in (None, ''))
    return text or None


def _metric_display_value(key: str, value: Any, field_types: Mapping[str, str] | None = None) -> Any:
    if value is None or value == '':
        return None
    if isinstance(value, Mapping) or isinstance(value, list):
        return None
    field_type = (field_types or FILL_DETAIL_FIELD_TYPES).get(key)
    if field_type == 'number':
        return _payload_float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    return text or None


def _extra_payload_metrics(
    payload: Mapping[str, Any],
    *,
    field_meta: Mapping[str, tuple[str, str]] | None = None,
    field_types: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    metrics = []
    resolved_meta = field_meta or FILL_DETAIL_FIELD_META
    for key, raw_value in payload.items():
        if key in STRUCTURED_EXTRA_PAYLOAD_KEYS:
            continue
        if key == 'quality_issue':
            value = _quality_issue_text(raw_value)
        else:
            value = _metric_display_value(key, raw_value, field_types)
        if value is None:
            continue
        label, unit = resolved_meta.get(key, (key, ''))
        metrics.append({'key': key, 'label': label, 'value': value, 'unit': unit})
    return metrics


def _metric_total(metrics: list[dict[str, Any]], keys: set[str]) -> float:
    total = 0.0
    for metric in metrics:
        if str(metric.get('key') or '') not in keys:
            continue
        value = _payload_float(metric.get('value'))
        if value is not None:
            total += value
    return total


def _entry_weight_tons(item: dict, field_name: str) -> float:
    value = _to_float(item.get(field_name))
    if item.get('weight_unit') == 'kg':
        return value / 1000
    return value


def _is_mes_weight_entry(item: dict) -> bool:
    if item.get('entry_type') == 'mes_projection':
        return True
    return bool(item.get('mes_weight_authority'))


def _is_formal_entry(item: dict) -> bool:
    return item.get('entry_status') in FORMAL_ENTRY_STATUSES or item.get('entry_type') == 'mes_projection'


def _entry_count_summary(items: list[dict]) -> dict:
    formal_count = len([item for item in items if _is_formal_entry(item)])
    draft_count = len([item for item in items if item.get('entry_status') == 'draft'])
    return {
        'formal_entry_count': formal_count,
        'draft_entry_count': draft_count,
        'total_entry_count': len(items),
    }


def _optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.DEFAULT_TIMEZONE))


def resolve_live_business_date(
    db: Session,
    *,
    today: date | None = None,
    now: datetime | None = None,
    lookback_hours: int = ACTIVE_DATE_LOOKBACK_HOURS,
    workshop_id: int | None = None,
) -> dict:
    resolved_now = now or _local_now()
    resolved_today = today or resolve_production_business_date(resolved_now)
    cutoff = resolved_now - timedelta(hours=max(int(lookback_hours or ACTIVE_DATE_LOOKBACK_HOURS), 1))

    entry_query = (
        db.query(
            WorkOrderEntry.business_date,
            func.count(WorkOrderEntry.id).label('entry_count'),
            func.max(WorkOrderEntry.created_at).label('last_created_at'),
        )
        .filter(
            WorkOrderEntry.business_date <= resolved_today,
            WorkOrderEntry.created_at >= cutoff,
        )
    )
    if workshop_id is not None:
        entry_query = entry_query.filter(WorkOrderEntry.workshop_id == workshop_id)
    recent_entry = (
        entry_query
        .group_by(WorkOrderEntry.business_date)
        .order_by(func.max(WorkOrderEntry.created_at).desc(), WorkOrderEntry.business_date.desc())
        .first()
    )
    if recent_entry is not None and recent_entry.business_date is not None:
        return {
            'business_date': recent_entry.business_date.isoformat(),
            'source': 'recent_upload',
            'recent_entry_count': int(recent_entry.entry_count or 0),
        }

    shift_query = (
        db.query(
            ShiftProductionData.business_date,
            func.count(ShiftProductionData.id).label('entry_count'),
            func.max(ShiftProductionData.updated_at).label('last_updated_at'),
        )
        .filter(
            ShiftProductionData.business_date <= resolved_today,
            ShiftProductionData.updated_at >= cutoff,
            ShiftProductionData.data_status != 'voided',
        )
    )
    if workshop_id is not None:
        shift_query = shift_query.filter(ShiftProductionData.workshop_id == workshop_id)
    recent_shift = (
        shift_query
        .group_by(ShiftProductionData.business_date)
        .order_by(func.max(ShiftProductionData.updated_at).desc(), ShiftProductionData.business_date.desc())
        .first()
    )
    if recent_shift is not None and recent_shift.business_date is not None:
        return {
            'business_date': recent_shift.business_date.isoformat(),
            'source': 'recent_shift_data',
            'recent_entry_count': int(recent_shift.entry_count or 0),
        }

    return {
        'business_date': resolved_today.isoformat(),
        'source': 'current_date',
        'recent_entry_count': 0,
    }


def _parse_business_date(value: object | None) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _count_live_fill_entries(db: Session, *, business_date: date, workshop_id: int | None) -> int:
    query = db.query(func.count(WorkOrderEntry.id)).filter(WorkOrderEntry.business_date == business_date)
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)
    return int(query.scalar() or 0)


def _latest_live_fill_business_date(db: Session, *, today: date, workshop_id: int | None) -> date | None:
    query = (
        db.query(
            WorkOrderEntry.business_date,
            func.max(WorkOrderEntry.created_at).label('last_created_at'),
        )
        .filter(WorkOrderEntry.business_date <= today)
        .group_by(WorkOrderEntry.business_date)
        .order_by(func.max(WorkOrderEntry.created_at).desc(), WorkOrderEntry.business_date.desc())
    )
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)
    row = query.first()
    return row.business_date if row is not None else None


def _build_live_business_date_context(db: Session, *, requested_date: date, workshop_id: int | None) -> dict:
    resolved_now = _local_now()
    current_date = resolve_production_business_date(resolved_now)
    active_payload = resolve_live_business_date(db, today=current_date, now=resolved_now, workshop_id=workshop_id)
    active_date = _parse_business_date(active_payload.get('business_date'))
    latest_fill_date = _latest_live_fill_business_date(db, today=current_date, workshop_id=workshop_id)

    requested_entry_count = _count_live_fill_entries(db, business_date=requested_date, workshop_id=workshop_id)
    current_date_entry_count = (
        requested_entry_count
        if requested_date == current_date
        else _count_live_fill_entries(db, business_date=current_date, workshop_id=workshop_id)
    )
    active_date_entry_count = (
        _count_live_fill_entries(db, business_date=active_date, workshop_id=workshop_id)
        if active_date is not None
        else 0
    )

    return {
        'requested_business_date': requested_date.isoformat(),
        'current_business_date': current_date.isoformat(),
        'active_business_date': active_date.isoformat() if active_date is not None else None,
        'active_date_source': active_payload.get('source') or 'current_date',
        'latest_fill_business_date': latest_fill_date.isoformat() if latest_fill_date is not None else None,
        'requested_entry_count': requested_entry_count,
        'current_date_entry_count': current_date_entry_count,
        'active_date_entry_count': active_date_entry_count,
        'has_current_date_entries': current_date_entry_count > 0,
        'is_requested_current_date': requested_date == current_date,
        'is_showing_active_business_date': active_date == requested_date if active_date is not None else False,
    }


def _has_reporting_workshop_rows(db: Session) -> bool:
    return bool(
        db.query(func.count(Workshop.id))
        .filter(
            Workshop.is_active.is_(True),
            Workshop.code.in_(tuple(REPORTING_MACHINE_WORKSHOP_CODES)),
        )
        .scalar()
        or 0
    )


def _has_reporting_machine_rows(db: Session) -> bool:
    return bool(
        db.query(func.count(Equipment.id))
        .filter(
            Equipment.is_active.is_(True),
            Equipment.code.in_(tuple(REPORTING_MACHINE_CODE_SET)),
        )
        .scalar()
        or 0
    )


def _build_pending_assignment_summary(*, entries: list[dict], workshops, shifts) -> dict:
    pending_entries = [
        item
        for item in entries
        if item.get('entry_type') not in {OWNER_DAILY_ENTRY_TYPE, 'mes_projection'}
        and (item.get('machine_id') is None or item.get('shift_id') is None)
    ]
    entry_count = len(pending_entries)
    if entry_count == 0:
        return {'entry_count': 0}

    workshop_name_by_id = {
        int(item.id): item.name
        for item in workshops
        if getattr(item, 'id', None) is not None
    }
    shift_name_by_id = {
        int(item.id): item.name
        for item in shifts
        if getattr(item, 'id', None) is not None
    }
    rows: dict[tuple[int | None, int | None], dict] = {}
    workshop_ids: set[int] = set()
    shift_ids: set[int] = set()
    input_total = 0.0
    output_total = 0.0
    formal_count = 0
    draft_count = 0
    missing_machine_count = 0
    missing_shift_count = 0

    for item in pending_entries:
        workshop_id = _optional_int(item.get('workshop_id'))
        shift_id = _optional_int(item.get('shift_id'))
        if workshop_id is not None:
            workshop_ids.add(workshop_id)
        if shift_id is not None:
            shift_ids.add(shift_id)

        input_weight = _entry_weight_tons(item, 'input_weight')
        output_weight = _entry_weight_tons(item, 'output_weight')
        input_total += input_weight
        output_total += output_weight
        is_formal = _is_formal_entry(item)
        is_draft = item.get('entry_status') == 'draft'
        formal_count += 1 if is_formal else 0
        draft_count += 1 if is_draft else 0
        missing_machine = item.get('machine_id') is None
        missing_shift = item.get('shift_id') is None
        missing_machine_count += 1 if missing_machine else 0
        missing_shift_count += 1 if missing_shift else 0

        key = (workshop_id, shift_id)
        row = rows.setdefault(
            key,
            {
                'workshop_id': workshop_id,
                'workshop_name': workshop_name_by_id.get(workshop_id, '未标记车间'),
                'shift_id': shift_id,
                'shift_name': shift_name_by_id.get(shift_id, '未标记班次'),
                'entry_count': 0,
                'draft_entry_count': 0,
                'formal_entry_count': 0,
                'missing_machine_count': 0,
                'missing_shift_count': 0,
                'input': 0.0,
                'output': 0.0,
            },
        )
        row['entry_count'] += 1
        row['draft_entry_count'] += 1 if is_draft else 0
        row['formal_entry_count'] += 1 if is_formal else 0
        row['missing_machine_count'] += 1 if missing_machine else 0
        row['missing_shift_count'] += 1 if missing_shift else 0
        row['input'] += input_weight
        row['output'] += output_weight

    row_items = []
    for row in rows.values():
        row_items.append(
            {
                **row,
                'input': round(row['input'], 2),
                'output': round(row['output'], 2),
            }
        )
    row_items.sort(key=lambda item: (-item['output'], -item['entry_count'], str(item['workshop_name']), str(item['shift_name'])))

    return {
        'entry_count': entry_count,
        'draft_entry_count': draft_count,
        'formal_entry_count': formal_count,
        'missing_machine_count': missing_machine_count,
        'missing_shift_count': missing_shift_count,
        'workshop_count': len(workshop_ids),
        'shift_count': len(shift_ids),
        'input': round(input_total, 2),
        'output': round(output_total, 2),
        'rows': row_items,
    }


def _is_mobile_entry_missing_output_weight(item: dict) -> bool:
    if item.get('entry_type') != 'mobile_coil':
        return False
    if not _is_formal_entry(item):
        return False
    if item.get('output_weight_missing') is True:
        return True
    return item.get('output_weight') is None


def _is_model_missing_output_weight(entry: WorkOrderEntry) -> bool:
    return (
        entry.entry_type == 'mobile_coil'
        and entry.entry_status in FORMAL_ENTRY_STATUSES
        and entry.output_weight is None
        and entry.verified_output_weight is None
    )


def _model_input_weight_tons(entry: WorkOrderEntry) -> float:
    value = entry.verified_input_weight if entry.verified_input_weight is not None else entry.input_weight
    return _to_float(value) / 1000


def _ensure_missing_output_entry_scope(db: Session, entry: WorkOrderEntry, current_user: User) -> None:
    summary = build_scope_summary(current_user)
    if not can_view_work_order_entries(summary):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='work order entry access denied')
    if not can_view_all_work_order_entries(summary):
        scoped_id = resolve_work_order_entry_workshop_scope(summary)
        if scoped_id is None or int(entry.workshop_id) != int(scoped_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='work order entry access denied')
    bound_machine = get_bound_machine_for_user(db, user_id=getattr(current_user, 'id', None))
    if bound_machine is not None:
        if bound_machine.operational_status != 'running':
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='该机台已停机')
        if entry.machine_id is None or int(entry.machine_id) != int(bound_machine.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权操作此机台')


def resolve_missing_output_weight(
    db: Session,
    *,
    entry_id: int,
    output_weight: float,
    reason: str,
    current_user: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    entry = db.get(WorkOrderEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='work order entry not found')
    _ensure_missing_output_entry_scope(db, entry, current_user)
    if not _is_model_missing_output_weight(entry):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='output_weight_already_present')

    output_tons = float(output_weight or 0)
    if output_tons <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='output_weight_required')
    input_tons = _model_input_weight_tons(entry)
    if input_tons <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='input_weight_required')
    if output_tons > input_tons:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='output_weight_exceeds_input')

    normalized_reason = str(reason or '').strip()
    if not normalized_reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='reason_required')

    from app.services import work_order_service

    output_kg = round(output_tons * 1000, 3)
    updated = work_order_service.update_entry(
        db,
        entry_id=entry_id,
        payload={'output_weight': output_kg},
        operator=current_user,
        override_reason=f'补产出重量：{normalized_reason}',
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return {
        'entry_id': int(updated['id']),
        'work_order_id': int(updated['work_order_id']),
        'output_weight': round(output_tons, 3),
        'yield_rate': round(_to_float(updated.get('yield_rate')), 4) if updated.get('yield_rate') is not None else None,
        'entry_status': updated.get('entry_status') or '',
    }


def _build_missing_output_weight_summary(*, entries: list[dict], workshops, machines, shifts) -> dict:
    workshop_name_by_id = {
        int(item.id): item.name
        for item in workshops
        if getattr(item, 'id', None) is not None
    }
    machine_name_by_id = {
        int(item.id): item.name
        for item in machines
        if getattr(item, 'id', None) is not None
    }
    shift_name_by_id = {
        int(item.id): item.name
        for item in shifts
        if getattr(item, 'id', None) is not None
    }

    input_total = 0.0
    scrap_total = 0.0
    items = []
    for item in entries:
        if not _is_mobile_entry_missing_output_weight(item):
            continue

        workshop_id = _optional_int(item.get('workshop_id'))
        machine_id = _optional_int(item.get('machine_id'))
        shift_id = _optional_int(item.get('shift_id'))
        input_weight = round(_entry_weight_tons(item, 'input_weight'), 2)
        scrap_weight = round(_entry_weight_tons(item, 'scrap_weight'), 2)
        input_total += input_weight
        scrap_total += scrap_weight
        items.append(
            {
                'entry_id': _optional_int(item.get('id')),
                'work_order_id': _optional_int(item.get('work_order_id')),
                'tracking_card_no': item.get('tracking_card_no') or '',
                'workshop_id': workshop_id,
                'workshop_name': workshop_name_by_id.get(workshop_id, '未标记车间'),
                'machine_id': machine_id,
                'machine_name': machine_name_by_id.get(machine_id, '未标记机列'),
                'shift_id': shift_id,
                'shift_name': shift_name_by_id.get(shift_id, '未标记班次'),
                'input_weight': input_weight,
                'output_weight': None,
                'scrap_weight': scrap_weight,
                'entry_status': item.get('entry_status') or '',
                'entry_type': item.get('entry_type') or '',
            }
        )

    items.sort(
        key=lambda item: (
            str(item['workshop_name']),
            str(item['machine_name']),
            str(item['shift_name']),
            -int(item['entry_id'] or 0),
        )
    )
    return {
        'entry_count': len(items),
        'input': round(input_total, 2),
        'scrap': round(scrap_total, 2),
        'items': items[:10],
    }


def _build_machine_mes_binding_summary(entries: list[dict]) -> dict:
    fill_entries = [item for item in entries if item.get('entry_type') != 'mes_projection']
    mes_matched_fill_entries = [item for item in fill_entries if int(item.get('mes_match_count') or 0) > 0]
    source_counts: dict[str, int] = defaultdict(int)
    for item in mes_matched_fill_entries:
        source_counts[str(item.get('mes_machine_binding_source') or 'unresolved')] += 1
    return {
        'fill_entry_count': len(fill_entries),
        'mes_matched_fill_count': len(mes_matched_fill_entries),
        'mes_bound_fill_count': len([item for item in mes_matched_fill_entries if item.get('machine_id') is not None]),
        'direct_machine_code_count': int(source_counts.get('direct_machine_code', 0)),
        'route_inferred_machine_count': int(source_counts.get('route_inferred', 0)),
        'mes_projection_count': len([item for item in entries if item.get('entry_type') == 'mes_projection']),
    }


def _round_rate(input_total: float, output_total: float) -> float | None:
    if input_total <= 0:
        return None
    return round((output_total / input_total) * 100, 2)


def _prefer_number(primary: Decimal | float | int | None, fallback: Decimal | float | int | None) -> float:
    if primary is not None:
        return _to_float(primary)
    return _to_float(fallback)


def _build_cell_status(*, is_applicable: bool, submission_status: str, attendance_status: str, attendance_exception_count: int) -> dict:
    if not is_applicable:
        return {'status_tone': 'muted', 'status_text': '不适用'}
    if attendance_exception_count > 0:
        return {'status_tone': 'danger', 'status_text': '考勤异常'}
    if submission_status == 'not_started':
        return {'status_tone': 'danger', 'status_text': '缺报'}
    if submission_status == 'in_progress':
        return {'status_tone': 'warning', 'status_text': '进行中'}
    if attendance_status in {'pending', 'not_started'}:
        return {'status_tone': 'warning', 'status_text': '考勤待确认'}
    return {'status_tone': 'success', 'status_text': '已填'}


def _resolve_workshop_filter(*, current_user: User, workshop_id: int | None) -> int | None:
    summary = build_scope_summary(current_user)
    if not can_view_work_order_entries(summary):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='work order entry access denied')
    scoped_id = resolve_work_order_entry_workshop_scope(summary)
    if can_view_all_work_order_entries(summary):
        return workshop_id
    if scoped_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='workshop scope denied')
    if workshop_id is not None and workshop_id != scoped_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='workshop scope denied')
    return scoped_id


def aggregate_live_payload(
    *,
    workshops,
    machines,
    shifts,
    entries: list[dict],
    attendance: dict[tuple[int, int], dict],
    expected_counts: dict[tuple[int, int, int], int],
) -> dict:
    machine_map: dict[int, list] = defaultdict(list)
    for machine in machines:
        machine_map[machine.workshop_id].append(machine)

    cell_entries: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
    machine_entries: dict[tuple[int, int], list[dict]] = defaultdict(list)
    data_shift_ids_by_machine: dict[tuple[int, int], set[int]] = defaultdict(set)
    for item in entries:
        if item.get('workshop_id') is not None and item.get('machine_id') is not None:
            machine_entries[(item['workshop_id'], item['machine_id'])].append(item)
        if item.get('machine_id') is None or item.get('shift_id') is None:
            continue
        cell_entries[(item['workshop_id'], item['machine_id'], item['shift_id'])].append(item)
        data_shift_ids_by_machine[(item['workshop_id'], item['machine_id'])].add(item['shift_id'])

    workshop_entries: dict[int, list[dict]] = defaultdict(list)
    for item in entries:
        workshop_id = _optional_int(item.get('workshop_id'))
        if workshop_id is None:
            continue
        workshop_entries[workshop_id].append(item)

    workshop_items: list[dict] = []
    submitted_cells = 0
    total_cells = 0
    missing_cell_count = 0
    attention_cell_count = 0
    factory_input = 0.0
    factory_output = 0.0
    factory_scrap = 0.0
    overall_entry_counts = _entry_count_summary(entries)
    pending_assignment = _build_pending_assignment_summary(entries=entries, workshops=workshops, shifts=shifts)
    missing_output_weight = _build_missing_output_weight_summary(
        entries=entries,
        workshops=workshops,
        machines=machines,
        shifts=shifts,
    )
    ordered_shifts = sorted(shifts, key=lambda item: (getattr(item, 'sort_order', 0), item.id))

    for workshop in sorted(workshops, key=lambda item: item.id):
        workshop_policy = get_workshop_data_source_policy(getattr(workshop, 'name', None))
        default_shift_ids = [shift.id for shift in ordered_shifts] if workshop_policy.get('has_terminal', True) else []
        workshop_input = 0.0
        workshop_output = 0.0
        workshop_scrap = 0.0
        workshop_entry_counts = _entry_count_summary(workshop_entries.get(int(workshop.id), []))
        machine_items: list[dict] = []

        for machine in sorted(machine_map.get(workshop.id, []), key=lambda item: (getattr(item, 'sort_order', 0), item.id)):
            shift_items: list[dict] = []
            machine_input = 0.0
            machine_output = 0.0
            machine_scrap = 0.0
            applicable_shift_ids = {
                int(item) for item in (getattr(machine, 'assigned_shift_ids', None) or default_shift_ids)
            }
            applicable_shift_ids.update(data_shift_ids_by_machine.get((workshop.id, machine.id), set()))

            for shift in ordered_shifts:
                is_applicable = shift.id in applicable_shift_ids
                attendance_state = attendance.get((workshop.id, shift.id), {'status': 'not_applicable', 'exception_count': 0})
                if not is_applicable:
                    cell_status = _build_cell_status(
                        is_applicable=False,
                        submission_status='not_applicable',
                        attendance_status='not_applicable',
                        attendance_exception_count=0,
                    )
                    shift_items.append(
                        {
                            'shift_id': shift.id,
                            'shift_name': shift.name,
                            'submitted_count': 0,
                            'draft_count': 0,
                            'total_expected': 0,
                            'total_input': 0.0,
                            'total_output': 0.0,
                            'total_scrap': 0.0,
                            'yield_rate': None,
                            'yield_rate_source': 'runtime_compat',
                            'attendance_status': 'not_applicable',
                            'attendance_exception_count': 0,
                            'submission_status': 'not_applicable',
                            'is_applicable': False,
                            **cell_status,
                        }
                    )
                    continue

                total_cells += 1
                rows = cell_entries.get((workshop.id, machine.id, shift.id), [])
                submitted_count = len(
                    [
                        item
                        for item in rows
                        if _is_formal_entry(item)
                    ]
                )
                draft_count = len([item for item in rows if item.get('entry_status') == 'draft'])
                total_count = len(rows)
                formal_rows = [item for item in rows if _is_formal_entry(item)]
                mes_weight_available = any(_is_mes_weight_entry(item) for item in formal_rows)
                weight_rows = [item for item in formal_rows if _is_mes_weight_entry(item)] if mes_weight_available else formal_rows
                input_total = round(sum(_entry_weight_tons(item, 'input_weight') for item in weight_rows), 2)
                output_total = round(sum(_entry_weight_tons(item, 'output_weight') for item in weight_rows), 2)
                scrap_total = round(sum(_entry_weight_tons(item, 'scrap_weight') for item in weight_rows), 2)
                expected_total = int(expected_counts.get((workshop.id, machine.id, shift.id), 0))
                if expected_total <= 0 and total_count > 0:
                    expected_total = total_count

                if total_count == 0:
                    submission_status = 'not_started'
                elif submitted_count >= max(expected_total, 1) and submitted_count == total_count:
                    submission_status = 'all_submitted'
                else:
                    submission_status = 'in_progress'
                if submitted_count > 0:
                    submitted_cells += 1
                attendance_status = attendance_state['status']
                attendance_exception_count = int(attendance_state.get('exception_count', 0))
                cell_status = _build_cell_status(
                    is_applicable=True,
                    submission_status=submission_status,
                    attendance_status=attendance_status,
                    attendance_exception_count=attendance_exception_count,
                )
                if submission_status == 'not_started':
                    missing_cell_count += 1
                if cell_status['status_tone'] in {'danger', 'warning'}:
                    attention_cell_count += 1

                machine_input += input_total
                machine_output += output_total
                machine_scrap += scrap_total
                shift_items.append(
                    {
                        'shift_id': shift.id,
                        'shift_name': shift.name,
                        'submitted_count': submitted_count,
                        'draft_count': draft_count,
                        'total_expected': expected_total,
                        'total_input': input_total,
                        'total_output': output_total,
                        'total_scrap': scrap_total,
                        'yield_rate': _round_rate(input_total, output_total),
                        'yield_rate_source': 'runtime_compat',
                        'attendance_status': attendance_status,
                        'attendance_exception_count': attendance_exception_count,
                        'submission_status': submission_status,
                        'is_applicable': True,
                        **cell_status,
                    }
                )

            workshop_input += machine_input
            workshop_output += machine_output
            workshop_scrap += machine_scrap
            machine_binding_status = getattr(machine, 'machine_binding_status', None)
            if not machine_binding_status:
                machine_binding_status = 'unbound' if int(machine.id) < 0 else 'bound'
            machine_items.append(
                {
                    'machine_id': machine.id,
                    'machine_name': machine.name,
                    'machine_binding_status': machine_binding_status,
                    'mes_binding': _build_machine_mes_binding_summary(machine_entries.get((workshop.id, machine.id), [])),
                    'shifts': shift_items,
                    'day_total': {
                        'input': round(machine_input, 2),
                        'output': round(machine_output, 2),
                        'scrap': round(machine_scrap, 2),
                        'yield_rate': _round_rate(machine_input, machine_output),
                        'yield_rate_source': 'runtime_compat',
                    },
                }
            )

        factory_input += workshop_input
        factory_output += workshop_output
        factory_scrap += workshop_scrap
        shift_totals: list[dict] = []
        for shift in ordered_shifts:
            is_applicable = False
            shift_input = 0.0
            shift_output = 0.0
            shift_scrap = 0.0
            for machine in machine_items:
                target = next((item for item in machine['shifts'] if item['shift_id'] == shift.id), None)
                if not target or not target.get('is_applicable'):
                    continue
                is_applicable = True
                shift_input += _to_float(target.get('total_input'))
                shift_output += _to_float(target.get('total_output'))
                shift_scrap += _to_float(target.get('total_scrap'))
            shift_totals.append(
                {
                    'shift_id': shift.id,
                    'shift_name': shift.name,
                    'is_applicable': is_applicable,
                    'total_input': round(shift_input, 2),
                    'total_output': round(shift_output, 2),
                    'total_scrap': round(shift_scrap, 2),
                    'yield_rate': _round_rate(shift_input, shift_output),
                    'yield_rate_source': 'runtime_compat',
                }
            )
        workshop_items.append(
            {
                'workshop_id': workshop.id,
                'workshop_name': workshop.name,
                'machines': machine_items,
                'shift_totals': shift_totals,
                'workshop_total': {
                    'input': round(workshop_input, 2),
                    'output': round(workshop_output, 2),
                    'scrap': round(workshop_scrap, 2),
                    'yield_rate': _round_rate(workshop_input, workshop_output),
                    'yield_rate_source': 'runtime_work_order',
                    **workshop_entry_counts,
                },
            }
        )

    overall_progress = {
        'submitted_cells': submitted_cells,
        'total_cells': total_cells,
        'missing_cell_count': missing_cell_count,
        'attention_cell_count': attention_cell_count,
        'completion_rate': round((submitted_cells / total_cells) * 100, 2) if total_cells else 0.0,
        **overall_entry_counts,
    }
    if pending_assignment['entry_count'] > 0:
        overall_progress['pending_assignment'] = pending_assignment

    return {
        'overall_progress': overall_progress,
        'workshops': workshop_items,
        'factory_total': {
            'input': round(factory_input, 2),
            'output': round(factory_output, 2),
            'scrap': round(factory_scrap, 2),
            'yield_rate': _round_rate(factory_input, factory_output),
            'yield_rate_source': 'runtime_work_order',
        },
        'data_quality': {
            'missing_output_weight': missing_output_weight,
        },
    }


def _build_owner_daily_status(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
) -> dict[str, Any]:
    expected_users_query = db.query(User).filter(
        User.is_active.is_(True),
        User.role.in_(tuple(OWNER_DAILY_ROLES)),
        User.username.in_(tuple(REPORTING_ROLE_QR_CODE_SET)),
    )
    if workshop_id is not None:
        expected_users_query = expected_users_query.filter(User.workshop_id == workshop_id)
    expected_users = expected_users_query.order_by(User.workshop_id.asc(), User.username.asc()).all()

    entry_rows_query = (
        db.query(WorkOrderEntry, User)
        .join(User, User.id == func.coalesce(WorkOrderEntry.created_by_user_id, WorkOrderEntry.created_by))
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.entry_type == OWNER_DAILY_ENTRY_TYPE,
            User.is_active.is_(True),
            User.role.in_(tuple(OWNER_DAILY_ROLES)),
        )
        .order_by(WorkOrderEntry.updated_at.asc(), WorkOrderEntry.id.asc())
    )
    if workshop_id is not None:
        entry_rows_query = entry_rows_query.filter(WorkOrderEntry.workshop_id == workshop_id)

    users_by_id = {int(user.id): user for user in expected_users if user.id is not None}
    latest_by_user: dict[int, WorkOrderEntry] = {}
    for row, user in entry_rows_query.all():
        if user.id is None:
            continue
        users_by_id[int(user.id)] = user
        latest_by_user[int(user.id)] = row

    workshop_ids = {item.workshop_id for item in users_by_id.values() if item.workshop_id is not None}
    workshops = db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all() if workshop_ids else []
    workshop_by_id = {item.id: item for item in workshops}
    grouped_items: dict[tuple[str, str], tuple[tuple[int, int, float, int], dict[str, Any]]] = {}
    totals: dict[str, float] = {}
    for user in users_by_id.values():
        entry = latest_by_user.get(int(user.id))
        is_submitted = entry is not None and entry.entry_status in FORMAL_ENTRY_STATUSES
        workshop = workshop_by_id.get(user.workshop_id)
        effective_role = _owner_daily_effective_role(user, workshop)
        payload = dict(entry.extra_payload or {}) if entry else {}
        field_meta, field_types = _workshop_field_context(workshop)
        metrics = _extra_payload_metrics(payload, field_meta=field_meta, field_types=field_types) if is_submitted else []
        item = {
            'user_id': user.id,
            'username': user.username,
            'person_name': user.name,
            'role': user.role,
            'effective_role': effective_role,
            'role_label': OWNER_DAILY_ROLE_LABELS.get(effective_role, effective_role),
            'workshop_id': user.workshop_id,
            'workshop_name': workshop.name if workshop else None,
            'status': 'submitted' if is_submitted else 'not_started',
            'entry_id': entry.id if entry else None,
            'updated_at': entry.updated_at.isoformat() if entry and entry.updated_at else None,
            'metrics': metrics,
        }
        updated_score = entry.updated_at.timestamp() if entry is not None and entry.updated_at else 0.0
        score = (
            1 if is_submitted else 0,
            1 if user.username in REPORTING_ROLE_QR_CODE_SET else 0,
            updated_score,
            int(user.id or 0),
        )
        group_key = _owner_daily_group_key(user, workshop)
        current = grouped_items.get(group_key)
        if current is None or score > current[0]:
            grouped_items[group_key] = (score, item)

    items = [item for _score, item in grouped_items.values()]
    items.sort(key=lambda item: (item.get('workshop_id') or 0, str(item.get('effective_role') or ''), str(item.get('username') or '')))
    submitted_count = len([item for item in items if item.get('status') == 'submitted'])
    for item in items:
        for metric in item.get('metrics') or []:
            key = str(metric['key'])
            value = _payload_float(metric.get('value'))
            if value is None:
                continue
            totals[key] = totals.get(key, 0.0) + value
    return {
        'business_date': business_date.isoformat(),
        'submitted_count': submitted_count,
        'total_count': len(items),
        'totals': [
            {
                'key': key,
                'label': FILL_DETAIL_FIELD_META.get(key, (key, ''))[0],
                'value': round(value, 4),
                'unit': FILL_DETAIL_FIELD_META.get(key, (key, ''))[1],
            }
            for key, value in totals.items()
        ],
        'items': items,
    }


def _resolve_yield_matrix_workshop_key(workshop: Workshop) -> str | None:
    code = str(getattr(workshop, 'code', '') or '').upper()
    name = str(getattr(workshop, 'name', '') or '')
    text = f'{code} {name}'
    if '1450' in text:
        return 'cold_roll_1450'
    if '1650' in text:
        return 'cold_roll_1650'
    if '2050' in text:
        return 'cold_roll_2050'
    if '1850' in text:
        return 'cold_roll_1850'
    if '拉矫' in text:
        return 'stretch'
    if '精整' in text:
        return 'finishing'
    if '飞剪' in text or '剪切' in text or code in {'JQ', 'CPK'}:
        return 'park_cutting'
    return None


def _apply_yield_matrix_authority(payload: dict, workshops: list[Workshop], yield_matrix_lane: dict) -> dict:
    matrix_ready = yield_matrix_lane.get('quality_status') == 'ready'
    if not matrix_ready:
        payload['yield_matrix_lane'] = yield_matrix_lane
        return payload

    workshop_truth = dict(yield_matrix_lane.get('workshop_yields') or {})
    company_total = yield_matrix_lane.get('company_total_yield')
    workshop_key_by_id = {item.id: _resolve_yield_matrix_workshop_key(item) for item in workshops}

    for workshop_payload in payload.get('workshops', []):
        workshop_key = workshop_key_by_id.get(workshop_payload.get('workshop_id'))
        workshop_total = dict(workshop_payload.get('workshop_total') or {})
        if workshop_key and workshop_key in workshop_truth:
            workshop_total['yield_rate'] = workshop_truth[workshop_key]
            workshop_total['yield_rate_source'] = 'yield_matrix_lane'
            workshop_total['yield_matrix_key'] = workshop_key
            workshop_payload['workshop_total'] = workshop_total

    factory_total = dict(payload.get('factory_total') or {})
    if company_total is not None:
        factory_total['yield_rate'] = company_total
        factory_total['yield_rate_source'] = 'yield_matrix_lane'
        payload['factory_total'] = factory_total

    payload['yield_matrix_lane'] = yield_matrix_lane
    return payload


def _load_entry_rows(db: Session, *, business_date: date, workshop_id: int | None) -> list[dict]:
    query = (
        db.query(WorkOrderEntry, WorkOrder)
        .join(WorkOrder, WorkOrder.id == WorkOrderEntry.work_order_id)
        .filter(WorkOrderEntry.business_date == business_date)
    )
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)
    rows = query.all()
    machine_ids = {entry.machine_id for entry, _work_order in rows if entry.machine_id is not None}
    machine_rows = db.query(Equipment).filter(Equipment.id.in_(machine_ids)).all() if machine_ids else []
    machine_by_id = {machine.id: machine for machine in machine_rows}
    candidate_workshop_ids = {machine.workshop_id for machine in machine_rows if machine.workshop_id is not None}
    reporting_candidates = (
        db.query(Equipment)
        .filter(Equipment.workshop_id.in_(candidate_workshop_ids), Equipment.is_active.is_(True))
        .all()
        if candidate_workshop_ids
        else []
    )
    candidates_by_workshop: dict[int, list[Equipment]] = defaultdict(list)
    for machine in reporting_candidates:
        candidates_by_workshop[machine.workshop_id].append(machine)

    def resolve_machine_id(machine_id: int | None) -> int | None:
        if machine_id is None:
            return None
        machine = machine_by_id.get(machine_id)
        reporting_machine = resolve_reporting_machine_from_candidates(machine, candidates_by_workshop.get(getattr(machine, 'workshop_id', None), []))
        return reporting_machine.id if reporting_machine is not None else machine_id

    items = []
    for entry, work_order in query.all():
        output_weight_missing = entry.verified_output_weight is None and entry.output_weight is None
        items.append(
            {
                'id': entry.id,
                'tracking_card_no': work_order.tracking_card_no,
                'work_order_id': entry.work_order_id,
                'workshop_id': entry.workshop_id,
                'machine_id': resolve_machine_id(entry.machine_id),
                'shift_id': entry.shift_id,
                'business_date': entry.business_date.isoformat(),
                'input_weight': _prefer_number(entry.verified_input_weight, entry.input_weight),
                'output_weight': None if output_weight_missing else _prefer_number(entry.verified_output_weight, entry.output_weight),
                'output_weight_missing': output_weight_missing,
                'scrap_weight': _to_float(entry.scrap_weight),
                'yield_rate': float(entry.yield_rate) if entry.yield_rate is not None else None,
                'yield_rate_source': 'runtime_compat',
                'entry_status': entry.entry_status,
                'entry_type': entry.entry_type,
                'weight_unit': 'kg',
                'tracking_card_status': work_order.overall_status,
            }
        )
    return items


def _entry_weight_kg_to_tons(entry: WorkOrderEntry, field_name: str) -> float:
    value = getattr(entry, field_name)
    if field_name == 'input_weight':
        value = _prefer_number(entry.verified_input_weight, entry.input_weight)
    elif field_name == 'output_weight':
        value = _prefer_number(entry.verified_output_weight, entry.output_weight)
    return _to_float(value) / 1000


def _extra_pass_count(extra: Any) -> int:
    if not isinstance(extra, dict):
        return 0
    raw = extra.get('pass_count')
    if raw in (None, ''):
        return 0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0
    if value <= 0:
        return 0
    return int(value)


def _build_mtd_totals(
    db: Session,
    *,
    business_date: date,
    workshop_ids: list[int],
    workshop_id: int | None,
) -> dict[str, Any]:
    """Sum month-to-date production for the given workshops.

    MES output records are authoritative when available. The legacy
    WorkOrderEntry branch remains only as a no-MES compatibility fallback.
    """
    month_start = date(business_date.year, business_date.month, 1)
    mes_by_workshop = daily_overview_builder._mixed_workshop_output_scope_by_workshop(db, month_start, business_date)
    if mes_by_workshop:
        scoped_ids = {int(item) for item in workshop_ids}
        if workshop_id is not None:
            scoped_ids = {int(workshop_id)}
        rounded: dict[int, dict[str, Any]] = {}
        factory_input = 0.0
        factory_output = 0.0
        factory_pass_total = 0
        for ws_id, bucket in mes_by_workshop.items():
            if scoped_ids and int(ws_id) not in scoped_ids:
                continue
            input_total = _to_float(bucket.get('input'))
            output_total = _to_float(bucket.get('output'))
            pass_total = int(bucket.get('pass_count_total') or 0)
            rounded[int(ws_id)] = {
                'mtd_input': round(input_total, 2),
                'mtd_output': round(output_total, 2),
                'mtd_scrap': 0.0,
                'mtd_yield_rate': _round_rate(input_total, output_total),
                'mtd_pass_count_total': pass_total,
                'source_basis': bucket.get('source_basis') or 'mes_output_records',
                'source_label': bucket.get('source_label') or '外部 MES 产量',
            }
            factory_input += input_total
            factory_output += output_total
            factory_pass_total += pass_total
        return {
            'by_workshop': rounded,
            'factory': {
                'mtd_input': round(factory_input, 2),
                'mtd_output': round(factory_output, 2),
                'mtd_scrap': 0.0,
                'mtd_yield_rate': _round_rate(factory_input, factory_output),
                'mtd_pass_count_total': int(factory_pass_total),
                'month_start': month_start.isoformat(),
                'month_end': business_date.isoformat(),
                'source_basis': 'mes_output_records',
                'source_label': '外部 MES 产量',
            },
        }

    query = (
        db.query(WorkOrderEntry)
        .filter(WorkOrderEntry.business_date >= month_start)
        .filter(WorkOrderEntry.business_date <= business_date)
    )
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)
    elif workshop_ids:
        query = query.filter(WorkOrderEntry.workshop_id.in_(workshop_ids))
    else:
        return {
            'by_workshop': {},
            'factory': {
                'mtd_input': 0.0,
                'mtd_output': 0.0,
                'mtd_scrap': 0.0,
                'mtd_yield_rate': None,
                'mtd_pass_count_total': 0,
            },
        }

    by_workshop: dict[int, dict[str, float]] = defaultdict(
        lambda: {
            'mtd_input': 0.0,
            'mtd_output': 0.0,
            'mtd_scrap': 0.0,
            'mtd_pass_count_total': 0,
        }
    )
    factory_input = 0.0
    factory_output = 0.0
    factory_scrap = 0.0
    factory_pass_total = 0

    for entry in query.all():
        if entry.workshop_id is None:
            continue
        bucket = by_workshop[int(entry.workshop_id)]
        input_t = _entry_weight_kg_to_tons(entry, 'input_weight')
        output_t = _entry_weight_kg_to_tons(entry, 'output_weight')
        scrap_t = _to_float(entry.scrap_weight) / 1000
        bucket['mtd_input'] += input_t
        bucket['mtd_output'] += output_t
        bucket['mtd_scrap'] += scrap_t
        factory_input += input_t
        factory_output += output_t
        factory_scrap += scrap_t
        if entry.entry_type == 'mobile_coil':
            passes = _extra_pass_count(entry.extra_payload)
            bucket['mtd_pass_count_total'] += passes
            factory_pass_total += passes

    rounded: dict[int, dict[str, Any]] = {}
    for ws_id, bucket in by_workshop.items():
        rounded[ws_id] = {
            'mtd_input': round(bucket['mtd_input'], 2),
            'mtd_output': round(bucket['mtd_output'], 2),
            'mtd_scrap': round(bucket['mtd_scrap'], 2),
            'mtd_yield_rate': _round_rate(bucket['mtd_input'], bucket['mtd_output']),
            'mtd_pass_count_total': int(bucket['mtd_pass_count_total']),
        }
    return {
        'by_workshop': rounded,
        'factory': {
            'mtd_input': round(factory_input, 2),
            'mtd_output': round(factory_output, 2),
            'mtd_scrap': round(factory_scrap, 2),
            'mtd_yield_rate': _round_rate(factory_input, factory_output),
            'mtd_pass_count_total': int(factory_pass_total),
            'month_start': month_start.isoformat(),
            'month_end': business_date.isoformat(),
        },
    }


def _safe_equipment_aliases(db: Session) -> list[MasterCodeAlias]:
    try:
        return (
            db.query(MasterCodeAlias)
            .filter(
                MasterCodeAlias.entity_type == 'equipment',
                MasterCodeAlias.is_active.is_(True),
            )
            .all()
        )
    except (OperationalError, ProgrammingError):
        return []


def _safe_terminal_bindings(db: Session) -> list[MesTerminalBinding]:
    try:
        return db.query(MesTerminalBinding).filter(MesTerminalBinding.is_active.is_(True)).all()
    except (OperationalError, ProgrammingError):
        return []


def _machine_in_workshop(machine: Equipment | None, workshop: Workshop) -> bool:
    return (
        machine is not None
        and getattr(machine, 'workshop_id', None) is not None
        and int(machine.workshop_id) == int(workshop.id)
    )


def _preferred_hot_roll_material_machine(machines: list[Equipment]) -> Equipment | None:
    for machine in machines:
        code = str(getattr(machine, 'code', '') or '').strip().upper()
        name = str(getattr(machine, 'name', '') or '').strip()
        if code == 'RZ-ZJ' or name == '热轧机':
            return machine
    return None


def _unresolved_mes_machine(*, workshop: Workshop, device_name: object | None, process_hint: object | None) -> SimpleNamespace:
    process_text = str(process_hint or '').strip() or '未标记工序'
    device_text = str(device_name or '').strip()
    key_text = f'{process_text}|{device_text}'
    stable_suffix = sum(ord(char) for char in key_text) % 90000
    machine_name = f'MES未匹配机台 / {process_text}'
    if device_text:
        machine_name = f'{machine_name} / {device_text}'
    return SimpleNamespace(
        id=-((int(workshop.id) * 100000) + stable_suffix + 1000),
        workshop_id=int(workshop.id),
        name=machine_name,
        machine_binding_status='unbound',
        sort_order=900000 + stable_suffix,
    )


def _resolve_mes_output_machine(
    *,
    machines: list[Equipment],
    machine_by_id: dict[int, Equipment],
    aliases: list[MasterCodeAlias],
    terminal_bindings: list[MesTerminalBinding],
    workshop: Workshop,
    device_name: object | None,
    process_hint: object | None,
    terminal_hints: Mapping[str, Any] | None,
    event_time: datetime | None,
) -> tuple[Equipment | None, str]:
    binding = mes_machine_match_service.resolve_mes_machine_binding(
        machines=machines,
        device_name=device_name,
        process_hint=process_hint,
        preferred_workshop_id=int(workshop.id),
        aliases=aliases,
        terminal_bindings=terminal_bindings,
        terminal_hints=terminal_hints,
        workshop_name=workshop.name,
        event_time=event_time,
    )
    machine_id = _optional_int(binding.get('machine_id'))
    machine = machine_by_id.get(machine_id) if machine_id is not None else None
    if _machine_in_workshop(machine, workshop):
        return machine, str(binding.get('source') or 'resolved')
    return None, str(binding.get('source') or 'unresolved')


def _append_mes_machine_output(
    result: dict[tuple[int, int], dict[str, Any]],
    *,
    workshop: Workshop,
    machine: Equipment | SimpleNamespace,
    input_weight: float,
    output_weight: float,
    pass_count: int,
    source_basis: str,
    source_label: str,
    binding_source: str,
) -> None:
    key = (int(workshop.id), int(machine.id))
    bucket = result.setdefault(
        key,
        {
            'input': 0.0,
            'output': 0.0,
            'scrap': 0.0,
            'pass_count_total': 0,
            'row_count': 0,
            'machine_name': getattr(machine, 'name', None),
            'machine_binding_status': getattr(machine, 'machine_binding_status', None) or 'bound',
            'source_basis': source_basis,
            'source_label': source_label,
            'binding_sources': {},
        },
    )
    bucket['input'] += input_weight
    bucket['output'] += output_weight
    bucket['pass_count_total'] += pass_count
    bucket['row_count'] += 1
    binding_sources = bucket.setdefault('binding_sources', {})
    binding_sources[binding_source] = int(binding_sources.get(binding_source, 0)) + 1


def _load_mes_machine_output_scope(
    db: Session,
    *,
    business_date: date,
    workshops: list[Workshop],
    machines: list[Equipment],
) -> tuple[dict[tuple[int, int], dict[str, Any]], set[int]]:
    result: dict[tuple[int, int], dict[str, Any]] = {}
    if not workshops or not machines:
        return result, set()

    material_workshops = [
        workshop
        for workshop in workshops
        if normalize_workshop_name(workshop.name) in daily_overview_builder.BILLET_MATERIAL_WORKSHOP_MAPPINGS
    ]
    process_workshops = [
        workshop
        for workshop in workshops
        if normalize_workshop_name(workshop.name) not in daily_overview_builder.BILLET_MATERIAL_WORKSHOP_MAPPINGS
        and get_workshop_data_source_policy(workshop.name).get('primary_source') == 'mes'
    ]
    authoritative_workshop_ids: set[int] = set()
    if not material_workshops and not process_workshops:
        return result, authoritative_workshop_ids

    machine_by_id = {int(machine.id): machine for machine in machines if getattr(machine, 'id', None) is not None}
    machines_by_workshop: dict[int, list[Equipment]] = defaultdict(list)
    for machine in machines:
        if getattr(machine, 'workshop_id', None) is not None:
            machines_by_workshop[int(machine.workshop_id)].append(machine)
    aliases = _safe_equipment_aliases(db)
    terminal_bindings = _safe_terminal_bindings(db)

    if material_workshops:
        try:
            start_at, end_at = daily_overview_builder._billet_material_business_window(business_date, business_date)
            material_rows = (
                db.query(MesMaterialRecord)
                .filter(
                    MesMaterialRecord.production_date >= start_at,
                    MesMaterialRecord.production_date < end_at,
                )
                .order_by(MesMaterialRecord.id.asc())
                .all()
            )
        except (OperationalError, ProgrammingError):
            material_rows = []
        if material_rows:
            authoritative_workshop_ids.update(int(workshop.id) for workshop in material_workshops)
        for row in material_rows:
            output_weight = daily_overview_builder._mes_material_weight_tons(row)
            if output_weight <= 0:
                continue
            matched_workshop = next(
                (workshop for workshop in material_workshops if daily_overview_builder._mes_material_row_matches_workshop(row, workshop)),
                None,
            )
            if matched_workshop is None:
                continue
            process_hint = row.position_name or row.line_name or row.workshop_name
            machine, binding_source = _resolve_mes_output_machine(
                machines=machines,
                machine_by_id=machine_by_id,
                aliases=aliases,
                terminal_bindings=terminal_bindings,
                workshop=matched_workshop,
                device_name=row.line_name,
                process_hint=process_hint,
                terminal_hints=row.source_payload if isinstance(row.source_payload, dict) else {},
                event_time=row.production_date,
            )
            if machine is None and normalize_workshop_name(matched_workshop.name) == '热轧':
                machine = _preferred_hot_roll_material_machine(machines_by_workshop.get(int(matched_workshop.id), []))
                binding_source = 'hot_roll_material_default' if machine is not None else binding_source
            if machine is None:
                machine = _unresolved_mes_machine(
                    workshop=matched_workshop,
                    device_name=row.line_name,
                    process_hint=process_hint,
                )
            _append_mes_machine_output(
                result,
                workshop=matched_workshop,
                machine=machine,
                input_weight=output_weight,
                output_weight=output_weight,
                pass_count=1,
                source_basis='mes_material_records',
                source_label='外部 MES 坯料卷产量',
                binding_source=binding_source,
            )

    if process_workshops:
        try:
            process_rows = (
                db.query(MesWorkshopProcessRecord)
                .filter(MesWorkshopProcessRecord.business_date == business_date)
                .order_by(MesWorkshopProcessRecord.id.asc())
                .all()
            )
        except (OperationalError, ProgrammingError):
            process_rows = []
        if process_rows:
            authoritative_workshop_ids.update(int(workshop.id) for workshop in process_workshops)
        for row in process_rows:
            output_weight = daily_overview_builder._mes_output_tons(row)
            if output_weight <= 0:
                continue
            matched_workshop = next(
                (workshop for workshop in process_workshops if daily_overview_builder._mes_row_matches_workshop(row, workshop)),
                None,
            )
            if matched_workshop is None:
                continue
            machine, binding_source = _resolve_mes_output_machine(
                machines=machines,
                machine_by_id=machine_by_id,
                aliases=aliases,
                terminal_bindings=terminal_bindings,
                workshop=matched_workshop,
                device_name=row.device_name,
                process_hint=row.process_name,
                terminal_hints=row.source_payload if isinstance(row.source_payload, dict) else {},
                event_time=row.end_time,
            )
            if machine is None:
                machine = _unresolved_mes_machine(
                    workshop=matched_workshop,
                    device_name=row.device_name,
                    process_hint=row.process_name,
                )
            _append_mes_machine_output(
                result,
                workshop=matched_workshop,
                machine=machine,
                input_weight=daily_overview_builder._mes_input_tons(row),
                output_weight=output_weight,
                pass_count=daily_overview_builder._process_row_pass_count(row),
                source_basis='mes_workshop_process_records',
                source_label='外部 MES 过站产量',
                binding_source=binding_source,
            )

    for bucket in result.values():
        bucket['input'] = round(_to_float(bucket.get('input')), 2)
        bucket['output'] = round(_to_float(bucket.get('output')), 2)
        bucket['scrap'] = round(_to_float(bucket.get('scrap')), 2)
        bucket['pass_count_total'] = int(bucket.get('pass_count_total') or 0)
    return result, authoritative_workshop_ids


def _apply_mes_machine_output_authority(
    payload: dict,
    *,
    mes_machine_output: dict[tuple[int, int], dict[str, Any]],
    authoritative_workshop_ids: set[int] | None = None,
) -> dict:
    authoritative_workshop_ids = {int(item) for item in (authoritative_workshop_ids or set())}
    if not mes_machine_output and not authoritative_workshop_ids:
        return payload

    by_workshop: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    for (workshop_id, machine_id), bucket in mes_machine_output.items():
        by_workshop[int(workshop_id)][int(machine_id)] = bucket

    for workshop_payload in payload.get('workshops') or []:
        workshop_id = _optional_int(workshop_payload.get('workshop_id'))
        if workshop_id is None or workshop_id not in authoritative_workshop_ids:
            continue
        machine_buckets = by_workshop.get(workshop_id, {})
        workshop_input = 0.0
        workshop_output = 0.0
        workshop_scrap = 0.0
        workshop_pass_count = 0
        source_basis = 'mes_machine_output'
        source_label = '外部 MES 工艺/机台产量'
        visible_machine_ids: set[int] = set()

        for machine_payload in workshop_payload.get('machines') or []:
            machine_id = _optional_int(machine_payload.get('machine_id'))
            if machine_id is not None:
                visible_machine_ids.add(machine_id)
            bucket = machine_buckets.get(machine_id) if machine_id is not None else None
            day_total = dict(machine_payload.get('day_total') or {})
            if bucket is None:
                day_total.update(
                    {
                        'input': 0.0,
                        'output': 0.0,
                        'scrap': 0.0,
                        'yield_rate': None,
                        'yield_rate_source': 'mes_machine_output',
                        'source_basis': source_basis,
                        'source_label': source_label,
                    }
                )
                machine_payload['day_total'] = day_total
                continue

            input_total = _to_float(bucket.get('input'))
            output_total = _to_float(bucket.get('output'))
            scrap_total = _to_float(bucket.get('scrap'))
            workshop_input += input_total
            workshop_output += output_total
            workshop_scrap += scrap_total
            workshop_pass_count += int(bucket.get('pass_count_total') or 0)
            day_total.update(
                {
                    'input': round(input_total, 2),
                    'output': round(output_total, 2),
                    'scrap': round(scrap_total, 2),
                    'yield_rate': _round_rate(input_total, output_total),
                    'yield_rate_source': 'mes_machine_output',
                    'source_basis': bucket.get('source_basis') or source_basis,
                    'source_label': bucket.get('source_label') or source_label,
                    'row_count': int(bucket.get('row_count') or 0),
                    'binding_sources': dict(bucket.get('binding_sources') or {}),
                }
            )
            machine_payload['day_total'] = day_total

        for machine_id, bucket in sorted(machine_buckets.items(), key=lambda item: str(item[1].get('machine_name') or item[0])):
            if machine_id in visible_machine_ids:
                continue
            input_total = _to_float(bucket.get('input'))
            output_total = _to_float(bucket.get('output'))
            scrap_total = _to_float(bucket.get('scrap'))
            workshop_input += input_total
            workshop_output += output_total
            workshop_scrap += scrap_total
            workshop_pass_count += int(bucket.get('pass_count_total') or 0)
            workshop_payload.setdefault('machines', []).append(
                {
                    'machine_id': machine_id,
                    'machine_name': bucket.get('machine_name') or 'MES未匹配机台',
                    'machine_binding_status': bucket.get('machine_binding_status') or 'unbound',
                    'mes_binding': {
                        'status': 'unresolved',
                        'source_basis': bucket.get('source_basis') or source_basis,
                    },
                    'shifts': [],
                    'day_total': {
                        'input': round(input_total, 2),
                        'output': round(output_total, 2),
                        'scrap': round(scrap_total, 2),
                        'yield_rate': _round_rate(input_total, output_total),
                        'yield_rate_source': 'mes_machine_output',
                        'source_basis': bucket.get('source_basis') or source_basis,
                        'source_label': bucket.get('source_label') or source_label,
                        'row_count': int(bucket.get('row_count') or 0),
                        'binding_sources': dict(bucket.get('binding_sources') or {}),
                    },
                }
            )

        workshop_total = dict(workshop_payload.get('workshop_total') or {})
        workshop_total.update(
            {
                'input': round(workshop_input, 2),
                'output': round(workshop_output, 2),
                'process_output': round(workshop_output, 2),
                'scrap': round(workshop_scrap, 2),
                'yield_rate': _round_rate(workshop_input, workshop_output),
                'yield_rate_source': 'mes_machine_output',
                'pass_count_total': int(workshop_pass_count),
                'source_basis': source_basis,
                'source_label': source_label,
            }
        )
        workshop_payload['workshop_total'] = workshop_total

    factory_input = 0.0
    factory_output = 0.0
    factory_scrap = 0.0
    factory_pass_count = 0
    for workshop_payload in payload.get('workshops') or []:
        total = workshop_payload.get('workshop_total') or {}
        factory_input += _to_float(total.get('input'))
        factory_output += _to_float(total.get('output'))
        factory_scrap += _to_float(total.get('scrap'))
        factory_pass_count += int(total.get('pass_count_total') or 0)

    factory_total = dict(payload.get('factory_total') or {})
    factory_total.update(
        {
            'input': round(factory_input, 2),
            'output': round(factory_output, 2),
            'process_output': round(factory_output, 2),
            'scrap': round(factory_scrap, 2),
            'yield_rate': _round_rate(factory_input, factory_output),
            'yield_rate_source': 'mes_machine_output',
            'pass_count_total': int(factory_pass_count),
            'source_basis': 'mes_machine_output',
            'source_label': '外部 MES 工艺/机台产量',
        }
    )
    payload['factory_total'] = factory_total
    return payload


def _inject_mtd_into_payload(payload: dict, mtd: dict) -> dict:
    by_workshop = mtd.get('by_workshop') or {}
    empty = {
        'mtd_input': 0.0,
        'mtd_output': 0.0,
        'mtd_scrap': 0.0,
        'mtd_yield_rate': None,
        'mtd_pass_count_total': 0,
    }
    for workshop in payload.get('workshops') or []:
        ws_id = workshop.get('workshop_id')
        bucket = dict(by_workshop.get(int(ws_id), empty) if ws_id is not None else empty)
        if 'source_basis' in bucket:
            bucket['mtd_source_basis'] = bucket.pop('source_basis')
        if 'source_label' in bucket:
            bucket['mtd_source_label'] = bucket.pop('source_label')
        total = workshop.setdefault('workshop_total', {})
        total.update(bucket)
    factory_total = payload.setdefault('factory_total', {})
    factory_mtd = dict(mtd.get('factory') or {})
    if 'source_basis' in factory_mtd:
        factory_mtd['mtd_source_basis'] = factory_mtd.pop('source_basis')
    if 'source_label' in factory_mtd:
        factory_mtd['mtd_source_label'] = factory_mtd.pop('source_label')
    factory_total.update(factory_mtd)
    return payload


def _inject_factory_packaging_output(
    payload: dict,
    db: Session,
    *,
    business_date: date,
    scoped_workshop_id: int | None,
) -> dict:
    factory_total = payload.setdefault('factory_total', {})
    if scoped_workshop_id is not None:
        packaging_output = 0.0
        packaging_monthly_output = 0.0
        finished_inbound_output = 0.0
        daily_output_source = 'scoped_workshop'
    else:
        mes_home_fact = mes_home_packaging_fact.build_mes_home_packaging_fact(db, target_date=business_date)
        if mes_home_fact.get('daily_row_count'):
            packaging_output = mes_home_fact.get('mes_home_daily_output') or 0.0
            daily_output_source = 'mes_stock_header_records'
        else:
            packaging_by_date, sources_by_date = daily_overview_builder._query_mes_packaging_output_with_source_by_date(
                db,
                business_date,
                business_date,
            )
            packaging_output = packaging_by_date.get(business_date, 0.0)
            daily_output_source = sources_by_date.get(business_date, 'mes_stock_records')
        if mes_home_fact.get('month_row_count'):
            packaging_monthly_output = mes_home_fact.get('mes_home_month_to_date_output') or 0.0
        else:
            month_start = business_date.replace(day=1)
            packaging_month_by_date, _month_sources = daily_overview_builder._query_mes_packaging_output_with_source_by_date(
                db,
                month_start,
                business_date,
            )
            packaging_monthly_output = sum(packaging_month_by_date.values())
        finished_inbound_output = daily_overview_builder._query_finished_inbound_totals_by_date(
            db,
            business_date,
            business_date,
        ).get(business_date, 0.0)

    factory_total.update({
        'packaging_output': round(packaging_output, 2),
        'daily_output': round(packaging_output, 2),
        'factory_total_output': round(packaging_output, 2),
        'packaging_monthly_output': round(packaging_monthly_output, 2),
        'month_to_date_output': round(packaging_monthly_output, 2),
        'finished_inbound_output': round(finished_inbound_output, 2),
        'owner_storage_finished_weight': round(finished_inbound_output, 2),
        'business_day_start': '07:30',
        'daily_output_source': daily_output_source,
        'finished_inbound_source': 'storage_owner_daily_entry',
    })
    return payload


def _iso_datetime(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _append_search_text(row: dict) -> dict:
    values = [
        row.get('source_label'),
        row.get('tracking_card_no'),
        row.get('workshop_name'),
        row.get('machine_name'),
        row.get('shift_name'),
        row.get('responsible_name'),
        row.get('responsible_username'),
        row.get('status'),
        row.get('entry_type'),
    ]
    for metric in row.get('metrics') or []:
        values.extend([metric.get('label'), metric.get('value'), metric.get('unit')])
    row['search_text'] = ' '.join(str(item) for item in values if item not in (None, ''))
    return row


def _fill_source_label(source_type: str) -> str:
    return {
        'work_order_entry': '扫码卷明细',
        'owner_daily': '内勤每日',
        'mobile_shift_report': '班次汇总',
        'machine_energy': '机台能耗',
        'mes_projection': '外部 MES',
        'local_shift_data': '班次产量',
    }.get(source_type, '填报明细')


def _user_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.name or user.username


def build_fill_detail_ledger(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
    current_user: User,
    search: str | None = None,
    limit: int = 800,
) -> dict:
    scoped_workshop_id = _resolve_workshop_filter(current_user=current_user, workshop_id=workshop_id)
    safe_limit = min(max(int(limit or 800), 1), 2000)
    needle = str(search or '').strip().lower()
    items: list[dict[str, Any]] = []

    machine_name_by_id = {item.id: item.name for item in db.query(Equipment).filter(Equipment.is_active.is_(True)).all()}

    energy_user = aliased(User)
    energy_rows_query = (
        db.query(MachineEnergyRecord, MobileShiftReport, Workshop, ShiftConfig, energy_user)
        .join(MobileShiftReport, MobileShiftReport.id == MachineEnergyRecord.shift_report_id)
        .join(Workshop, Workshop.id == MobileShiftReport.workshop_id)
        .join(ShiftConfig, ShiftConfig.id == MobileShiftReport.shift_config_id)
        .outerjoin(energy_user, energy_user.id == MobileShiftReport.submitted_by_user_id)
        .filter(MobileShiftReport.business_date == business_date)
    )
    if scoped_workshop_id is not None:
        energy_rows_query = energy_rows_query.filter(MobileShiftReport.workshop_id == scoped_workshop_id)
    machine_energy_report_ids: set[int] = set()
    energy_rows_query = energy_rows_query.order_by(MachineEnergyRecord.id.desc())
    if not needle:
        energy_rows_query = energy_rows_query.limit(safe_limit)
    for energy, report, workshop, shift, user in energy_rows_query.all():
        machine_energy_report_ids.add(int(report.id))
        source_type = 'machine_energy'
        row = {
            'row_id': f'machine-energy-{energy.id}',
            'source_type': source_type,
            'source_label': _fill_source_label(source_type),
            'report_id': report.id,
            'business_date': business_date.isoformat(),
            'workshop_id': report.workshop_id,
            'workshop_name': workshop.name,
            'machine_id': energy.machine_id,
            'machine_name': energy.machine_name or machine_name_by_id.get(energy.machine_id) or '未标记机列',
            'shift_id': report.shift_config_id,
            'shift_name': shift.name,
            'responsible_user_id': getattr(user, 'id', None),
            'responsible_name': _user_name(user) or report.leader_name,
            'responsible_username': getattr(user, 'username', None),
            'status': report.report_status,
            'entry_type': source_type,
            'energy_kwh': round(_to_float(energy.energy_kwh), 3) if energy.energy_kwh is not None else None,
            'gas_m3': round(_to_float(energy.gas_m3), 3) if energy.gas_m3 is not None else None,
            'submitted_at': _iso_datetime(report.submitted_at),
            'updated_at': _iso_datetime(energy.updated_at),
        }
        items.append(_append_search_text(row))

    creator_user = aliased(User)
    entry_rows_query = (
        db.query(WorkOrderEntry, WorkOrder, Workshop, Equipment, ShiftConfig, creator_user)
        .join(WorkOrder, WorkOrder.id == WorkOrderEntry.work_order_id)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .outerjoin(Equipment, Equipment.id == WorkOrderEntry.machine_id)
        .outerjoin(ShiftConfig, ShiftConfig.id == WorkOrderEntry.shift_id)
        .outerjoin(creator_user, creator_user.id == func.coalesce(WorkOrderEntry.created_by_user_id, WorkOrderEntry.created_by))
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.entry_type != 'mes_projection',
        )
    )
    if scoped_workshop_id is not None:
        entry_rows_query = entry_rows_query.filter(WorkOrderEntry.workshop_id == scoped_workshop_id)
    entry_rows_query = entry_rows_query.order_by(WorkOrderEntry.updated_at.desc(), WorkOrderEntry.id.desc())
    if not needle:
        entry_rows_query = entry_rows_query.limit(safe_limit)
    for entry, work_order, workshop, machine, shift, user in entry_rows_query.all():
        source_type = 'owner_daily' if entry.entry_type == OWNER_DAILY_ENTRY_TYPE else 'work_order_entry'
        input_weight = _entry_weight_kg_to_tons(entry, 'input_weight')
        output_weight = _entry_weight_kg_to_tons(entry, 'output_weight')
        scrap_weight = _entry_weight_kg_to_tons(entry, 'scrap_weight')
        field_meta, field_types = _workshop_field_context(workshop)
        metrics = _extra_payload_metrics(entry.extra_payload or {}, field_meta=field_meta, field_types=field_types)
        row = {
            'row_id': f'entry-{entry.id}',
            'source_type': source_type,
            'source_label': _fill_source_label(source_type),
            'entry_id': entry.id,
            'tracking_card_no': work_order.tracking_card_no,
            'business_date': entry.business_date.isoformat(),
            'workshop_id': entry.workshop_id,
            'workshop_name': workshop.name,
            'machine_id': entry.machine_id,
            'machine_name': '内勤岗' if source_type == 'owner_daily' else (machine.name if machine else '未绑定机列'),
            'shift_id': entry.shift_id,
            'shift_name': shift.name if shift else None,
            'responsible_user_id': getattr(user, 'id', None),
            'responsible_name': _user_name(user),
            'responsible_username': getattr(user, 'username', None),
            'status': entry.entry_status,
            'entry_type': entry.entry_type,
            'input_weight': round(input_weight, 3) if input_weight else None,
            'output_weight': round(output_weight, 3) if output_weight else None,
            'scrap_weight': round(scrap_weight, 3) if scrap_weight else None,
            'yield_rate': _round_rate(input_weight, output_weight),
            'energy_kwh': round(_to_float(entry.energy_kwh), 3) if entry.energy_kwh is not None else None,
            'gas_m3': round(_to_float(entry.gas_m3), 3) if entry.gas_m3 is not None else None,
            'submitted_at': _iso_datetime(entry.submitted_at),
            'updated_at': _iso_datetime(entry.updated_at),
            'metrics': metrics,
        }
        items.append(_append_search_text(row))

    owner_user = aliased(User)
    submitter_user = aliased(User)
    report_rows_query = (
        db.query(MobileShiftReport, Workshop, ShiftConfig, owner_user, submitter_user)
        .join(Workshop, Workshop.id == MobileShiftReport.workshop_id)
        .join(ShiftConfig, ShiftConfig.id == MobileShiftReport.shift_config_id)
        .outerjoin(owner_user, owner_user.id == MobileShiftReport.owner_user_id)
        .outerjoin(submitter_user, submitter_user.id == MobileShiftReport.submitted_by_user_id)
        .filter(MobileShiftReport.business_date == business_date)
    )
    if scoped_workshop_id is not None:
        report_rows_query = report_rows_query.filter(MobileShiftReport.workshop_id == scoped_workshop_id)
    report_rows_query = report_rows_query.order_by(MobileShiftReport.updated_at.desc(), MobileShiftReport.id.desc())
    if not needle:
        report_rows_query = report_rows_query.limit(safe_limit)
    for report, workshop, shift, owner, submitter in report_rows_query.all():
        source_type = 'mobile_shift_report'
        report_has_machine_energy = int(report.id) in machine_energy_report_ids
        row = {
            'row_id': f'mobile-report-{report.id}',
            'source_type': source_type,
            'source_label': _fill_source_label(source_type),
            'report_id': report.id,
            'business_date': report.business_date.isoformat(),
            'workshop_id': report.workshop_id,
            'workshop_name': workshop.name,
            'machine_name': '班次汇总',
            'shift_id': report.shift_config_id,
            'shift_name': shift.name,
            'responsible_user_id': getattr(submitter or owner, 'id', None),
            'responsible_name': _user_name(submitter) or _user_name(owner) or report.leader_name,
            'responsible_username': getattr(submitter or owner, 'username', None),
            'status': report.report_status,
            'entry_type': source_type,
            'input_weight': round(_to_float(report.input_weight), 3) if report.input_weight is not None else None,
            'output_weight': round(_to_float(report.output_weight), 3) if report.output_weight is not None else None,
            'scrap_weight': round(_to_float(report.scrap_weight), 3) if report.scrap_weight is not None else None,
            'energy_kwh': None if report_has_machine_energy else (round(_to_float(report.electricity_daily), 3) if report.electricity_daily is not None else None),
            'gas_m3': None if report_has_machine_energy else (round(_to_float(report.gas_daily), 3) if report.gas_daily is not None else None),
            'submitted_at': _iso_datetime(report.submitted_at),
            'updated_at': _iso_datetime(report.updated_at),
        }
        items.append(_append_search_text(row))

    if needle:
        items = [item for item in items if needle in str(item.get('search_text') or '').lower()]

    items.sort(key=lambda item: (item.get('updated_at') or item.get('submitted_at') or '', item.get('row_id') or ''), reverse=True)
    visible_items = items[:safe_limit]
    source_counts: dict[str, int] = defaultdict(int)
    machine_ids: set[int] = set()
    owner_keys: set[str] = set()
    output_total = 0.0
    energy_total = 0.0
    gas_total = 0.0
    for item in visible_items:
        source_counts[str(item.get('source_type') or 'unknown')] += 1
        if item.get('machine_id') is not None:
            machine_ids.add(int(item['machine_id']))
        owner_key = item.get('responsible_user_id') or item.get('responsible_username') or item.get('responsible_name')
        if owner_key:
            owner_keys.add(str(owner_key))
        if item.get('source_type') in {'work_order_entry', 'local_shift_data'}:
            output_total += _to_float(item.get('output_weight'))
        energy_total += _to_float(item.get('energy_kwh'))
        gas_total += _to_float(item.get('gas_m3'))
        if item.get('energy_kwh') is None:
            energy_total += _metric_total(item.get('metrics') or [], {'total_electricity_kwh'})
        if item.get('gas_m3') is None:
            gas_total += _metric_total(item.get('metrics') or [], {'total_gas_m3'})

    return {
        'business_date': business_date.isoformat(),
        'workshop_id': scoped_workshop_id,
        'total': len(visible_items),
        'summary': {
            'entry_count': len(visible_items),
            'machine_count': len(machine_ids),
            'owner_count': len(owner_keys),
            'output': round(output_total, 3),
            'energy_kwh': round(energy_total, 3),
            'gas_m3': round(gas_total, 3),
            'source_counts': dict(source_counts),
        },
        'items': visible_items,
    }


def build_pending_assignment_detail(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
    current_user: User,
) -> dict:
    scoped_workshop_id = _resolve_workshop_filter(current_user=current_user, workshop_id=workshop_id)
    query = (
        db.query(WorkOrderEntry, WorkOrder, Workshop, ShiftConfig)
        .join(WorkOrder, WorkOrder.id == WorkOrderEntry.work_order_id)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .outerjoin(ShiftConfig, ShiftConfig.id == WorkOrderEntry.shift_id)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.entry_type != OWNER_DAILY_ENTRY_TYPE,
            or_(WorkOrderEntry.machine_id.is_(None), WorkOrderEntry.shift_id.is_(None)),
        )
    )
    if scoped_workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == scoped_workshop_id)

    items = []
    input_total = 0.0
    output_total = 0.0
    scrap_total = 0.0
    draft_count = 0
    formal_count = 0
    missing_machine_count = 0
    missing_shift_count = 0

    rows = query.order_by(Workshop.sort_order.asc(), Workshop.id.asc(), WorkOrderEntry.id.desc()).all()
    creator_ids = {entry.created_by_user_id for entry, _work_order, _workshop, _shift in rows if entry.created_by_user_id}
    creator_by_id = {
        item.id: item
        for item in db.query(User).filter(User.id.in_(creator_ids)).all()
    } if creator_ids else {}
    workshop_ids = {entry.workshop_id for entry, _work_order, _workshop, _shift in rows if entry.workshop_id}
    machine_candidates_by_workshop: dict[int, list[Equipment]] = defaultdict(list)
    if workshop_ids:
        machine_rows = (
            db.query(Equipment)
            .filter(
                Equipment.workshop_id.in_(workshop_ids),
                Equipment.is_active.is_(True),
                Equipment.operational_status == 'running',
            )
            .order_by(Equipment.sort_order.asc(), Equipment.id.asc())
            .all()
        )
        for machine in machine_rows:
            equipment_type = str(machine.equipment_type or '').strip().lower()
            if equipment_type in {'virtual_workshop_qr', 'virtual_role_qr'}:
                continue
            machine_candidates_by_workshop[machine.workshop_id].append(machine)
    machine_name_by_id = {
        machine.id: machine.name
        for candidates in machine_candidates_by_workshop.values()
        for machine in candidates
    }
    tracking_cards = {work_order.tracking_card_no for _entry, work_order, _workshop, _shift in rows if work_order.tracking_card_no}
    mes_rows = _load_mes_snapshot_rows(
        db,
        business_date=business_date,
        workshop_id=scoped_workshop_id,
        tracking_card_nos=tracking_cards,
    ) if tracking_cards else []
    mes_rows_by_card: dict[str, list[dict]] = defaultdict(list)
    for mes_row in mes_rows:
        for card_key in _entry_tracking_keys(mes_row):
            mes_rows_by_card[card_key].append(mes_row)

    for entry, work_order, workshop, shift in rows:
        input_weight = _entry_weight_kg_to_tons(entry, 'input_weight')
        output_weight = _entry_weight_kg_to_tons(entry, 'output_weight')
        scrap_weight = _entry_weight_kg_to_tons(entry, 'scrap_weight')
        input_total += input_weight
        output_total += output_weight
        scrap_total += scrap_weight

        missing_fields = []
        if entry.machine_id is None:
            missing_fields.append('machine_id')
            missing_machine_count += 1
        if entry.shift_id is None:
            missing_fields.append('shift_id')
            missing_shift_count += 1

        entry_status = entry.entry_status
        entry_type = entry.entry_type
        is_formal = _is_formal_entry({'entry_status': entry_status, 'entry_type': entry_type})
        formal_count += 1 if is_formal else 0
        draft_count += 1 if entry_status == 'draft' else 0
        creator = creator_by_id.get(entry.created_by_user_id)
        machine_candidates = machine_candidates_by_workshop.get(entry.workshop_id, [])
        mes_matches_by_id: dict[Any, dict] = {}
        for card_key in _tracking_card_keys(work_order.tracking_card_no):
            for item in mes_rows_by_card.get(card_key, []):
                if item.get('workshop_id') in {None, entry.workshop_id}:
                    mes_matches_by_id.setdefault(item.get('id'), item)
        mes_matches = list(mes_matches_by_id.values())
        mes_machine_id = None
        mes_machine_name = None
        for mes_item in mes_matches:
            if mes_item.get('machine_id') is not None:
                mes_machine_id = mes_item.get('machine_id')
                mes_machine_name = machine_name_by_id.get(mes_machine_id)
                break
        items.append(
            {
                'entry_id': entry.id,
                'work_order_id': entry.work_order_id,
                'tracking_card_no': work_order.tracking_card_no,
                'business_date': entry.business_date.isoformat(),
                'workshop_id': entry.workshop_id,
                'workshop_name': workshop.name,
                'shift_id': entry.shift_id,
                'shift_name': shift.name if shift is not None else None,
                'machine_id': entry.machine_id,
                'entry_status': entry_status,
                'entry_type': entry_type,
                'input_weight': round(input_weight, 2),
                'output_weight': round(output_weight, 2),
                'scrap_weight': round(scrap_weight, 2),
                'missing_fields': missing_fields,
                'created_by_user_id': entry.created_by_user_id,
                'created_by_user_name': creator.name if creator is not None else None,
                'created_by_username': creator.username if creator is not None else None,
                'mes_match_count': len(mes_matches),
                'mes_machine_id': mes_machine_id,
                'mes_machine_name': mes_machine_name,
                'machine_candidate_count': len(machine_candidates),
                'machine_candidate_names': [machine.name for machine in machine_candidates[:5]],
                'machine_candidates': [
                    {'machine_id': machine.id, 'machine_name': machine.name}
                    for machine in machine_candidates
                ],
                'created_at': _iso_datetime(entry.created_at),
            }
        )

    return {
        'business_date': business_date.isoformat(),
        'workshop_id': scoped_workshop_id,
        'total': len(items),
        'summary': {
            'entry_count': len(items),
            'draft_entry_count': draft_count,
            'formal_entry_count': formal_count,
            'missing_machine_count': missing_machine_count,
            'missing_shift_count': missing_shift_count,
            'input': round(input_total, 2),
            'output': round(output_total, 2),
            'scrap': round(scrap_total, 2),
        },
        'items': items,
    }


def _load_local_shift_rows(db: Session, *, business_date: date, workshop_id: int | None) -> list[ShiftProductionData]:
    query = db.query(ShiftProductionData).filter(
        ShiftProductionData.business_date == business_date,
        ShiftProductionData.data_source == LOCAL_SHIFT_DATA_SOURCE,
        ShiftProductionData.data_status.in_(LOCAL_SHIFT_DATA_STATUSES),
    )
    if workshop_id is not None:
        query = query.filter(ShiftProductionData.workshop_id == workshop_id)
    return query.all()


def _unbound_shift_machine_id(workshop_id: int, shift_id: int) -> int:
    return -((int(workshop_id) * 1000) + int(shift_id))


def _build_local_shift_runtime_inputs(*, machines, shifts, rows) -> tuple[list, list[dict]]:
    machine_items = list(machines)
    machine_by_id = {int(item.id): item for item in machine_items if getattr(item, 'id', None) is not None}
    candidates_by_workshop: dict[int, list] = defaultdict(list)
    for machine in machine_items:
        if getattr(machine, 'workshop_id', None) is not None:
            candidates_by_workshop[int(machine.workshop_id)].append(machine)
    shift_by_id = {int(item.id): item for item in shifts if getattr(item, 'id', None) is not None}
    unbound_keys: set[tuple[int, int]] = set()
    entries: list[dict] = []

    for row in rows:
        workshop_id = getattr(row, 'workshop_id', None)
        shift_id = getattr(row, 'shift_config_id', None)
        if workshop_id is None or shift_id is None:
            continue
        workshop_id = int(workshop_id)
        shift_id = int(shift_id)
        machine_id = getattr(row, 'equipment_id', None)
        if machine_id is None:
            machine_id = _unbound_shift_machine_id(workshop_id, shift_id)
            key = (workshop_id, shift_id)
            if key not in unbound_keys:
                shift = shift_by_id.get(shift_id)
                shift_name = getattr(shift, 'name', None) or f'{shift_id}班'
                shift_sort = int(getattr(shift, 'sort_order', shift_id) or shift_id)
                machine_items.append(
                    SimpleNamespace(
                        id=machine_id,
                        workshop_id=workshop_id,
                        name=f'未绑定机列 / {shift_name}',
                        machine_binding_status='unbound',
                        assigned_shift_ids=[shift_id],
                        sort_order=100000 + shift_sort,
                    )
                )
                unbound_keys.add(key)
        else:
            raw_machine_id = int(machine_id)
            machine = machine_by_id.get(raw_machine_id)
            reporting_machine = resolve_reporting_machine_from_candidates(machine, candidates_by_workshop.get(workshop_id, []))
            machine_id = int(getattr(reporting_machine, 'id', raw_machine_id) or raw_machine_id)

        business_date_value = getattr(row, 'business_date', None)
        yield_value = getattr(row, 'yield_rate', None)
        entries.append(
            {
                'id': getattr(row, 'id', None),
                'tracking_card_no': f"SHIFT-{getattr(row, 'id', '')}",
                'work_order_id': None,
                'workshop_id': workshop_id,
                'machine_id': machine_id,
                'shift_id': shift_id,
                'business_date': business_date_value.isoformat() if business_date_value else None,
                'input_weight': _to_float(getattr(row, 'input_weight', None)),
                'output_weight': _to_float(getattr(row, 'output_weight', None)),
                'scrap_weight': _to_float(getattr(row, 'scrap_weight', None)),
                'yield_rate': float(yield_value) if yield_value is not None else None,
                'yield_rate_source': 'local_shift_data',
                'entry_status': 'submitted',
                'entry_type': LOCAL_SHIFT_DATA_SOURCE,
                'weight_unit': 'kg',
                'tracking_card_status': getattr(row, 'data_status', None) or 'pending',
                'data_source': LOCAL_SHIFT_DATA_SOURCE,
            }
        )

    return machine_items, entries


def _drop_local_entries_for_existing_cells(entry_rows: list[dict], local_entries: list[dict]) -> list[dict]:
    occupied = {
        (item.get('workshop_id'), item.get('machine_id'), item.get('shift_id'))
        for item in entry_rows
        if item.get('workshop_id') is not None and item.get('machine_id') is not None and item.get('shift_id') is not None
    }
    return [
        item
        for item in local_entries
        if (item.get('workshop_id'), item.get('machine_id'), item.get('shift_id')) not in occupied
    ]


def _tracking_card_key(value) -> str:
    return tracking_card_lookup_key(value)


def _tracking_card_keys(value) -> set[str]:
    return tracking_card_lookup_candidates(value)


def _entry_tracking_keys(item: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for field_name in ('tracking_card_no', 'batch_no', 'material_code', 'coil_id'):
        keys.update(_tracking_card_keys(item.get(field_name)))
    for value in item.get('tracking_card_keys') or []:
        keys.update(_tracking_card_keys(value))
    return keys


def _same_entry_business_date(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_date = str(left.get('business_date') or '').strip()
    right_date = str(right.get('source_business_date') or '').strip()
    return bool(left_date and right_date and left_date == right_date)


def _merge_runtime_entries(*, entry_rows: list[dict], local_entries: list[dict], mes_rows: list[dict]) -> tuple[list[dict], str]:
    mes_rows_by_card: dict[str, dict[Any, dict]] = defaultdict(dict)
    for item in mes_rows:
        for card_key in _entry_tracking_keys(item):
            mes_rows_by_card[card_key].setdefault(item.get('id'), item)

    def apply_mes_binding(items: list[dict]) -> tuple[list[dict], bool]:
        enriched: list[dict] = []
        has_mes_match = False
        for item in items:
            mes_matches_by_id: dict[Any, dict] = {}
            for card_key in _entry_tracking_keys(item):
                mes_matches_by_id.update(mes_rows_by_card.get(card_key, {}))
            if not mes_matches_by_id:
                enriched.append(item)
                continue
            mes_matches = list(mes_matches_by_id.values())
            updated = dict(item)
            current_workshop_id = updated.get('workshop_id')
            matched_mes_rows = [
                mes_item
                for mes_item in mes_matches
                if mes_item.get('workshop_id') is None or current_workshop_id is None or current_workshop_id == mes_item.get('workshop_id')
            ]
            if not matched_mes_rows:
                enriched.append(item)
                continue

            has_mes_match = True
            mes_item = next((row for row in matched_mes_rows if row.get('machine_id') is not None), matched_mes_rows[0])
            updated['mes_match_count'] = len(matched_mes_rows)
            updated['mes_machine_id'] = mes_item.get('machine_id')
            updated['mes_machine_binding_source'] = mes_item.get('machine_binding_source') or 'unresolved'
            for field_name in ('workshop_id', 'machine_id', 'shift_id'):
                if updated.get(field_name) is None and mes_item.get(field_name) is not None:
                    updated[field_name] = mes_item[field_name]
            if _same_entry_business_date(updated, mes_item):
                has_mes_weight = False
                for field_name in ('input_weight', 'output_weight', 'scrap_weight'):
                    if mes_item.get(field_name) is None:
                        continue
                    updated[field_name] = mes_item[field_name]
                    has_mes_weight = True
                if has_mes_weight:
                    updated['weight_unit'] = 'tons'
                    updated['weight_source'] = 'mes_projection'
                    updated['mes_weight_authority'] = True
            enriched.append(updated)
        return enriched, has_mes_match

    entry_rows, entry_has_mes_binding = apply_mes_binding(entry_rows)
    local_entries, local_has_mes_binding = apply_mes_binding(local_entries)
    has_mes_binding = entry_has_mes_binding or local_has_mes_binding
    fill_tracking_cards = {
        card_key
        for item in [*entry_rows, *local_entries]
        for card_key in _entry_tracking_keys(item)
    }
    filtered_mes_rows = [
        item
        for item in mes_rows
        if not (_entry_tracking_keys(item) & fill_tracking_cards)
    ]
    entries = [*entry_rows, *local_entries, *filtered_mes_rows]
    has_fill = bool(entry_rows or local_entries)
    has_mes = bool(filtered_mes_rows)
    if has_fill and (has_mes or has_mes_binding):
        return entries, 'mixed'
    if has_mes:
        return entries, 'mes_projection'
    if local_entries:
        return entries, 'local_shift_data'
    return entries, 'work_order_runtime'


def _build_mes_machine_binding_summary(
    *,
    mes_rows: list[dict],
    entries: list[dict],
    pending_assignment: dict | None,
    business_date: date | None = None,
) -> dict:
    target_business_date = business_date.isoformat() if business_date is not None else None
    summary_mes_rows = [
        item
        for item in mes_rows
        if target_business_date is None
        or str(item.get('source_business_date') or item.get('business_date') or '') == target_business_date
    ]
    mes_row_count = len(summary_mes_rows)
    mes_rows_with_machine = len([item for item in summary_mes_rows if item.get('machine_id') is not None])
    source_counts: dict[str, int] = defaultdict(int)
    for item in summary_mes_rows:
        source_counts[str(item.get('machine_binding_source') or 'unresolved')] += 1

    fill_entries = [item for item in entries if item.get('entry_type') != 'mes_projection']
    fill_entries_with_mes_match = 0
    fill_entries_bound_to_machine = 0
    fill_entries_pending_machine = 0
    for item in fill_entries:
        if int(item.get('mes_match_count') or 0) <= 0:
            continue
        fill_entries_with_mes_match += 1
        if item.get('machine_id') is not None:
            fill_entries_bound_to_machine += 1
        else:
            fill_entries_pending_machine += 1

    pending_payload = pending_assignment or {}
    return {
        'mes_row_count': mes_row_count,
        'mes_rows_with_machine': mes_rows_with_machine,
        'mes_rows_without_machine': mes_row_count - mes_rows_with_machine,
        'direct_machine_code_count': int(source_counts.get('direct_machine_code', 0)),
        'route_inferred_machine_count': int(source_counts.get('route_inferred', 0)),
        'unresolved_machine_count': int(source_counts.get('unresolved', 0)),
        'upstream_machine_code_missing_count': len([item for item in summary_mes_rows if item.get('upstream_machine_code_missing')]),
        'fill_entry_count': len(fill_entries),
        'fill_entries_with_mes_match': fill_entries_with_mes_match,
        'fill_entries_bound_to_machine': fill_entries_bound_to_machine,
        'fill_entries_pending_machine': fill_entries_pending_machine,
        'pending_assignment_entry_count': int(pending_payload.get('entry_count') or 0),
        'pending_machine_assignment_count': int(pending_payload.get('missing_machine_count') or 0),
    }


def _mes_snapshot_tracking_keys(item: MesCoilSnapshot) -> set[str]:
    values = [
        getattr(item, 'tracking_card_no', None),
        getattr(item, 'batch_no', None),
        getattr(item, 'material_code', None),
        getattr(item, 'coil_id', None),
        getattr(item, 'qr_code', None),
    ]
    source_payload = getattr(item, 'source_payload', None)
    if isinstance(source_payload, Mapping):
        values.extend(
            source_payload.get(key)
            for key in (
                'MaterialCode',
                'material_code',
                'TrackingCardNo',
                'tracking_card_no',
                'CardNo',
                'card_no',
                'PrintCardNo',
                'print_card_no',
                'BatchNo',
                'batch_no',
            )
        )
    keys: set[str] = set()
    for value in values:
        keys.update(_tracking_card_keys(value))
    return keys


VIRTUAL_QR_EQUIPMENT_TYPES = {'virtual_workshop_qr', 'virtual_role_qr'}
MES_PROCESS_MACHINE_TYPE_HINTS = (
    (('冷轧',), {'cold_mill'}),
    (('北线退火', '南线退火', '在线退火', '退火'), {'annealing_line'}),
    (('纵剪', '分切'), {'slitter'}),
    (('重卷',), {'recoiler'}),
    (('拉矫', '洗拉'), {'straightener'}),
    (('横剪',), {'cross_cut'}),
    (('飞剪',), {'fly_cut'}),
    (('剪切',), {'shear', 'cross_cut', 'fly_cut'}),
    (('铣',), {'milling'}),
    (('锯',), {'sawing'}),
    (('热轧',), {'hot_mill'}),
)


def _is_physical_machine(machine: Equipment) -> bool:
    equipment_type = str(getattr(machine, 'equipment_type', '') or '').strip().lower()
    return equipment_type not in VIRTUAL_QR_EQUIPMENT_TYPES


def _infer_mes_machine_id_from_route(*, machines: list[Equipment], process_hint: object | None) -> int | None:
    physical_machines = [machine for machine in machines if _is_physical_machine(machine)]
    if len(physical_machines) == 1:
        return physical_machines[0].id

    process_text = str(process_hint or '').strip()
    if not process_text:
        return None

    for keywords, equipment_types in MES_PROCESS_MACHINE_TYPE_HINTS:
        if not any(keyword in process_text for keyword in keywords):
            continue
        matches = [
            machine
            for machine in physical_machines
            if str(getattr(machine, 'equipment_type', '') or '').strip().lower() in equipment_types
        ]
        directional = _match_directional_mes_route_hint(machines=matches, process_hint=process_text)
        if directional is not None:
            return directional.id
        if len(matches) == 1:
            return matches[0].id
        return None
    return None


def _normalize_mes_machine_text(value: object | None) -> str:
    return str(value or '').strip().upper().replace(' ', '')


def _match_directional_mes_route_hint(*, machines: list[Equipment], process_hint: str) -> Equipment | None:
    direction_markers: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
        (('北', 'north'), ('北', 'NORTH', 'N线', 'N#', '-N', '_N')),
        (('南', 'south'), ('南', 'SOUTH', 'S线', 'S#', '-S', '_S')),
    )
    for hint_markers, machine_markers in direction_markers:
        if not any(marker in process_hint for marker in hint_markers):
            continue
        candidates = []
        for machine in machines:
            text = f"{_normalize_mes_machine_text(getattr(machine, 'code', None))} {_normalize_mes_machine_text(getattr(machine, 'name', None))}"
            if any(marker in text for marker in machine_markers):
                candidates.append(machine)
        if len(candidates) == 1:
            return candidates[0]
    return None


def _load_mes_snapshot_rows(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
    tracking_card_nos: set[str] | None = None,
) -> list[dict]:
    workshop_rows = db.query(Workshop).filter(Workshop.is_active.is_(True)).all()
    workshop_id_by_code = {str(item.code or '').strip().upper(): item.id for item in workshop_rows if item.code}
    workshop_name_by_id = {item.id: item.name for item in workshop_rows}
    machine_rows = db.query(Equipment).filter(Equipment.is_active.is_(True)).all()
    machine_id_by_code = {str(item.code or '').strip().upper(): item.id for item in machine_rows if item.code}
    machines_by_workshop: dict[int, list[Equipment]] = defaultdict(list)
    for machine in machine_rows:
        machines_by_workshop[machine.workshop_id].append(machine)
    equipment_aliases = (
        db.query(MasterCodeAlias)
        .filter(
            MasterCodeAlias.entity_type == 'equipment',
            MasterCodeAlias.is_active.is_(True),
        )
        .all()
    )
    try:
        terminal_bindings = db.query(MesTerminalBinding).filter(MesTerminalBinding.is_active.is_(True)).all()
    except (OperationalError, ProgrammingError):
        terminal_bindings = []
    shift_rows = db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).all()
    shift_id_by_code = {str(item.code or '').strip().upper(): item.id for item in shift_rows if item.code}
    work_order_by_card: dict[str, WorkOrder] = {}
    for item in db.query(WorkOrder).all():
        for card_key in _tracking_card_keys(item.tracking_card_no):
            work_order_by_card.setdefault(card_key, item)
    resolved_workshop_code_by_raw: dict[str, str] = {}
    resolved_machine_code_by_raw: dict[str, str] = {}

    def resolve_mes_code(entity_type: str, raw_code: object | None, cache: dict[str, str]) -> str:
        raw_text = str(raw_code or '').strip()
        if raw_text not in cache:
            cache[raw_text] = master_service.resolve_canonical_code(
                db,
                entity_type=entity_type,
                value=raw_text,
                source_type='mes_mvc',
            ) or raw_text
        return cache[raw_text]

    def resolve_snapshot_workshop_id(item: MesCoilSnapshot) -> int | None:
        raw_workshop = item.workshop_code or item.current_workshop or item.next_workshop
        canonical_workshop_code = resolve_mes_code('workshop', raw_workshop, resolved_workshop_code_by_raw)
        return workshop_id_by_code.get(canonical_workshop_code.strip().upper())

    def resolve_snapshot_machine_binding(item: MesCoilSnapshot, resolved_workshop_id: int | None) -> tuple[int | None, str]:
        canonical_machine_code = resolve_mes_code('equipment', item.machine_code, resolved_machine_code_by_raw)
        direct_machine_id = machine_id_by_code.get(canonical_machine_code.strip().upper())
        if direct_machine_id is not None:
            return direct_machine_id, 'direct_machine_code'
        if resolved_workshop_id is None:
            return None, 'unresolved'
        process_hint = item.current_process or item.process_code or item.next_process
        raw_workshop = item.workshop_code or item.current_workshop or item.next_workshop
        binding = mes_machine_match_service.resolve_mes_machine_binding(
            machines=machine_rows,
            device_name=item.machine_code,
            process_hint=process_hint,
            preferred_workshop_id=resolved_workshop_id,
            aliases=equipment_aliases,
            terminal_bindings=terminal_bindings,
            terminal_hints=item.source_payload if isinstance(item.source_payload, dict) else {},
            workshop_name=workshop_name_by_id.get(resolved_workshop_id) or raw_workshop,
            event_time=item.event_time or item.updated_from_mes_at,
        )
        if binding.get('machine_id') is not None:
            return int(binding['machine_id']), str(binding.get('source') or 'route_inferred')
        inferred_machine_id = _infer_mes_machine_id_from_route(
            machines=machines_by_workshop.get(resolved_workshop_id, []),
            process_hint=process_hint,
        )
        if inferred_machine_id is not None:
            return inferred_machine_id, 'route_inferred'
        return None, 'unresolved'

    requested_tracking_cards = {
        card_key
        for item in (tracking_card_nos or set())
        for card_key in _tracking_card_keys(item)
    }
    def resolve_snapshot_date(item: MesCoilSnapshot) -> date | None:
        if item.business_date is not None:
            return item.business_date
        if item.event_time is not None:
            return resolve_production_business_date(item.event_time)
        return None

    query = db.query(MesCoilSnapshot)
    snapshots = []
    for item in query.all():
        snapshot_date = resolve_snapshot_date(item)
        snapshot_tracking_keys = _mes_snapshot_tracking_keys(item)
        if snapshot_date != business_date and not (snapshot_tracking_keys & requested_tracking_cards):
            continue
        snapshot_workshop_id = resolve_snapshot_workshop_id(item)
        if workshop_id is not None and snapshot_workshop_id != workshop_id:
            continue
        snapshots.append(item)

    payload: list[dict] = []
    for item in snapshots:
        source_business_date = resolve_snapshot_date(item)
        source_payload = dict(item.source_payload or {})
        metadata = dict(source_payload.get('metadata') or {})
        tracking_card_no = str(item.tracking_card_no or '').strip().upper()
        snapshot_tracking_keys = _mes_snapshot_tracking_keys(item)
        work_order = next((work_order_by_card.get(card_key) for card_key in snapshot_tracking_keys if work_order_by_card.get(card_key)), None)
        resolved_workshop_id = resolve_snapshot_workshop_id(item)
        resolved_machine_id, machine_binding_source = resolve_snapshot_machine_binding(item, resolved_workshop_id)
        resolved_shift_id = shift_id_by_code.get(str(item.shift_code or '').strip().upper())
        payload.append(
            {
                'id': item.id,
                'tracking_card_no': tracking_card_no,
                'work_order_id': work_order.id if work_order else None,
                'workshop_id': resolved_workshop_id,
                'machine_id': resolved_machine_id,
                'shift_id': resolved_shift_id,
                'business_date': business_date.isoformat(),
                'source_business_date': source_business_date.isoformat() if source_business_date else None,
                'input_weight': _to_float(source_payload.get('input_weight') or metadata.get('input_weight')),
                'output_weight': _to_float(source_payload.get('output_weight') or metadata.get('output_weight')),
                'scrap_weight': _to_float(source_payload.get('scrap_weight') or metadata.get('scrap_weight')),
                'yield_rate': None,
                'yield_rate_source': 'mes_projection',
                'entry_status': item.status or 'synced',
                'entry_type': 'mes_projection',
                'tracking_card_status': item.status or 'synced',
                'material_code': item.material_code,
                'machine_code': item.machine_code,
                'machine_binding_source': machine_binding_source,
                'upstream_machine_code_missing': not bool(str(item.machine_code or '').strip()),
                'coil_id': item.coil_id,
                'batch_no': item.batch_no,
                'tracking_card_keys': sorted(snapshot_tracking_keys),
            }
        )
    return payload


def _build_attendance_summary(db: Session, *, business_date: date, workshop_id: int | None) -> dict[tuple[int, int], dict]:
    summary: dict[tuple[int, int], dict] = {}

    confirmation_query = (
        db.query(ShiftAttendanceConfirmation.workshop_id, ShiftAttendanceConfirmation.shift_id, ShiftAttendanceConfirmation.status)
        .filter(ShiftAttendanceConfirmation.business_date == business_date)
    )
    if workshop_id is not None:
        confirmation_query = confirmation_query.filter(ShiftAttendanceConfirmation.workshop_id == workshop_id)
    confirmation_rows = confirmation_query.all()

    detail_query = (
        db.query(EmployeeAttendanceDetail, ShiftAttendanceConfirmation, ShiftConfig)
        .join(ShiftAttendanceConfirmation, ShiftAttendanceConfirmation.id == EmployeeAttendanceDetail.confirmation_id)
        .join(ShiftConfig, ShiftConfig.id == ShiftAttendanceConfirmation.shift_id)
        .filter(ShiftAttendanceConfirmation.business_date == business_date)
    )
    if workshop_id is not None:
        detail_query = detail_query.filter(ShiftAttendanceConfirmation.workshop_id == workshop_id)

    anomaly_map: dict[tuple[int, int], int] = {}
    for detail, confirmation, shift in detail_query.all():
        auto = attendance_confirm_service.calculate_auto_status(
            shift=shift,
            business_date=confirmation.business_date,
            clock_in=detail.dingtalk_clock_in,
            clock_out=detail.dingtalk_clock_out,
        )
        if detail.leader_status == auto['status']:
            continue
        key = (confirmation.workshop_id, confirmation.shift_id)
        anomaly_map[key] = int(anomaly_map.get(key, 0)) + 1

    for row in confirmation_rows:
        key = (row.workshop_id, row.shift_id)
        exception_count = int(anomaly_map.get(key, 0))
        summary[key] = {
            'status': 'confirmed' if row.status in {'confirmed', 'hr_reviewed'} and exception_count == 0 else 'pending',
            'exception_count': exception_count,
        }

    schedule_query = (
        db.query(AttendanceSchedule.workshop_id, AttendanceSchedule.shift_config_id)
        .filter(AttendanceSchedule.business_date == business_date)
    )
    if workshop_id is not None:
        schedule_query = schedule_query.filter(AttendanceSchedule.workshop_id == workshop_id)
    for row in schedule_query.group_by(AttendanceSchedule.workshop_id, AttendanceSchedule.shift_config_id).all():
        summary.setdefault((row.workshop_id, row.shift_config_id), {'status': 'not_started', 'exception_count': 0})
    return summary


def _build_expected_count_map(db: Session, *, business_date: date, workshop_id: int | None) -> dict[tuple[int, int, int], int]:
    planned_counts = _build_planned_count_map(db, business_date=business_date, workshop_id=workshop_id)
    query = (
        db.query(
            WorkOrderEntry.workshop_id,
            WorkOrderEntry.machine_id,
            WorkOrderEntry.shift_id,
            func.count(WorkOrderEntry.id).label('entry_count'),
            func.count(func.distinct(WorkOrderEntry.business_date)).label('day_count'),
        )
        .filter(
            WorkOrderEntry.business_date >= business_date - timedelta(days=14),
            WorkOrderEntry.business_date < business_date,
            WorkOrderEntry.machine_id.is_not(None),
            WorkOrderEntry.shift_id.is_not(None),
        )
        .group_by(WorkOrderEntry.workshop_id, WorkOrderEntry.machine_id, WorkOrderEntry.shift_id)
    )
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)

    payload: dict[tuple[int, int, int], int] = {}
    for row in query.all():
        day_count = max(int(row.day_count or 0), 1)
        average_count = round(int(row.entry_count or 0) / day_count)
        payload[(row.workshop_id, row.machine_id, row.shift_id)] = max(average_count, 1)
    planned_counts.update({key: value for key, value in payload.items() if key not in planned_counts})
    return planned_counts


def _build_planned_count_map(db: Session, *, business_date: date, workshop_id: int | None) -> dict[tuple[int, int, int], int]:
    # The current schema does not yet include machine+shift production targets.
    # This hook preserves the plan-first contract so a dedicated plan source can be
    # dropped in without changing the aggregation API or frontend behavior.
    del db, business_date, workshop_id
    return {}


def build_live_aggregation(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
    current_user: User,
) -> dict:
    scoped_workshop_id = _resolve_workshop_filter(current_user=current_user, workshop_id=workshop_id)
    workshops_query = db.query(Workshop).filter(Workshop.is_active.is_(True))
    if _has_reporting_workshop_rows(db):
        workshops_query = workshops_query.filter(Workshop.code.in_(tuple(REPORTING_MACHINE_WORKSHOP_CODES)))
    if scoped_workshop_id is not None:
        workshops_query = workshops_query.filter(Workshop.id == scoped_workshop_id)
    workshops = workshops_query.order_by(Workshop.sort_order.asc(), Workshop.id.asc()).all()
    workshop_ids = [item.id for item in workshops]

    machines_query = db.query(Equipment).filter(Equipment.is_active.is_(True))
    if _has_reporting_machine_rows(db):
        machines_query = machines_query.filter(Equipment.code.in_(tuple(REPORTING_MACHINE_CODE_SET)))
    if workshop_ids:
        machines_query = machines_query.filter(Equipment.workshop_id.in_(workshop_ids))
    else:
        machines_query = machines_query.filter(Equipment.id == -1)

    machines = machines_query.order_by(Equipment.id.asc()).all()
    shifts = db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).order_by(ShiftConfig.sort_order.asc(), ShiftConfig.id.asc()).all()
    entry_rows = _load_entry_rows(db, business_date=business_date, workshop_id=scoped_workshop_id)
    local_machines, local_entries = _build_local_shift_runtime_inputs(
        machines=machines,
        shifts=shifts,
        rows=_load_local_shift_rows(db, business_date=business_date, workshop_id=scoped_workshop_id),
    )
    local_entries = _drop_local_entries_for_existing_cells(entry_rows, local_entries)
    fill_tracking_cards = {
        _tracking_card_key(item.get('tracking_card_no'))
        for item in [*entry_rows, *local_entries]
        if _tracking_card_key(item.get('tracking_card_no'))
    }
    mes_rows = _load_mes_snapshot_rows(
        db,
        business_date=business_date,
        workshop_id=scoped_workshop_id,
        tracking_card_nos=fill_tracking_cards,
    )
    machines = local_machines
    entries, data_source = _merge_runtime_entries(
        entry_rows=entry_rows,
        local_entries=local_entries,
        mes_rows=mes_rows,
    )
    payload = aggregate_live_payload(
        workshops=workshops,
        machines=machines,
        shifts=shifts,
        entries=entries,
        attendance=_build_attendance_summary(db, business_date=business_date, workshop_id=scoped_workshop_id),
        expected_counts=_build_expected_count_map(db, business_date=business_date, workshop_id=scoped_workshop_id),
    )
    mes_machine_output, authoritative_workshop_ids = _load_mes_machine_output_scope(
        db,
        business_date=business_date,
        workshops=workshops,
        machines=machines,
    )
    payload = _apply_mes_machine_output_authority(
        payload,
        mes_machine_output=mes_machine_output,
        authoritative_workshop_ids=authoritative_workshop_ids,
    )
    payload = _apply_yield_matrix_authority(
        payload,
        workshops=workshops,
        yield_matrix_lane=build_yield_matrix_projection(db, target_date=business_date),
    )
    payload['business_date'] = business_date.isoformat()
    mtd_totals = _build_mtd_totals(
        db,
        business_date=business_date,
        workshop_ids=workshop_ids,
        workshop_id=scoped_workshop_id,
    )
    payload = _inject_mtd_into_payload(payload, mtd_totals)
    payload = _inject_factory_packaging_output(
        payload,
        db,
        business_date=business_date,
        scoped_workshop_id=scoped_workshop_id,
    )
    payload['business_date_context'] = _build_live_business_date_context(
        db,
        requested_date=business_date,
        workshop_id=scoped_workshop_id,
    )
    payload['mes_machine_binding'] = _build_mes_machine_binding_summary(
        mes_rows=mes_rows,
        entries=entries,
        pending_assignment=(payload.get('overall_progress') or {}).get('pending_assignment') or {},
        business_date=business_date,
    )
    payload['mes_sync_status'] = mes_sync_service.latest_sync_status(db)
    payload['owner_daily_status'] = _build_owner_daily_status(
        db,
        business_date=business_date,
        workshop_id=scoped_workshop_id,
    )
    payload['data_source'] = data_source
    return payload


def build_live_cell_detail(
    db: Session,
    *,
    business_date: date,
    workshop_id: int,
    machine_id: int,
    shift_id: int,
    current_user: User,
) -> dict:
    scoped_workshop_id = _resolve_workshop_filter(current_user=current_user, workshop_id=workshop_id)
    machines = (
        db.query(Equipment)
        .filter(
            Equipment.is_active.is_(True),
            Equipment.workshop_id == scoped_workshop_id,
        )
        .order_by(Equipment.id.asc())
        .all()
    )
    shifts = db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).order_by(ShiftConfig.sort_order.asc(), ShiftConfig.id.asc()).all()
    entry_rows = _load_entry_rows(db, business_date=business_date, workshop_id=scoped_workshop_id)
    _local_machines, local_entries = _build_local_shift_runtime_inputs(
        machines=machines,
        shifts=shifts,
        rows=_load_local_shift_rows(db, business_date=business_date, workshop_id=scoped_workshop_id),
    )
    local_entries = _drop_local_entries_for_existing_cells(entry_rows, local_entries)
    fill_tracking_cards = {
        _tracking_card_key(item.get('tracking_card_no'))
        for item in [*entry_rows, *local_entries]
        if _tracking_card_key(item.get('tracking_card_no'))
    }
    mes_rows = _load_mes_snapshot_rows(
        db,
        business_date=business_date,
        workshop_id=scoped_workshop_id,
        tracking_card_nos=fill_tracking_cards,
    )
    entries, _data_source = _merge_runtime_entries(
        entry_rows=entry_rows,
        local_entries=local_entries,
        mes_rows=mes_rows,
    )
    cell_items = [
        item
        for item in entries
        if _optional_int(item.get('workshop_id')) == scoped_workshop_id
        and _optional_int(item.get('machine_id')) == machine_id
        and _optional_int(item.get('shift_id')) == shift_id
    ]
    cell_items.sort(key=lambda item: _optional_int(item.get('id')) or 0, reverse=True)
    return {
        'business_date': business_date.isoformat(),
        'workshop_id': scoped_workshop_id,
        'machine_id': machine_id,
        'shift_id': shift_id,
        'items': [_serialize_live_cell_item(item) for item in cell_items],
    }


def _serialize_live_cell_item(item: dict) -> dict:
    input_weight = round(_entry_weight_tons(item, 'input_weight'), 2)
    output_weight = round(_entry_weight_tons(item, 'output_weight'), 2)
    scrap_weight = round(_entry_weight_tons(item, 'scrap_weight'), 2)
    return {
        'tracking_card_no': item.get('tracking_card_no') or '',
        'entry_id': item.get('id'),
        'work_order_id': item.get('work_order_id'),
        'entry_status': item.get('entry_status') or 'draft',
        'entry_type': item.get('entry_type') or 'mobile_coil',
        'input_weight': input_weight,
        'output_weight': output_weight,
        'scrap_weight': scrap_weight,
        'yield_rate': _round_rate(input_weight, output_weight),
        'yield_rate_source': item.get('yield_rate_source') or 'runtime_compat',
        'machine_id': item.get('machine_id'),
        'shift_id': item.get('shift_id'),
    }
