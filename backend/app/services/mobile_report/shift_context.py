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


def _shift_window_for_date(business_date: date, shift: ShiftConfig) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(business_date, shift.start_time, tzinfo=LOCAL_TZ)
    end_dt = datetime.combine(business_date, shift.end_time, tzinfo=LOCAL_TZ)
    if shift.business_day_offset:
        start_dt += timedelta(days=shift.business_day_offset)
        end_dt += timedelta(days=shift.business_day_offset)
    if shift.is_cross_day or shift.end_time <= shift.start_time:
        end_dt += timedelta(days=1)
    return start_dt, end_dt

def _resolve_workshop_team(db: Session, current_user: User) -> tuple[Workshop, Team | None]:
    workshop_id = current_user.workshop_id
    team_id = current_user.team_id
    if workshop_id is None and current_user.role == 'admin':
        fallback_workshop = db.query(Workshop).order_by(Workshop.sort_order.asc(), Workshop.id.asc()).first()
        workshop_id = fallback_workshop.id if fallback_workshop else None
        if fallback_workshop is not None and team_id is None:
            fallback_team = (
                db.query(Team)
                .filter(Team.workshop_id == fallback_workshop.id)
                .order_by(Team.sort_order.asc(), Team.id.asc())
                .first()
            )
            team_id = fallback_team.id if fallback_team else None

    if workshop_id is None:
        raise HTTPException(status_code=400, detail='当前账号未绑定车间，请先在用户管理中设置车间归属。')
    workshop = db.get(Workshop, workshop_id)
    if workshop is None:
        raise HTTPException(status_code=400, detail='当前账号绑定的车间不存在，请联系管理员修正主数据。')
    team = db.get(Team, team_id) if team_id else None
    if team is not None and (not team.is_active or team.workshop_id != workshop.id):
        team = None
    return workshop, team

def _shift_candidates(db: Session, workshop_id: int) -> list[ShiftConfig]:
    return (
        db.query(ShiftConfig)
        .filter(
            ShiftConfig.is_active.is_(True),
            or_(ShiftConfig.workshop_id == workshop_id, ShiftConfig.workshop_id.is_(None)),
        )
        .order_by(ShiftConfig.sort_order.asc(), ShiftConfig.id.asc())
        .all()
    )

def _machine_shift_candidates(
    db: Session,
    *,
    workshop_id: int,
    machine: Equipment | None,
) -> list[ShiftConfig]:
    items = _shift_candidates(db, workshop_id)
    if machine is None or not machine.assigned_shift_ids:
        return items
    allowed_ids = {int(item) for item in machine.assigned_shift_ids}
    return [item for item in items if item.id in allowed_ids]

def _pick_shift_by_time(candidates: list[tuple[date, ShiftConfig]], now: datetime) -> tuple[date, ShiftConfig] | None:
    for business_date, shift in candidates:
        start_dt, end_dt = _shift_window_for_date(business_date, shift)
        if start_dt <= now <= end_dt:
            return business_date, shift
    return None

def _infer_current_shift(db: Session, current_user: User, now: datetime | None = None) -> ShiftContext:
    current_local = _local_now(now)
    workshop, team = _resolve_workshop_team(db, current_user)
    machine = get_bound_machine_for_user(db, user_id=current_user.id)
    candidate_dates = [current_local.date(), current_local.date() - timedelta(days=1)]
    shifts_by_id = {item.id: item for item in _machine_shift_candidates(db, workshop_id=workshop.id, machine=machine)}

    schedule_query = (
        db.query(AttendanceSchedule.business_date, AttendanceSchedule.shift_config_id)
        .filter(
            AttendanceSchedule.business_date.in_(candidate_dates),
            AttendanceSchedule.workshop_id == workshop.id,
            AttendanceSchedule.shift_config_id.is_not(None),
        )
        .distinct()
    )
    if team is not None:
        schedule_query = schedule_query.filter(
            or_(AttendanceSchedule.team_id == team.id, AttendanceSchedule.team_id.is_(None))
        )
    schedule_rows = schedule_query.all()
    scheduled_candidates = [
        (row.business_date, shifts_by_id[row.shift_config_id])
        for row in schedule_rows
        if row.shift_config_id in shifts_by_id
    ]
    matched = _pick_shift_by_time(scheduled_candidates, current_local)
    if matched:
        return ShiftContext(business_date=matched[0], shift=matched[1], workshop=workshop, team=team, machine=machine)

    if scheduled_candidates:
        scheduled_candidates.sort(key=lambda item: (item[0], item[1].sort_order, item[1].id), reverse=True)
        business_date, shift = scheduled_candidates[0]
        return ShiftContext(business_date=business_date, shift=shift, workshop=workshop, team=team, machine=machine)

    fallback_candidates = [(candidate_date, shift) for candidate_date in candidate_dates for shift in shifts_by_id.values()]
    matched = _pick_shift_by_time(fallback_candidates, current_local)
    if matched:
        return ShiftContext(business_date=matched[0], shift=matched[1], workshop=workshop, team=team, machine=machine)

    first_shift = next(iter(shifts_by_id.values()), None)
    return ShiftContext(business_date=current_local.date(), shift=first_shift, workshop=workshop, team=team, machine=machine)

def _get_workshop_machines(db: Session, *, workshop_id: int) -> list[dict]:
    if not hasattr(db, 'query'):
        return []
    machines = (
        db.query(Equipment)
        .filter(
            Equipment.workshop_id == workshop_id,
            Equipment.equipment_type != 'virtual_workshop_qr',
            Equipment.equipment_type != 'virtual_role_qr',
            Equipment.operational_status == 'running',
        )
        .order_by(Equipment.sort_order.asc(), Equipment.id.asc())
        .all()
    )
    if not machines:
        machines = (
            db.query(Equipment)
            .filter(
                Equipment.workshop_id == workshop_id,
                Equipment.equipment_type == 'virtual_role_qr',
                Equipment.qr_code.like('XT-%-%-OP'),
            )
            .order_by(Equipment.sort_order.asc(), Equipment.id.asc())
            .all()
        )
    return [
        {
            'machine_id': m.id,
            'machine_code': m.code,
            'machine_name': m.name,
        }
        for m in machines
    ]

def _build_current_shift_fallback(
    *,
    current_user: User,
    identity: dict,
    ownership_note: str,
    workshop: Workshop | None = None,
    machine: Equipment | None = None,
) -> dict:
    return {
        'business_date': _local_now().date(),
        'shift_id': None,
        'shift_code': None,
        'shift_name': None,
        'workshop_id': workshop.id if workshop else current_user.workshop_id,
        'workshop_code': workshop.code if workshop else None,
        'workshop_name': workshop.name if workshop else None,
        'workshop_type': None,
        'machine_id': machine.id if machine else None,
        'machine_code': machine.code if machine else None,
        'machine_name': machine.name if machine else None,
        'is_machine_bound': machine is not None,
        'machine_custom_fields': (machine.custom_fields or []) if machine else [],
        'team_id': None,
        'team_name': None,
        'leader_name': current_user.name,
        'report_id': None,
        'report_status': 'unreported',
        'entry_channel': identity.get('entry_channel', 'web_debug'),
        'dingtalk_ready': bool(identity.get('dingtalk_ready', False)),
        'dingtalk_hint': identity.get('dingtalk_hint'),
        'ownership_note': ownership_note,
        'active_reminders': [],
        'attendance_confirmation_id': None,
        'attendance_machine_id': None,
        'attendance_machine_name': None,
        'attendance_status': 'not_started',
        'attendance_exception_count': 0,
        'attendance_pending_count': 0,
        'can_submit': False,
    }

def _resolve_entry_mode(role: str) -> str:
    if role in ('shift_leader', 'mobile_user', 'team_leader', 'deputy_leader'):
        return 'coil_entry'
    if role in ('energy_stat', 'maintenance_lead', 'hydraulic_lead', 'consumable_stat', 'qc', 'weigher'):
        return 'auxiliary_shift_entry'
    if role in ('utility_manager', 'inventory_keeper', 'contracts'):
        return 'owner_daily_entry'
    return 'coil_entry'

SHIFT_REPORT_OWNERSHIP_ROLES = {'shift_leader', 'mobile_user', 'team_leader', 'deputy_leader'}

def _uses_shift_report_ownership(current_user: User) -> bool:
    return (current_user.role or '').strip() in SHIFT_REPORT_OWNERSHIP_ROLES

def get_mobile_bootstrap(db: Session, *, current_user: User) -> dict:
    assert_mobile_user_access(current_user)
    payload = dingtalk_service.service.build_mobile_bootstrap(current_user)
    data_entry_mode = settings.mobile_data_entry_mode_normalized
    payload['current_scope_summary'] = scope_to_dict(build_scope_summary(current_user))
    payload['data_entry_mode'] = data_entry_mode
    payload['entry_mode'] = _resolve_entry_mode(current_user.role or '')
    payload['user_role'] = current_user.role
    payload['scan_assist_enabled'] = settings.MOBILE_SCAN_ASSIST_ENABLED
    payload['mes_display_enabled'] = settings.MOBILE_MES_DISPLAY_ENABLED
    payload['phase_notice'] = (
        '当前阶段先由主操手工录入，系统自动校验与汇总；扫码补数与 MES 自动带数后续开放。'
        if data_entry_mode == 'manual_only'
        else None
    )
    machine = get_bound_machine_for_user(db, user_id=current_user.id)
    payload['is_machine_bound'] = machine is not None
    payload['machine_id'] = machine.id if machine else None
    payload['machine_code'] = machine.code if machine else None
    payload['machine_name'] = machine.name if machine else None
    if machine is not None:
        workshop = db.get(Workshop, machine.workshop_id)
        payload['workshop_id'] = workshop.id if workshop else machine.workshop_id
        payload['workshop_name'] = workshop.name if workshop else None
    else:
        payload['workshop_id'] = current_user.workshop_id
        payload['workshop_name'] = None
    return payload

def get_current_shift(db: Session, *, current_user: User) -> dict:
    summary = assert_mobile_user_access(current_user)
    identity = dingtalk_service.service.resolve_mobile_identity(current_user)
    try:
        context = _infer_current_shift(db, current_user)
    except HTTPException as exc:
        if exc.status_code in {400, 404}:
            workshop = db.get(Workshop, current_user.workshop_id) if current_user.workshop_id else None
            machine = get_bound_machine_for_user(db, user_id=current_user.id)
            return _build_current_shift_fallback(
                current_user=current_user,
                identity=identity,
                ownership_note='当前账号未绑定车间，无法进行填报。',
                workshop=workshop,
                machine=machine,
            )
        raise
    attendance_snapshot = {
        'attendance_confirmation_id': None,
        'attendance_machine_id': None,
        'attendance_machine_name': None,
        'attendance_status': 'not_started',
        'attendance_exception_count': 0,
        'attendance_pending_count': 0,
    }
    uses_report_ownership = _uses_shift_report_ownership(current_user)
    report = None
    if context.shift is not None:
        from app.services import attendance_confirm_service

        attendance_snapshot = attendance_confirm_service.get_shift_confirmation_snapshot(
            db,
            business_date=context.business_date,
            workshop_id=context.workshop.id,
            shift_id=context.shift.id,
        )
        if uses_report_ownership:
            report = _find_mobile_report(
                db,
                business_date=context.business_date,
                shift_id=context.shift.id,
                workshop_id=context.workshop.id,
                team_id=context.team.id if context.team else None,
            )
    ownership_note = _ownership_note(report=report, current_user=current_user) if uses_report_ownership else None
    if context.shift is None:
        ownership_note = '当前车间未配置可用班次，请联系管理员在“班次配置”中启用班次。'
    can_submit = context.shift is not None
    report_id = report.id if report else None
    entry_mode = _resolve_entry_mode(current_user.role or '')
    report_status = report.report_status if report else ('coil_entry' if context.shift and entry_mode == 'coil_entry' else 'unreported')
    if ownership_note and not summary.is_admin:
        can_submit = False
        report_id = None
        report_status = 'locked'

    try:
        workshop_type = resolve_workshop_type(
            workshop_type=getattr(context.workshop, 'workshop_type', None),
            workshop_code=context.workshop.code,
            workshop_name=context.workshop.name,
        )
    except HTTPException as exc:
        if exc.status_code == 404 and str(exc.detail) == 'workshop template not found':
            return _build_current_shift_fallback(
                current_user=current_user,
                identity=identity,
                ownership_note='当前车间未配置填报模板，请联系管理员在“车间模板配置”中补齐。',
                workshop=context.workshop,
                machine=context.machine,
            )
        raise

    return {
        'business_date': context.business_date,
        'shift_id': context.shift.id if context.shift else None,
        'shift_code': context.shift.code if context.shift else None,
        'shift_name': context.shift.name if context.shift else None,
        'workshop_id': context.workshop.id,
        'workshop_code': context.workshop.code,
        'workshop_name': context.workshop.name,
        'workshop_type': workshop_type,
        'machine_id': context.machine.id if context.machine else None,
        'machine_code': context.machine.code if context.machine else None,
        'machine_name': context.machine.name if context.machine else None,
        'is_machine_bound': context.machine is not None,
        'machine_custom_fields': (context.machine.custom_fields or []) if context.machine else [],
        'team_id': context.team.id if context.team else None,
        'team_name': context.team.name if context.team else None,
        'leader_name': current_user.name,
        'report_id': report_id,
        'report_status': report_status,
        'entry_channel': identity['entry_channel'],
        'dingtalk_ready': identity['dingtalk_ready'],
        'dingtalk_hint': identity['dingtalk_hint'],
        'ownership_note': ownership_note,
        'active_reminders': _active_reminders_for_context(
            db,
            business_date=context.business_date,
            shift_id=context.shift.id if context.shift else 0,
            workshop_id=context.workshop.id,
            team_id=context.team.id if context.team else None,
            leader_user_id=current_user.id,
        )
        if context.shift is not None
        else [],
        **attendance_snapshot,
        'workshop_machines': _get_workshop_machines(db, workshop_id=context.workshop.id),
        'can_submit': can_submit,
    }
