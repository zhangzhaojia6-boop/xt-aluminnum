from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.agents.validator import validator_agent
from app.agents.base import AgentAction, AgentDecision
from app.config import settings
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
from app.services.equipment_service import get_bound_machine_for_user
from app.services.pilot_observability_service import log_pilot_event


def _find_mobile_report(
    db: Session,
    *,
    business_date: date,
    shift_id: int,
    workshop_id: int,
    team_id: int | None,
) -> MobileShiftReport | None:
    query = db.query(MobileShiftReport).filter(
        MobileShiftReport.business_date == business_date,
        MobileShiftReport.shift_config_id == shift_id,
        MobileShiftReport.workshop_id == workshop_id,
    )
    if team_id is None:
        query = query.filter(MobileShiftReport.team_id.is_(None))
    else:
        query = query.filter(MobileShiftReport.team_id == team_id)
    return query.first()

def calculate_mobile_report_metrics(
    payload: dict,
    *,
    monthly_output: float | None,
    monthly_electricity: float | None,
    monthly_gas: float | None,
    target_value: float | None = None,
    compare_value: float | None = None,
) -> dict:
    output_weight = float(payload.get('output_weight') or 0)
    scrap_weight = float(payload.get('scrap_weight') or 0)
    electricity_daily = float(payload.get('electricity_daily') or 0)

    monthly_yield_rate = None
    if output_weight > 0:
        monthly_yield_rate = round(((output_weight - scrap_weight) / output_weight) * 100, 2)

    energy_per_ton = None
    if output_weight > 0:
        energy_per_ton = round(electricity_daily / output_weight, 2)

    return {
        'monthly_output': _round_value(monthly_output),
        'monthly_electricity': _round_value(monthly_electricity),
        'monthly_gas': _round_value(monthly_gas),
        'monthly_yield_rate': monthly_yield_rate,
        'target_value': _round_value(target_value),
        'compare_value': _round_value(compare_value),
        'energy_per_ton': energy_per_ton,
    }

def _aggregate_monthly_totals(
    db: Session,
    *,
    report: MobileShiftReport | None,
    business_date: date,
    workshop_id: int,
    team_id: int | None,
) -> dict:
    month_start, month_end = _month_range(business_date)
    query = db.query(MobileShiftReport).filter(
        MobileShiftReport.business_date >= month_start,
        MobileShiftReport.business_date <= month_end,
        MobileShiftReport.workshop_id == workshop_id,
        MobileShiftReport.report_status.in_(tuple(SUBMITTED_STATUSES)),
    )
    if team_id is None:
        query = query.filter(MobileShiftReport.team_id.is_(None))
    else:
        query = query.filter(MobileShiftReport.team_id == team_id)

    rows = query.all()
    if report and report.id is not None:
        rows = [item for item in rows if item.id != report.id]

    monthly_output = sum(_to_float(item.output_weight) or 0 for item in rows)
    monthly_electricity = sum(_to_float(item.electricity_daily) or 0 for item in rows)
    monthly_gas = sum(_to_float(item.gas_daily) or 0 for item in rows)
    if report is not None and _same_month(business_date, report.business_date):
        monthly_output += _to_float(report.output_weight) or 0
        monthly_electricity += _to_float(report.electricity_daily) or 0
        monthly_gas += _to_float(report.gas_daily) or 0

    return {
        'monthly_output': monthly_output,
        'monthly_electricity': monthly_electricity,
        'monthly_gas': monthly_gas,
    }

def _target_and_compare_values(
    db: Session,
    *,
    business_date: date,
    shift_id: int,
    workshop_id: int,
    team_id: int | None,
) -> tuple[float | None, float | None]:
    base_query = db.query(MobileShiftReport).filter(
        MobileShiftReport.shift_config_id == shift_id,
        MobileShiftReport.workshop_id == workshop_id,
        MobileShiftReport.report_status.in_(tuple(SUBMITTED_STATUSES)),
    )
    if team_id is None:
        base_query = base_query.filter(MobileShiftReport.team_id.is_(None))
    else:
        base_query = base_query.filter(MobileShiftReport.team_id == team_id)

    month_start, _ = _month_range(business_date)
    month_rows = (
        base_query.filter(
            MobileShiftReport.business_date >= month_start,
            MobileShiftReport.business_date < business_date,
        )
        .order_by(MobileShiftReport.business_date.desc())
        .all()
    )
    compare_row = (
        base_query.filter(MobileShiftReport.business_date < business_date)
        .order_by(MobileShiftReport.business_date.desc())
        .first()
    )

    target_value = None
    if month_rows:
        total_output = sum(_to_float(item.output_weight) or 0 for item in month_rows)
        target_value = total_output / len(month_rows)

    compare_value = _to_float(compare_row.output_weight) if compare_row else None
    return target_value, compare_value

def _serialize_mobile_report(
    db: Session,
    report: MobileShiftReport | None,
    *,
    business_date: date,
    shift: ShiftConfig,
    workshop: Workshop,
    team: Team | None,
    leader_name: str,
    agent_decision_snapshot: dict | None = None,
) -> dict:
    monthly_totals = _aggregate_monthly_totals(
        db,
        report=report,
        business_date=business_date,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
    )
    target_value, compare_value = _target_and_compare_values(
        db,
        business_date=business_date,
        shift_id=shift.id,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
    )
    payload = {
        'output_weight': _to_float(report.output_weight) if report else None,
        'scrap_weight': _to_float(report.scrap_weight) if report else None,
        'electricity_daily': _to_float(report.electricity_daily) if report else None,
        'gas_daily': _to_float(report.gas_daily) if report else None,
    }
    metrics = calculate_mobile_report_metrics(
        payload,
        monthly_output=monthly_totals['monthly_output'],
        monthly_electricity=monthly_totals['monthly_electricity'],
        monthly_gas=monthly_totals['monthly_gas'],
        target_value=target_value,
        compare_value=compare_value,
    )
    active_reminders = _active_reminders_for_context(
        db,
        business_date=business_date,
        shift_id=shift.id,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
        leader_user_id=report.owner_user_id if report else None,
    )
    decision_snapshot = agent_decision_snapshot or _build_agent_decision_snapshot(report=report)

    return {
        'id': report.id if report else None,
        'business_date': business_date,
        'shift_id': shift.id,
        'shift_code': shift.code,
        'shift_name': shift.name,
        'workshop_id': workshop.id,
        'workshop_name': workshop.name,
        'team_id': team.id if team else None,
        'team_name': team.name if team else None,
        'leader_name': report.leader_name if report and report.leader_name else leader_name,
        'owner_user_id': report.owner_user_id if report else None,
        'submitted_by_user_id': report.submitted_by_user_id if report else None,
        'last_action_by_user_id': report.last_action_by_user_id if report else None,
        'report_status': report.report_status if report else 'unreported',
        'attendance_count': report.attendance_count if report else None,
        'input_weight': _to_float(report.input_weight) if report else None,
        'output_weight': _to_float(report.output_weight) if report else None,
        'scrap_weight': _to_float(report.scrap_weight) if report else None,
        'storage_prepared': _to_float(report.storage_prepared) if report else None,
        'storage_finished': _to_float(report.storage_finished) if report else None,
        'shipment_weight': _to_float(report.shipment_weight) if report else None,
        'contract_received': _to_float(report.contract_received) if report else None,
        'electricity_daily': _to_float(report.electricity_daily) if report else None,
        'gas_daily': _to_float(report.gas_daily) if report else None,
        'has_exception': report.has_exception if report else False,
        'exception_type': report.exception_type if report else None,
        'note': report.note if report else None,
        'optional_photo_url': report.optional_photo_url if report else None,
        'photo_file_path': report.photo_file_path if report else None,
        'photo_file_name': report.photo_file_name if report else None,
        'photo_file_url': _public_upload_url(report.photo_file_path) if report and report.photo_file_path else None,
        'photo_uploaded_at': report.photo_uploaded_at if report else None,
        'linked_production_data_id': report.linked_production_data_id if report else None,
        'returned_reason': report.returned_reason if report else None,
        'agent_decision_status': decision_snapshot.get('agent_decision_status'),
        'agent_decision_action': decision_snapshot.get('agent_decision_action'),
        'agent_decision_agent': decision_snapshot.get('agent_decision_agent'),
        'agent_decision_reason': decision_snapshot.get('agent_decision_reason'),
        'agent_decision_warnings': decision_snapshot.get('agent_decision_warnings', []),
        'agent_decision_errors': decision_snapshot.get('agent_decision_errors', []),
        'agent_decision_at': decision_snapshot.get('agent_decision_at'),
        'active_reminders': active_reminders,
        'machine_energy_records': _load_machine_energy_records(db, report_id=report.id) if report else [],
        'workshop_machines': _get_workshop_machines(db, workshop_id=workshop.id),
        'submitted_at': report.submitted_at if report else None,
        'last_saved_at': report.last_saved_at if report else None,
        'updated_at': report.updated_at if report else None,
        **metrics,
    }

def _sync_to_shift_production(
    db: Session,
    *,
    report: MobileShiftReport,
    shift: ShiftConfig,
    workshop: Workshop,
    team: Team | None,
) -> ShiftProductionData:
    output_weight = _to_float(report.output_weight)
    scrap_weight = _to_float(report.scrap_weight) or 0.0
    qualified_weight = None if output_weight is None else max(output_weight - scrap_weight, 0.0)

    entity = db.get(ShiftProductionData, report.linked_production_data_id) if report.linked_production_data_id else None
    if entity is None:
        entity = ShiftProductionData(
            business_date=report.business_date,
            shift_config_id=shift.id,
            workshop_id=workshop.id,
            team_id=team.id if team else None,
            equipment_id=None,
            data_source='mobile',
            version_no=1,
        )
        db.add(entity)

    entity.business_date = report.business_date
    entity.shift_config_id = shift.id
    entity.workshop_id = workshop.id
    entity.team_id = team.id if team else None
    entity.input_weight = _to_float(report.input_weight)
    entity.output_weight = output_weight
    entity.qualified_weight = qualified_weight
    entity.scrap_weight = _to_float(report.scrap_weight)
    entity.planned_headcount = report.attendance_count
    entity.actual_headcount = report.attendance_count
    entity.downtime_minutes = 0
    entity.downtime_reason = None
    entity.issue_count = 1 if report.has_exception else 0
    entity.electricity_kwh = _to_float(report.electricity_daily)
    entity.data_source = 'mobile'
    entity.data_status = 'pending'
    entity.reviewed_by = None
    entity.reviewed_at = None
    entity.confirmed_by = None
    entity.confirmed_at = None
    entity.rejected_by = None
    entity.rejected_at = None
    entity.rejected_reason = None
    entity.voided_by = None
    entity.voided_at = None
    entity.voided_reason = None
    entity.published_at = None
    entity.published_by = None
    entity.notes = report.note
    db.flush()
    report.linked_production_data_id = entity.id
    return entity

def _required_submit_fields(payload: dict) -> list[str]:
    field_labels = {
        'input_weight': '投入重量',
        'output_weight': '产出重量',
    }
    missing: list[str] = []
    for field in ('input_weight', 'output_weight'):
        value = payload.get(field)
        if value is None or value == '':
            missing.append(field_labels[field])
    return missing

MOBILE_REPORT_DATA_KEY_MAP = {
    'operator_notes': 'note',
}

MOBILE_REPORT_ALLOWED_DATA_KEYS = {
    'attendance_count',
    'input_weight',
    'output_weight',
    'scrap_weight',
    'storage_prepared',
    'storage_finished',
    'shipment_weight',
    'contract_received',
    'electricity_daily',
    'gas_daily',
    'has_exception',
    'exception_type',
    'operator_notes',
    'note',
    'optional_photo_url',
    'machine_energy_records',
}

def _normalize_mobile_report_payload(payload: dict) -> dict:
    normalized = dict(payload)
    nested = normalized.pop('data', None) or {}
    if not isinstance(nested, dict):
        nested = {}

    for source_key, value in nested.items():
        if source_key not in MOBILE_REPORT_ALLOWED_DATA_KEYS:
            continue
        target_key = MOBILE_REPORT_DATA_KEY_MAP.get(source_key, source_key)
        if normalized.get(target_key) is None:
            normalized[target_key] = value

    return normalized

def _save_machine_energy_records(db: Session, *, report_id: int, records: list[dict]) -> None:
    db.query(MachineEnergyRecord).filter(MachineEnergyRecord.shift_report_id == report_id).delete()
    for rec in records:
        if rec.get('energy_kwh') is None and rec.get('gas_m3') is None:
            continue
        db.add(MachineEnergyRecord(
            shift_report_id=report_id,
            machine_id=rec.get('machine_id'),
            machine_code=rec.get('machine_code', ''),
            machine_name=rec.get('machine_name', ''),
            energy_kwh=rec.get('energy_kwh'),
            gas_m3=rec.get('gas_m3'),
        ))

def _load_machine_energy_records(db: Session, *, report_id: int) -> list[dict]:
    rows = (
        db.query(MachineEnergyRecord)
        .filter(MachineEnergyRecord.shift_report_id == report_id)
        .order_by(MachineEnergyRecord.id.asc())
        .all()
    )
    return [
        {
            'id': row.id,
            'machine_id': row.machine_id,
            'machine_code': row.machine_code,
            'machine_name': row.machine_name,
            'energy_kwh': _to_float(row.energy_kwh),
            'gas_m3': _to_float(row.gas_m3),
        }
        for row in rows
    ]

def _sum_machine_energy(records: list[dict]) -> tuple[float | None, float | None]:
    kwh_values = [r.get('energy_kwh') or 0 for r in records if r.get('energy_kwh') is not None]
    gas_values = [r.get('gas_m3') or 0 for r in records if r.get('gas_m3') is not None]
    total_kwh = sum(kwh_values) if kwh_values else None
    total_gas = sum(gas_values) if gas_values else None
    return total_kwh, total_gas

def store_report_photo(
    report,
    *,
    file_bytes: bytes,
    original_name: str,
    upload_dir: Path,
    actor_user_id: int,
    now: datetime | None = None,
    public_prefix: str = '/uploads',
) -> dict:
    upload_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (now or _local_now()).strftime('%Y%m%d%H%M%S')
    business_date = str(getattr(report, 'business_date', date.today()))
    relative_dir = Path('mobile') / business_date
    file_name = _normalize_filename(original_name)
    stored_name = f"report_{getattr(report, 'id', 'draft')}_{timestamp}_{uuid4().hex[:8]}{Path(file_name).suffix.lower()}"
    absolute_dir = upload_dir / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)
    stored_path = absolute_dir / stored_name
    stored_path.write_bytes(file_bytes)

    relative_path = stored_path.relative_to(upload_dir).as_posix()
    uploaded_at = now or _local_now()
    report.photo_file_path = relative_path
    report.photo_file_name = original_name
    report.photo_uploaded_at = uploaded_at
    report.optional_photo_url = _public_upload_url(relative_path, public_prefix=public_prefix)
    report.last_action_by_user_id = actor_user_id

    return {
        'relative_path': relative_path,
        'file_url': _public_upload_url(relative_path, public_prefix=public_prefix),
        'uploaded_at': uploaded_at,
    }

def upload_report_photo(
    db: Session,
    *,
    business_date: date,
    shift_id: int,
    file_name: str,
    file_bytes: bytes,
    current_user: User,
    override_reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    assert_mobile_user_access(current_user)
    workshop, team = _resolve_workshop_team(db, current_user)
    _ensure_mobile_write_scope(current_user, workshop_id=workshop.id, shift_id=shift_id)
    assert_scope_access(
        current_user,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
        shift_id=shift_id,
    )
    shift = db.get(ShiftConfig, shift_id)
    if shift is None or not shift.is_active:
        raise HTTPException(status_code=404, detail='shift not found')

    suffix = Path(file_name or '').suffix.lower()
    if suffix not in PHOTO_ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail='unsupported photo type')
    if len(file_bytes) > PHOTO_MAX_BYTES:
        raise HTTPException(status_code=400, detail='photo exceeds size limit')

    report = _find_mobile_report(
        db,
        business_date=business_date,
        shift_id=shift_id,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
    )
    if report is None:
        report = MobileShiftReport(
            business_date=business_date,
            shift_config_id=shift.id,
            workshop_id=workshop.id,
            team_id=team.id if team else None,
            owner_user_id=current_user.id,
            leader_user_id=current_user.id,
            leader_name=current_user.name,
            dingtalk_user_id=current_user.dingtalk_user_id,
            dingtalk_union_id=current_user.dingtalk_union_id,
            report_status='draft',
            last_saved_at=_local_now(),
        )
        db.add(report)
        db.flush()
    else:
        assert_mobile_report_access(current_user, report=report, write=True)
        _ensure_mobile_override_for_locked_report(
            report,
            current_user,
            override_reason=_normalize_override_reason(override_reason),
        )

    original = _model_to_dict(report)
    stored = store_report_photo(
        report,
        file_bytes=file_bytes,
        original_name=file_name,
        upload_dir=settings.upload_dir_path,
        actor_user_id=current_user.id,
        public_prefix='/uploads',
    )
    db.flush()
    record_entity_change(
        db,
        user=current_user,
        action='mobile_report_upload_photo',
        module='mobile',
        entity_type='mobile_shift_reports',
        entity_id=report.id,
        old_value=_json_ready(original),
        new_value=_json_ready(_model_to_dict(report)),
        reason=_normalize_override_reason(override_reason),
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    db.commit()
    db.refresh(report)
    return {
        'report_id': report.id,
        'photo_file_name': report.photo_file_name,
        'photo_file_path': report.photo_file_path,
        'photo_file_url': stored['file_url'],
        'uploaded_at': report.photo_uploaded_at,
    }

def get_report_detail(
    db: Session,
    *,
    business_date: date,
    shift_id: int,
    current_user: User,
) -> dict:
    assert_mobile_user_access(current_user)
    workshop, team = _resolve_workshop_team(db, current_user)
    shift = db.get(ShiftConfig, shift_id)
    if shift is None or not shift.is_active:
        raise HTTPException(status_code=404, detail='当前班次不存在或已停用，请联系管理员检查班次配置。')
    assert_scope_access(
        current_user,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
        shift_id=shift_id,
    )
    report = _find_mobile_report(
        db,
        business_date=business_date,
        shift_id=shift_id,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
    )
    if report is not None:
        assert_mobile_report_access(current_user, report=report, write=False)
    return _serialize_mobile_report(
        db,
        report,
        business_date=business_date,
        shift=shift,
        workshop=workshop,
        team=team,
        leader_name=current_user.name,
    )

def save_or_submit_report(
    db: Session,
    *,
    payload: dict,
    current_user: User,
    submit: bool,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    assert_mobile_user_access(current_user)
    payload = _normalize_mobile_report_payload(payload)
    workshop, team = _resolve_workshop_team(db, current_user)
    shift = db.get(ShiftConfig, int(payload['shift_id']))
    if shift is None or not shift.is_active:
        raise HTTPException(status_code=404, detail='当前班次不存在或已停用，请联系管理员检查班次配置。')
    override_reason = _normalize_override_reason(payload.pop('override_reason', None))
    _ensure_mobile_write_scope(current_user, workshop_id=workshop.id, shift_id=shift.id)
    assert_scope_access(
        current_user,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
        shift_id=shift.id,
    )

    business_date = payload['business_date']
    report = _find_mobile_report(
        db,
        business_date=business_date,
        shift_id=shift.id,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
    )
    if report is None:
        report = MobileShiftReport(
            business_date=business_date,
            shift_config_id=shift.id,
            workshop_id=workshop.id,
            team_id=team.id if team else None,
            owner_user_id=current_user.id,
            leader_user_id=current_user.id,
            leader_name=current_user.name,
            dingtalk_user_id=current_user.dingtalk_user_id,
            dingtalk_union_id=current_user.dingtalk_union_id,
        )
        db.add(report)
    else:
        assert_mobile_report_access(current_user, report=report, write=True)
        _ensure_mobile_override_for_locked_report(report, current_user, override_reason=override_reason)

    original = _model_to_dict(report)
    report.owner_user_id = report.owner_user_id or current_user.id
    report.leader_user_id = current_user.id
    report.leader_name = current_user.name
    report.dingtalk_user_id = current_user.dingtalk_user_id
    report.dingtalk_union_id = current_user.dingtalk_union_id
    report.last_action_by_user_id = current_user.id
    report.attendance_count = payload.get('attendance_count')
    report.input_weight = payload.get('input_weight')
    report.output_weight = payload.get('output_weight')
    report.scrap_weight = payload.get('scrap_weight')
    report.storage_prepared = payload.get('storage_prepared')
    report.storage_finished = payload.get('storage_finished')
    report.shipment_weight = payload.get('shipment_weight')
    report.contract_received = payload.get('contract_received')
    report.electricity_daily = payload.get('electricity_daily')
    report.gas_daily = payload.get('gas_daily')
    report.has_exception = bool(payload.get('has_exception'))
    report.exception_type = payload.get('exception_type')
    report.note = payload.get('note')
    report.optional_photo_url = payload.get('optional_photo_url')
    report.last_saved_at = _local_now()

    machine_energy_records = payload.get('machine_energy_records') or []
    if machine_energy_records:
        total_kwh, total_gas = _sum_machine_energy(machine_energy_records)
        report.electricity_daily = total_kwh
        report.gas_daily = total_gas

    decision_snapshot = None
    if submit:
        missing = _required_submit_fields(payload)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f'以下必填项未填写：{", ".join(missing)}。请补全后再提交。',
            )
        report.report_status = 'submitted'
        report.submitted_at = _local_now()
        report.submitted_by_user_id = current_user.id
        report.returned_reason = None
        _sync_to_shift_production(db, report=report, shift=shift, workshop=workshop, team=team)
        db.flush()

        # === 自动校验（替代人工审核）===
        # 工人提交后，由校验 Agent 自动判断数据是否合格
        # 合格则自动确认，不合格则退回并给出可执行修改建议
        _report_data = {
            'attendance_count': getattr(report, 'attendance_count', None),
            'input_weight': _to_float(getattr(report, 'input_weight', None)),
            'output_weight': _to_float(getattr(report, 'output_weight', None)),
            'scrap_weight': _to_float(getattr(report, 'scrap_weight', None)),
            'electricity_daily': _to_float(getattr(report, 'electricity_daily', None)),
            'gas_daily': _to_float(getattr(report, 'gas_daily', None)),
        }
        decisions = validator_agent.execute(
            db=db,
            report_id=report.id,
            report_data=_report_data,
            workshop_code=workshop.code,
        )
        decision_snapshot = _build_agent_decision_snapshot(report=report, decisions=decisions)
        log_pilot_event(
            "worker_report_submitted",
            report_id=report.id,
            workshop_id=workshop.id,
            team_id=team.id if team else None,
            shift_id=shift.id,
            user_id=current_user.id,
            final_report_status=report.report_status,
            linked_production_data_id=report.linked_production_data_id,
            has_returned_reason=bool(report.returned_reason),
        )
        action = 'mobile_report_submit'
    else:
        if report.report_status not in {'returned', *APPROVED_REPORT_STATUSES}:
            report.report_status = 'draft'
        action = 'mobile_report_save'

    db.flush()
    if machine_energy_records:
        _save_machine_energy_records(db, report_id=report.id, records=machine_energy_records)
    record_entity_change(
        db,
        user=current_user,
        action=action,
        module='mobile',
        entity_type='mobile_shift_reports',
        entity_id=report.id,
        old_value=_json_ready(original),
        new_value=_json_ready(_model_to_dict(report)),
        reason=override_reason,
        ip_address=ip_address,
        user_agent=user_agent,
        auto_commit=False,
    )
    db.commit()
    db.refresh(report)
    return _serialize_mobile_report(
        db,
        report,
        business_date=business_date,
        shift=shift,
        workshop=workshop,
        team=team,
        leader_name=current_user.name,
        agent_decision_snapshot=decision_snapshot,
    )

def list_report_history(db: Session, *, current_user: User, limit: int = 10) -> dict:
    summary = assert_mobile_user_access(current_user)
    workshop, team = _resolve_workshop_team(db, current_user)
    query = db.query(MobileShiftReport).filter(MobileShiftReport.workshop_id == workshop.id)
    if team is None:
        query = query.filter(MobileShiftReport.team_id.is_(None))
    else:
        query = query.filter(MobileShiftReport.team_id == team.id)
    if not summary.is_admin:
        query = query.filter(MobileShiftReport.owner_user_id == current_user.id)

    rows = (
        query.order_by(
            MobileShiftReport.business_date.desc(),
            MobileShiftReport.updated_at.desc().nullslast(),
            MobileShiftReport.id.desc(),
        )
        .limit(max(1, min(limit, 30)))
        .all()
    )
    shift_ids = {row.shift_config_id for row in rows}
    shift_map = {item.id: item for item in db.query(ShiftConfig).filter(ShiftConfig.id.in_(shift_ids)).all()} if rows else {}
    items = [
        {
            'id': row.id,
            'business_date': row.business_date,
            'shift_id': row.shift_config_id,
            'shift_code': shift_map.get(row.shift_config_id).code if shift_map.get(row.shift_config_id) else None,
            'shift_name': shift_map.get(row.shift_config_id).name if shift_map.get(row.shift_config_id) else None,
            'workshop_name': workshop.name,
            'team_name': team.name if team else None,
            'report_status': row.report_status,
            'output_weight': _to_float(row.output_weight),
            'electricity_daily': _to_float(row.electricity_daily),
            'gas_daily': _to_float(row.gas_daily),
            'has_exception': row.has_exception,
            'exception_type': row.exception_type,
            'photo_file_name': row.photo_file_name,
            'submitted_at': row.submitted_at,
            'last_saved_at': row.last_saved_at,
            'returned_reason': row.returned_reason,
        }
        for row in rows
    ]
    return {'items': items, 'total': len(items)}

def sync_mobile_status_from_review(
    db: Session,
    *,
    shift_data_id: int,
    action: str,
    reason: str | None,
    actor_user_id: int | None = None,
) -> None:
    report = db.query(MobileShiftReport).filter(MobileShiftReport.linked_production_data_id == shift_data_id).first()
    if report is None:
        return
    if actor_user_id is not None:
        report.last_action_by_user_id = actor_user_id
    if action == 'confirm':
        report.report_status = 'approved'
        report.returned_reason = None
    elif action in {'reject', 'void'}:
        report.report_status = 'returned'
        report.returned_reason = (reason or '').strip() or '数据未通过校验，请按提示修改后重新提交。'
    db.flush()
