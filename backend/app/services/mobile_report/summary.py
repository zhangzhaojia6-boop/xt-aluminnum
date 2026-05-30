from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.agents.validator import validator_agent
from app.agents.base import AgentAction, AgentDecision
from app.config import settings
from app.core.business_time import OWNER_DAILY_CUTOFF, PRODUCTION_BUSINESS_DAY_START
from app.core.permissions import assert_mobile_report_access, assert_mobile_user_access, assert_scope_access
from app.core.scope import build_scope_summary, scope_to_dict
from app.core.workshop_templates import resolve_workshop_type
from app.models.attendance import AttendanceSchedule
from app.models.energy import MachineEnergyRecord
from app.models.master import Equipment, Team, Workshop
from app.models.production import (
    MobileReminderRecord,
    MobileShiftReport,
    ProductionException,
    ShiftProductionData,
    WorkOrderEntry,
)
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import dingtalk_service
from app.services.audit_service import record_entity_change
from app.services.equipment_service import get_bound_machine_for_user, resolve_reporting_machine_for_equipment
from app.services.locked_fields_service import LockedFieldsTokenInvalid, verify_locked_fields_token
from app.services.pilot_observability_service import log_pilot_event
from app.services.real_master_data import OWNER_DAILY_ROLES
from app.services.work_order._utils import _normalize_flow_payload


def _report_key(row) -> tuple[date, int, int, int | None]:
    return (row.business_date, row.shift_config_id, row.workshop_id, row.team_id)

def _build_inventory_summary_bucket(
    *,
    workshop_id: int,
    workshop_name: str | None,
    team_id: int | None,
    team_name: str | None,
) -> dict:
    return {
        'workshop_id': workshop_id,
        'workshop_name': workshop_name,
        'team_id': team_id,
        'team_name': team_name,
        'source': 'mobile',
        'source_label': '主操直录',
        'source_variant': 'mobile',
        'storage_prepared': 0.0,
        'storage_finished': 0.0,
        'shipment_weight': 0.0,
        'contract_received': 0.0,
        'storage_inbound_area': 0.0,
        'shipment_area': 0.0,
        'consignment_weight': 0.0,
        'finished_inventory_weight': 0.0,
        'actual_inventory_weight': 0.0,
    }

def summarize_mobile_reporting(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None = None,
) -> dict:
    schedule_query = (
        db.query(
            AttendanceSchedule.business_date,
            AttendanceSchedule.shift_config_id,
            AttendanceSchedule.workshop_id,
            AttendanceSchedule.team_id,
        )
        .filter(
            AttendanceSchedule.business_date == target_date,
            AttendanceSchedule.shift_config_id.is_not(None),
            AttendanceSchedule.workshop_id.is_not(None),
        )
        .distinct()
    )
    if workshop_id:
        schedule_query = schedule_query.filter(AttendanceSchedule.workshop_id == workshop_id)
    expected_rows = schedule_query.all()
    expected_keys = {_report_key(row) for row in expected_rows}

    report_query = db.query(MobileShiftReport).filter(MobileShiftReport.business_date == target_date)
    if workshop_id:
        report_query = report_query.filter(MobileShiftReport.workshop_id == workshop_id)
    reports = report_query.all()
    report_map = {_report_key(row): row for row in reports}
    config_warnings: list[str] = []
    if not expected_keys:
        config_warnings.append('当日班次应报清单为空，仅检查每日一填岗位。')

    submitted_count = len([row for row in reports if row.report_status == 'submitted'])
    approved_count = len([row for row in reports if row.report_status in APPROVED_REPORT_STATUSES])
    auto_confirmed_count = len([row for row in reports if _is_mobile_report_auto_confirmed(row)])
    reported_count = submitted_count + auto_confirmed_count
    draft_count = len([row for row in reports if row.report_status == 'draft'])
    returned_count = len([row for row in reports if _mobile_report_decision_status(row) == 'returned'])
    exception_count = len([row for row in reports if row.has_exception])
    late_count = len([row for row in reports if row.submitted_at is not None and row.submitted_at.date() > row.business_date])
    unreported_count = len([key for key in expected_keys if key not in report_map])
    expected_count = len(expected_keys)
    reporting_rate = round(min((reported_count / expected_count) * 100, 100), 2) if expected_count else 0.0

    returned_items = sorted(
        [
            {
                'report_id': row.id,
                'business_date': row.business_date.isoformat(),
                'shift_id': row.shift_config_id,
                'workshop_id': row.workshop_id,
                'team_id': row.team_id,
                'returned_reason': row.returned_reason,
            }
            for row in reports
            if _mobile_report_decision_status(row) == 'returned'
        ],
        key=lambda item: item['business_date'],
        reverse=True,
    )[:8]

    return {
        'expected_count': expected_count,
        'reported_count': reported_count,
        'submitted_count': submitted_count,
        'approved_count': approved_count,
        'auto_confirmed_count': auto_confirmed_count,
        'draft_count': draft_count,
        'unreported_count': unreported_count,
        'late_count': late_count,
        'returned_count': returned_count,
        'exception_count': exception_count,
        'reporting_rate': reporting_rate,
        'config_warnings': config_warnings,
        'returned_items': returned_items,
    }

def summarize_mobile_inventory(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None = None,
) -> list[dict]:
    inventory_payload_fields = {
        'storage_inbound_weight',
        'storage_inbound_area',
        'park_inbound_daily',
        'park_inbound_monthly',
        'park_outbound_daily',
        'park_outbound_monthly',
        'new_plant_inbound_daily',
        'new_plant_inbound_monthly',
        'new_plant_outbound_daily',
        'new_plant_outbound_monthly',
        'plant_to_park_inbound_weight',
        'park_to_storage_inbound_weight',
        'month_to_date_inbound_weight',
        'month_to_date_inbound_area',
        'shipment_weight',
        'shipment_area',
        'month_to_date_shipment_weight',
        'month_to_date_shipment_area',
        'consignment_weight',
        'finished_inventory_weight',
        'actual_inventory_weight',
        'shearing_prepared_weight',
    }
    inventory_entry_query = (
        db.query(WorkOrderEntry, Workshop)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .filter(
            WorkOrderEntry.business_date == target_date,
            WorkOrderEntry.entry_type == OWNER_DAILY_ENTRY_TYPE,
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
        )
    )
    if workshop_id:
        inventory_entry_query = inventory_entry_query.filter(WorkOrderEntry.workshop_id == workshop_id)
    owner_only_rows = inventory_entry_query.all()
    owner_only_inventory_rows = [
        (entry, workshop)
        for entry, workshop in owner_only_rows
        if any(dict(entry.extra_payload or {}).get(field_name) is not None for field_name in inventory_payload_fields)
    ]
    owner_only_workshop_ids = {entry.workshop_id for entry, _workshop in owner_only_inventory_rows}

    query = db.query(MobileShiftReport).filter(
        MobileShiftReport.business_date == target_date,
        MobileShiftReport.report_status.in_(tuple(SUBMITTED_STATUSES)),
    )
    if workshop_id:
        query = query.filter(MobileShiftReport.workshop_id == workshop_id)
    rows = query.all()

    workshop_ids = {row.workshop_id for row in rows}
    team_ids = {row.team_id for row in rows if row.team_id}
    workshop_map = {item.id: item.name for item in db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all()} if workshop_ids else {}
    team_map = {item.id: item.name for item in db.query(Team).filter(Team.id.in_(team_ids)).all()} if team_ids else {}

    grouped: dict[tuple[int, int | None], dict] = {}
    for row in rows:
        if row.workshop_id in owner_only_workshop_ids:
            continue
        key = (row.workshop_id, row.team_id)
        payload = grouped.setdefault(
            key,
            _build_inventory_summary_bucket(
                workshop_id=row.workshop_id,
                workshop_name=workshop_map.get(row.workshop_id),
                team_id=row.team_id,
                team_name=team_map.get(row.team_id) if row.team_id else None,
            ),
        )
        payload['storage_prepared'] += _to_float(row.storage_prepared) or 0.0
        payload['storage_finished'] += _to_float(row.storage_finished) or 0.0
        payload['shipment_weight'] += _to_float(row.shipment_weight) or 0.0
        payload['contract_received'] += _to_float(row.contract_received) or 0.0

    for entry, workshop in owner_only_inventory_rows:
        extra_payload = dict(entry.extra_payload or {})
        if not extra_payload:
            continue

        key = (entry.workshop_id, None)
        payload = grouped.setdefault(
            key,
            _build_inventory_summary_bucket(
                workshop_id=entry.workshop_id,
                workshop_name=workshop.name if workshop else workshop_map.get(entry.workshop_id),
                team_id=None,
                team_name=None,
            ),
        )
        payload['source'] = 'owner_only'
        payload['source_label'] = '专项补录'
        payload['source_variant'] = 'owner'
        inbound_weight = _to_float(extra_payload.get('storage_inbound_weight'))
        if inbound_weight is None:
            inbound_weight = (
                (_to_float(extra_payload.get('park_inbound_daily')) or 0.0)
                + (_to_float(extra_payload.get('new_plant_inbound_daily')) or 0.0)
            )
        shipment_weight = _to_float(extra_payload.get('shipment_weight'))
        if shipment_weight is None:
            shipment_weight = (
                (_to_float(extra_payload.get('park_outbound_daily')) or 0.0)
                + (_to_float(extra_payload.get('new_plant_outbound_daily')) or 0.0)
            )
        payload['storage_finished'] += inbound_weight or 0.0
        payload['shipment_weight'] += shipment_weight or 0.0
        payload['storage_inbound_area'] += _to_float(extra_payload.get('storage_inbound_area')) or 0.0
        payload['shipment_area'] += _to_float(extra_payload.get('shipment_area')) or 0.0
        payload['consignment_weight'] += _to_float(extra_payload.get('consignment_weight')) or 0.0
        payload['finished_inventory_weight'] += _to_float(extra_payload.get('finished_inventory_weight')) or 0.0
        payload['actual_inventory_weight'] += _to_float(extra_payload.get('actual_inventory_weight')) or 0.0

    items = list(grouped.values())
    items.sort(key=lambda item: (item['workshop_name'] or '', item['team_name'] or ''))
    return items

def recent_mobile_exceptions(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None = None,
) -> list[dict]:
    query = db.query(MobileShiftReport).filter(
        MobileShiftReport.business_date == target_date,
        or_(
            MobileShiftReport.has_exception.is_(True),
            MobileShiftReport.report_status == 'returned',
            MobileShiftReport.returned_reason.is_not(None),
        ),
    )
    if workshop_id:
        query = query.filter(MobileShiftReport.workshop_id == workshop_id)
    rows = query.order_by(MobileShiftReport.updated_at.desc().nullslast(), MobileShiftReport.id.desc()).limit(12).all()
    workshop_ids = {row.workshop_id for row in rows}
    team_ids = {row.team_id for row in rows if row.team_id}
    shift_ids = {row.shift_config_id for row in rows}
    workshop_map = {item.id: item.name for item in db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all()} if workshop_ids else {}
    team_map = {item.id: item.name for item in db.query(Team).filter(Team.id.in_(team_ids)).all()} if team_ids else {}
    shift_map = {item.id: item.name for item in db.query(ShiftConfig).filter(ShiftConfig.id.in_(shift_ids)).all()} if shift_ids else {}

    return [
        {
            'report_id': row.id,
            'workshop_name': workshop_map.get(row.workshop_id),
            'team_name': team_map.get(row.team_id) if row.team_id else None,
            'shift_name': shift_map.get(row.shift_config_id),
            'report_status': row.report_status,
            'has_exception': row.has_exception,
            'exception_type': row.exception_type,
            'note': row.note,
            'returned_reason': row.returned_reason,
        }
        for row in rows
    ]

def count_linked_open_production_exceptions(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None = None,
) -> int:
    query = (
        db.query(func.count(ProductionException.id))
        .join(MobileShiftReport, MobileShiftReport.linked_production_data_id == ProductionException.production_data_id)
        .filter(
            MobileShiftReport.business_date == target_date,
            ProductionException.status == 'open',
        )
    )
    if workshop_id:
        query = query.filter(MobileShiftReport.workshop_id == workshop_id)
    return int(query.scalar() or 0)

def list_coil_entries(
    db: Session,
    *,
    business_date: date,
    shift_id: int,
    current_user: User,
) -> list[dict]:
    assert_mobile_user_access(current_user)
    workshop_id = current_user.workshop_id
    if not workshop_id:
        scope = build_scope_summary(current_user)
        workshop_id = scope.workshop_id
    query = (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.shift_id == shift_id,
        )
    )
    if workshop_id:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)
    rows = query.order_by(WorkOrderEntry.id.desc()).all()
    from app.models.production import WorkOrder
    wo_ids = {r.work_order_id for r in rows}
    wo_map = {}
    if wo_ids:
        wos = db.query(WorkOrder).filter(WorkOrder.id.in_(wo_ids)).all()
        wo_map = {wo.id: wo for wo in wos}
    result = []
    for r in rows:
        wo = wo_map.get(r.work_order_id)
        extra_payload = dict(r.extra_payload or {})
        result.append({
            'id': r.id,
            'tracking_card_no': wo.tracking_card_no if wo else '',
            'alloy_grade': wo.alloy_grade if wo else None,
            'input_spec': r.input_spec,
            'output_spec': r.output_spec,
            'input_weight': float(r.input_weight) if r.input_weight is not None else None,
            'output_weight': float(r.output_weight) if r.output_weight is not None else None,
            'scrap_weight': float(r.scrap_weight) if r.scrap_weight is not None else None,
            'operator_notes': r.operator_notes,
            'extra_payload': extra_payload,
            'previous_process': extra_payload.get('previous_process') or extra_payload.get('flow', {}).get('previous_process'),
            'next_process': extra_payload.get('next_process') or extra_payload.get('flow', {}).get('next_process'),
            'business_date': r.business_date,
            'created_at': r.created_at if hasattr(r, 'created_at') else None,
        })
    return result

def _aggregate_coil_to_shift(
    db: Session,
    *,
    business_date: date,
    shift_id: int,
    workshop_id: int,
    machine_id: int | None = None,
):
    # Disabled 2026-05-27: mobile_coil_agg duplicate filing path retired.
    # Mobile filing now flows only through data_source='mobile' via lifecycle.py.
    return
    entry_query = db.query(
        func.sum(WorkOrderEntry.input_weight).label('total_input'),
        func.sum(WorkOrderEntry.output_weight).label('total_output'),
        func.sum(WorkOrderEntry.scrap_weight).label('total_scrap'),
        func.count(WorkOrderEntry.id).label('coil_count'),
    ).filter(
        WorkOrderEntry.business_date == business_date,
        WorkOrderEntry.shift_id == shift_id,
        WorkOrderEntry.workshop_id == workshop_id,
        WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
    )
    if machine_id is None:
        entry_query = entry_query.filter(WorkOrderEntry.machine_id.is_(None))
    else:
        entry_query = entry_query.filter(WorkOrderEntry.machine_id == machine_id)
    agg = entry_query.first()
    spd_query = (
        db.query(ShiftProductionData)
        .filter(
            ShiftProductionData.business_date == business_date,
            ShiftProductionData.shift_config_id == shift_id,
            ShiftProductionData.workshop_id == workshop_id,
            ShiftProductionData.data_source == 'mobile_coil_agg',
            ShiftProductionData.data_status != 'voided',
        )
    )
    if machine_id is None:
        spd_query = spd_query.filter(ShiftProductionData.equipment_id.is_(None))
    else:
        spd_query = spd_query.filter(ShiftProductionData.equipment_id == machine_id)
    spd = spd_query.first()
    if not agg or not agg.coil_count:
        if spd:
            spd.data_status = 'voided'
            spd.voided_at = datetime.now(ZoneInfo(settings.DEFAULT_TIMEZONE))
            spd.voided_reason = 'no submitted mobile coil entries'
            db.commit()
        return
    if spd:
        spd.input_weight = float(agg.total_input or 0)
        spd.output_weight = float(agg.total_output or 0)
        spd.scrap_weight = float(agg.total_scrap or 0)
        spd.data_source = 'mobile_coil_agg'
        spd.equipment_id = machine_id
    else:
        spd = ShiftProductionData(
            business_date=business_date,
            shift_config_id=shift_id,
            workshop_id=workshop_id,
            equipment_id=machine_id,
            input_weight=float(agg.total_input or 0),
            output_weight=float(agg.total_output or 0),
            scrap_weight=float(agg.total_scrap or 0),
            data_source='mobile_coil_agg',
            data_status='pending',
        )
        db.add(spd)
    db.commit()


def _normalized_locked_value(value) -> str:
    if value is None:
        return ''
    if isinstance(value, Decimal):
        value = _normalized_numeric_text(str(value))
    return str(value).strip()


def _normalized_numeric_text(value: str) -> str:
    text = str(value).strip()
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text
    normalized = format(number.normalize(), 'f')
    if '.' in normalized:
        normalized = normalized.rstrip('0').rstrip('.')
    return '0' if normalized in {'', '-0'} else normalized


def _normalized_alloy_grade(value) -> str:
    return _normalized_numeric_text(_normalized_locked_value(value)).upper()


def _normalized_spec_parts(value) -> tuple[str, ...]:
    text = _normalized_locked_value(value).upper()
    text = re.sub(r'\s+', '', text)
    text = text.replace('×', 'X').replace('＊', '*').replace('Ｘ', 'X').replace('ｘ', 'X')
    return tuple(_normalized_numeric_text(part) for part in re.split(r'[X*]', text) if part)


def _without_fixed_c_suffix(parts: tuple[str, ...]) -> tuple[str, ...]:
    if parts and parts[-1] == 'C':
        return parts[:-1]
    return parts


def _locked_values_match(key: str, current, expected) -> bool:
    if key == 'alloy_grade':
        return _normalized_alloy_grade(current) == _normalized_alloy_grade(expected)
    if key.endswith('_spec'):
        current_parts = _normalized_spec_parts(current)
        expected_parts = _normalized_spec_parts(expected)
        return current_parts == expected_parts or _without_fixed_c_suffix(current_parts) == _without_fixed_c_suffix(expected_parts)
    return _normalized_locked_value(current) == _normalized_locked_value(expected)


def _locked_payload_value(payload: dict, key: str):
    if key in payload:
        return payload.get(key), True
    extra_payload = dict(payload.get('extra_payload') or {})
    if key in extra_payload:
        return extra_payload.get(key), True
    flow = extra_payload.get('flow')
    if isinstance(flow, dict) and key in flow:
        return flow.get(key), True
    return None, False


def _trusted_locked_snapshot(db: Session, payload: dict) -> tuple[dict, bool]:
    """Return (snapshot, has_token). Only enforce strict validation when has_token=True."""
    token = payload.get('locked_fields_token')
    if token:
        try:
            return verify_locked_fields_token(str(token)), True
        except LockedFieldsTokenInvalid as exc:
            raise HTTPException(status_code=409, detail='locked_field_tampered') from exc
    from app.services import scan_lookup_service

    try:
        snapshot = scan_lookup_service.submission_locked_snapshot_for_tracking_card(
            db,
            tracking_card_no=str(payload.get('tracking_card_no') or ''),
        )
    except scan_lookup_service.ScanLookupUnavailable:
        snapshot = {}
    return snapshot, False


def _validate_locked_fields(db: Session, payload: dict) -> tuple[list[str], dict]:
    snapshot, has_token = _trusted_locked_snapshot(db, payload)
    if not snapshot:
        return [], {}

    if not has_token:
        return [str(key) for key in snapshot.keys()], dict(snapshot)

    tampered: list[str] = []
    for key, expected in snapshot.items():
        current, found = _locked_payload_value(payload, str(key))
        if not found and _normalized_locked_value(expected):
            tampered.append(str(key))
            continue
        if not _locked_values_match(str(key), current, expected):
            tampered.append(str(key))
    if tampered:
        raise HTTPException(status_code=409, detail='locked_field_tampered')
    return [str(key) for key in snapshot.keys()], dict(snapshot)


def _required_positive_weight(payload: dict, key: str, detail: str) -> Decimal:
    value = payload.get(key)
    if value in (None, ''):
        raise HTTPException(status_code=422, detail=detail)
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise HTTPException(status_code=422, detail=detail) from exc
    if not number.is_finite() or number <= 0:
        raise HTTPException(status_code=422, detail=detail)
    return number


def _validate_coil_entry_weights(payload: dict) -> None:
    input_weight = _required_positive_weight(payload, 'input_weight', 'input_weight_required')
    # output_weight 改为可选
    output_weight_raw = payload.get('output_weight')
    if output_weight_raw is not None:
        try:
            output_weight = Decimal(str(output_weight_raw))
            if not output_weight.is_finite() or output_weight <= 0:
                raise HTTPException(status_code=422, detail='output_weight_invalid')
            # 移除下机重量不能大于上机重量的硬性限制
            # 某些工序（复合、涂层、包装）或计量误差可能导致下机重量大于上机重量
            # if output_weight > input_weight:
            #     raise HTTPException(status_code=422, detail='output_weight_exceeds_input')
        except (InvalidOperation, ValueError) as exc:
            raise HTTPException(status_code=422, detail='output_weight_invalid') from exc


def create_coil_entry(
    db: Session,
    *,
    payload: dict,
    current_user: User,
    ip_address: str | None = None,
) -> dict:
    assert_mobile_user_access(current_user)
    _validate_coil_entry_weights(payload)
    from app.models.production import WorkOrder

    tracking_card_no = payload['tracking_card_no'].strip()
    wo = db.query(WorkOrder).filter(WorkOrder.tracking_card_no == tracking_card_no).first()
    if not wo:
        wo = WorkOrder(
            tracking_card_no=tracking_card_no,
            alloy_grade=payload.get('alloy_grade'),
            process_route_code='mobile',
            overall_status='created',
            created_by=current_user.id,
        )
        db.add(wo)
        db.flush()

    bound_machine = get_bound_machine_for_user(db, user_id=current_user.id)
    reporting_machine = resolve_reporting_machine_for_equipment(db, bound_machine)
    workshop_id = reporting_machine.workshop_id if reporting_machine else current_user.workshop_id
    if not workshop_id:
        scope = build_scope_summary(current_user)
        workshop_id = scope.workshop_id
    locked_fields, locked_snapshot = _validate_locked_fields(db, payload)
    extra_payload = _build_coil_flow_extra_payload(db, payload, locked_fields_snapshot=locked_snapshot)

    entry = WorkOrderEntry(
        work_order_id=wo.id,
        workshop_id=workshop_id or 0,
        machine_id=reporting_machine.id if reporting_machine else None,
        shift_id=payload['shift_id'],
        business_date=payload['business_date'],
        on_machine_time=payload.get('on_machine_time'),
        off_machine_time=payload.get('off_machine_time'),
        input_weight=payload.get('input_weight'),
        output_weight=payload.get('output_weight'),
        input_spec=payload.get('input_spec'),
        output_spec=payload.get('output_spec'),
        scrap_weight=payload.get('scrap_weight'),
        operator_notes=payload.get('operator_notes'),
        extra_payload=extra_payload,
        entry_type='mobile_coil',
        entry_status='submitted',
        locked_fields=locked_fields or None,
        created_by=current_user.id,
        created_by_user_id=current_user.id,
    )
    if entry.scrap_weight is None and entry.input_weight and entry.output_weight:
        inp = float(entry.input_weight)
        out = float(entry.output_weight)
        spool = float(payload.get('spool_weight') or 0)
        trim = float(payload.get('trim_weight') or 0)
        tray = float(payload.get('tray_weight') or 0)
        entry.scrap_weight = round(inp - out - spool - trim - tray, 2)
    if payload.get('input_weight') and payload.get('output_weight'):
        inp = float(payload['input_weight'])
        out = float(payload['output_weight'])
        if inp > 0:
            entry.yield_rate = round(out / inp, 4)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    _aggregate_coil_to_shift(
        db,
        business_date=payload['business_date'],
        shift_id=payload['shift_id'],
        workshop_id=entry.workshop_id,
        machine_id=entry.machine_id,
    )

    return {
        'id': entry.id,
        'tracking_card_no': wo.tracking_card_no,
        'alloy_grade': wo.alloy_grade,
        'input_spec': entry.input_spec,
        'output_spec': entry.output_spec,
        'input_weight': float(entry.input_weight) if entry.input_weight is not None else None,
        'output_weight': float(entry.output_weight) if entry.output_weight is not None else None,
        'scrap_weight': float(entry.scrap_weight) if entry.scrap_weight is not None else None,
        'operator_notes': entry.operator_notes,
        'extra_payload': dict(entry.extra_payload or {}),
        'previous_process': (entry.extra_payload or {}).get('previous_process') or (entry.extra_payload or {}).get('flow', {}).get('previous_process'),
        'next_process': (entry.extra_payload or {}).get('next_process') or (entry.extra_payload or {}).get('flow', {}).get('next_process'),
        'business_date': entry.business_date,
        'created_at': None,
    }


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


def _owner_daily_tracking_card(*, role: str, user_id: int, business_date: date) -> str:
    return f"OWNER-{role}-{user_id}-{business_date.isoformat()}"


def _owner_daily_response(entry: WorkOrderEntry, *, workshop: Workshop | None, current_user: User) -> dict:
    return {
        'id': entry.id,
        'business_date': entry.business_date,
        'workshop_id': entry.workshop_id,
        'workshop_name': workshop.name if workshop else None,
        'role': current_user.role,
        'role_label': OWNER_DAILY_ROLE_LABELS.get(current_user.role, current_user.role),
        'data': dict(entry.extra_payload or {}),
        'entry_status': entry.entry_status,
        'updated_at': entry.updated_at if hasattr(entry, 'updated_at') else None,
    }


def get_owner_daily_entry(
    db: Session,
    *,
    business_date: date,
    current_user: User,
) -> dict | None:
    assert_mobile_user_access(current_user)
    role = current_user.role or ''
    if role not in OWNER_DAILY_ROLES:
        raise HTTPException(status_code=403, detail='owner_daily_role_required')
    workshop_id = current_user.workshop_id or build_scope_summary(current_user).workshop_id
    if not workshop_id:
        raise HTTPException(status_code=400, detail='当前账号未绑定车间，请先在用户管理中设置车间归属。')
    entry = (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.entry_type == OWNER_DAILY_ENTRY_TYPE,
            WorkOrderEntry.created_by_user_id == current_user.id,
        )
        .order_by(WorkOrderEntry.updated_at.desc(), WorkOrderEntry.id.desc())
        .first()
    )
    if entry is None:
        return None
    return _owner_daily_response(entry, workshop=db.get(Workshop, workshop_id), current_user=current_user)


def save_owner_daily_entry(
    db: Session,
    *,
    payload: dict,
    current_user: User,
) -> dict:
    assert_mobile_user_access(current_user)
    role = current_user.role or ''
    if role not in OWNER_DAILY_ROLES:
        raise HTTPException(status_code=403, detail='owner_daily_role_required')
    workshop_id = current_user.workshop_id or build_scope_summary(current_user).workshop_id
    if not workshop_id:
        raise HTTPException(status_code=400, detail='当前账号未绑定车间，请先在用户管理中设置车间归属。')

    resolved_business_date = resolve_owner_daily_business_date()
    raw_business_date = payload.get('business_date')
    business_date = date.fromisoformat(raw_business_date) if isinstance(raw_business_date, str) else (raw_business_date or resolved_business_date)
    current_local = _local_now()
    if current_local.time() < OWNER_DAILY_CUTOFF and business_date >= current_local.date():
        business_date = resolved_business_date
    elif current_local.time() >= PRODUCTION_BUSINESS_DAY_START and business_date <= current_local.date():
        business_date = resolved_business_date
    data = dict(payload.get('data') or {})
    from app.models.production import WorkOrder

    tracking_card_no = _owner_daily_tracking_card(role=role, user_id=current_user.id, business_date=business_date)
    work_order = db.query(WorkOrder).filter(WorkOrder.tracking_card_no == tracking_card_no).first()
    if work_order is None:
        work_order = WorkOrder(
            tracking_card_no=tracking_card_no,
            process_route_code='owner_daily',
            overall_status='created',
            created_by=current_user.id,
        )
        db.add(work_order)
        db.flush()

    entry = (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.work_order_id == work_order.id,
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.entry_type == OWNER_DAILY_ENTRY_TYPE,
            WorkOrderEntry.created_by_user_id == current_user.id,
        )
        .first()
    )
    if entry is None:
        entry = WorkOrderEntry(
            work_order_id=work_order.id,
            workshop_id=workshop_id,
            machine_id=None,
            shift_id=None,
            business_date=business_date,
            entry_type=OWNER_DAILY_ENTRY_TYPE,
            created_by=current_user.id,
            created_by_user_id=current_user.id,
        )
        db.add(entry)

    entry.workshop_id = workshop_id
    entry.extra_payload = data
    entry.entry_status = 'submitted'
    entry.submitted_at = datetime.now(ZoneInfo(settings.DEFAULT_TIMEZONE))
    db.commit()
    db.refresh(entry)
    return _owner_daily_response(entry, workshop=db.get(Workshop, workshop_id), current_user=current_user)


def _flow_context_from_external_snapshot(db: Session, payload: dict) -> dict:
    from app.services import scan_lookup_service

    try:
        return scan_lookup_service.flow_context_for_identifier(
            db,
            identifier=str(payload.get('tracking_card_no') or ''),
        )
    except scan_lookup_service.ScanLookupUnavailable:
        return {}


def _build_coil_flow_extra_payload(db: Session, payload: dict, *, locked_fields_snapshot: dict | None = None) -> dict:
    extra_payload = dict(payload.get('extra_payload') or {})
    if 'flow' in extra_payload:
        extra_payload['flow'] = _normalize_flow_payload(extra_payload.get('flow'))
    if locked_fields_snapshot:
        extra_payload['locked_fields_snapshot'] = dict(locked_fields_snapshot)

    legacy_flow = {
        key: payload.get(key)
        for key in ('previous_process', 'next_process')
        if payload.get(key) not in (None, '')
    }
    if legacy_flow and 'flow' not in extra_payload:
        extra_payload.update(legacy_flow)
    if 'flow' not in extra_payload:
        extra_payload.update(_flow_context_from_external_snapshot(db, payload))
    return extra_payload
