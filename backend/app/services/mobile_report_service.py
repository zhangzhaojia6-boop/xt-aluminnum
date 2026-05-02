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

AUTO_CONFIRMED_REPORT_STATUS = 'auto_confirmed'
APPROVED_REPORT_STATUSES = {'approved', AUTO_CONFIRMED_REPORT_STATUS}
SUBMITTED_STATUSES = {'submitted', *APPROVED_REPORT_STATUSES}
LOCAL_TZ = ZoneInfo(settings.DEFAULT_TIMEZONE)
PHOTO_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
PHOTO_MAX_BYTES = 5 * 1024 * 1024


@dataclass(slots=True)
class ShiftContext:
    business_date: date
    shift: ShiftConfig | None
    workshop: Workshop
    team: Team | None
    machine: Equipment | None = None


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _json_ready(value):
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _model_to_dict(entity) -> dict:
    return {column.name: getattr(entity, column.name) for column in entity.__table__.columns}


def _normalize_override_reason(value: str | None) -> str | None:
    normalized = (value or '').strip()
    return normalized or None


def _mobile_report_decision_status(report: MobileShiftReport | None) -> str:
    if report is None:
        return 'unreported'
    if _normalize_override_reason(getattr(report, 'returned_reason', None)) is not None:
        return 'returned'
    report_status = getattr(report, 'report_status', None)
    if report_status in APPROVED_REPORT_STATUSES:
        return AUTO_CONFIRMED_REPORT_STATUS
    if report_status == 'returned':
        return 'returned'
    return report_status or 'unreported'


def _is_mobile_report_auto_confirmed(report: MobileShiftReport | None) -> bool:
    return _mobile_report_decision_status(report) == AUTO_CONFIRMED_REPORT_STATUS


def _build_agent_decision_snapshot(
    *,
    report: MobileShiftReport | None,
    decisions: list[AgentDecision] | None = None,
) -> dict:
    latest = decisions[-1] if decisions else None
    if latest is not None:
        details = latest.details or {}
        if latest.action == AgentAction.AUTO_CONFIRM:
            status = AUTO_CONFIRMED_REPORT_STATUS
        elif latest.action == AgentAction.AUTO_REJECT:
            status = 'returned'
        else:
            status = _mobile_report_decision_status(report)
        return {
            'agent_decision_status': status,
            'agent_decision_action': latest.action.value,
            'agent_decision_agent': latest.agent_name,
            'agent_decision_reason': latest.reason,
            'agent_decision_warnings': [str(item) for item in (details.get('warnings') or [])],
            'agent_decision_errors': [str(item) for item in (details.get('errors') or [])],
            'agent_decision_at': latest.timestamp,
        }

    status = _mobile_report_decision_status(report)
    if status == AUTO_CONFIRMED_REPORT_STATUS:
        return {
            'agent_decision_status': AUTO_CONFIRMED_REPORT_STATUS,
            'agent_decision_action': AgentAction.AUTO_CONFIRM.value,
            'agent_decision_agent': 'validator',
            'agent_decision_reason': '系统自动校验通过',
            'agent_decision_warnings': [],
            'agent_decision_errors': [],
            'agent_decision_at': None,
        }
    if status == 'returned':
        return {
            'agent_decision_status': 'returned',
            'agent_decision_action': AgentAction.AUTO_REJECT.value,
            'agent_decision_agent': 'validator',
            'agent_decision_reason': (
                _normalize_override_reason(getattr(report, 'returned_reason', None))
                or '系统自动校验未通过，请按提示修正后再提交。'
            ),
            'agent_decision_warnings': [],
            'agent_decision_errors': [],
            'agent_decision_at': None,
        }
    return {
        'agent_decision_status': status if report is not None else None,
        'agent_decision_action': None,
        'agent_decision_agent': None,
        'agent_decision_reason': None,
        'agent_decision_warnings': [],
        'agent_decision_errors': [],
        'agent_decision_at': None,
    }


def _ensure_mobile_write_scope(current_user: User, *, workshop_id: int, shift_id: int) -> None:
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.is_reviewer:
        return
    if current_user.workshop_id is None or int(current_user.workshop_id) != int(workshop_id):
        raise HTTPException(status_code=403, detail='当前账号不在该车间权限内，请联系管理员检查用户归属。')
    if summary.assigned_shift_ids and int(shift_id) not in summary.assigned_shift_ids:
        raise HTTPException(status_code=403, detail='当前账号未分配该班次，请联系管理员检查班次权限。')


def _ensure_mobile_override_for_locked_report(report: MobileShiftReport, current_user: User, *, override_reason: str | None) -> None:
    if report.report_status not in SUBMITTED_STATUSES:
        return
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.is_reviewer:
        if override_reason is not None:
            return
    raise HTTPException(
        status_code=403,
        detail='submitted or approved reports require reviewer/admin override with reason',
    )


def _round_value(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _public_upload_url(relative_path: str, *, public_prefix: str = '/uploads') -> str:
    prefix = public_prefix.rstrip('/')
    return f"{prefix}/{relative_path.lstrip('/')}"


def _normalize_filename(name: str) -> str:
    raw_name = (name or '').strip() or 'photo'
    suffix = Path(raw_name).suffix.lower()
    if suffix not in PHOTO_ALLOWED_EXTENSIONS:
        suffix = '.jpg'
    stem = Path(raw_name).stem.strip().replace(' ', '_') or 'photo'
    safe_stem = ''.join(char for char in stem if char.isalnum() or char in {'_', '-', '.', '\u4e00', '\u9fff'})
    safe_stem = safe_stem[:48] or 'photo'
    return f'{safe_stem}{suffix}'


def _local_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(LOCAL_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=LOCAL_TZ)
    return now.astimezone(LOCAL_TZ)


def _month_range(target_date: date) -> tuple[date, date]:
    month_start = target_date.replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1) - timedelta(days=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1) - timedelta(days=1)
    return month_start, month_end


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


def _serialize_active_reminders(rows: list[MobileReminderRecord]) -> list[dict]:
    return [
        {
            'id': row.id,
            'reminder_type': row.reminder_type,
            'reminder_status': row.reminder_status,
            'reminder_channel': row.reminder_channel,
            'reminder_count': row.reminder_count,
            'last_reminded_at': row.last_reminded_at,
            'note': row.note,
        }
        for row in rows
    ]


def _active_reminders_for_context(
    db: Session,
    *,
    business_date: date,
    shift_id: int,
    workshop_id: int,
    team_id: int | None,
    leader_user_id: int | None,
) -> list[dict]:
    query = db.query(MobileReminderRecord).filter(
        MobileReminderRecord.business_date == business_date,
        MobileReminderRecord.shift_config_id == shift_id,
        MobileReminderRecord.workshop_id == workshop_id,
        MobileReminderRecord.reminder_status.in_(['pending', 'sent', 'acknowledged']),
    )
    if team_id is None:
        query = query.filter(MobileReminderRecord.team_id.is_(None))
    else:
        query = query.filter(MobileReminderRecord.team_id == team_id)
    if leader_user_id is not None:
        query = query.filter(MobileReminderRecord.leader_user_id == leader_user_id)
    rows = query.order_by(MobileReminderRecord.id.desc()).all()
    return _serialize_active_reminders(rows)


def _ownership_note(*, report: MobileShiftReport | None, current_user: User) -> str | None:
    if report is None:
        return None
    owner_user_id = report.owner_user_id or report.leader_user_id
    if owner_user_id and owner_user_id != current_user.id:
        return '当前班次已由其他负责人处理，如需代填请走授权流程。'
    return None


def _same_month(base_date: date, compare_date: date) -> bool:
    return base_date.year == compare_date.year and base_date.month == compare_date.month


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
        config_warnings.append('当日应报清单为空，请先导入排班/应报数据后再看上报率。')

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
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
            Workshop.workshop_type == 'inventory',
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
        payload['storage_finished'] += _to_float(extra_payload.get('storage_inbound_weight')) or 0.0
        payload['shipment_weight'] += _to_float(extra_payload.get('shipment_weight')) or 0.0
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
    rows = (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.shift_id == shift_id,
        )
        .order_by(WorkOrderEntry.id.desc())
        .all()
    )
    from app.models.production import WorkOrder
    wo_ids = {r.work_order_id for r in rows}
    wo_map = {}
    if wo_ids:
        wos = db.query(WorkOrder).filter(WorkOrder.id.in_(wo_ids)).all()
        wo_map = {wo.id: wo for wo in wos}
    result = []
    for r in rows:
        wo = wo_map.get(r.work_order_id)
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
            'business_date': r.business_date,
            'created_at': r.created_at if hasattr(r, 'created_at') else None,
        })
    return result


def _aggregate_coil_to_shift(db: Session, *, business_date: date, shift_id: int, workshop_id: int):
    agg = (
        db.query(
            func.sum(WorkOrderEntry.input_weight).label('total_input'),
            func.sum(WorkOrderEntry.output_weight).label('total_output'),
            func.sum(WorkOrderEntry.scrap_weight).label('total_scrap'),
            func.count(WorkOrderEntry.id).label('coil_count'),
        )
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.shift_id == shift_id,
            WorkOrderEntry.workshop_id == workshop_id,
        )
        .first()
    )
    if not agg or not agg.coil_count:
        return
    spd = (
        db.query(ShiftProductionData)
        .filter(
            ShiftProductionData.business_date == business_date,
            ShiftProductionData.shift_config_id == shift_id,
            ShiftProductionData.workshop_id == workshop_id,
            ShiftProductionData.data_status != 'voided',
        )
        .first()
    )
    if spd:
        spd.input_weight = float(agg.total_input or 0)
        spd.output_weight = float(agg.total_output or 0)
        spd.scrap_weight = float(agg.total_scrap or 0)
        spd.data_source = 'mobile_coil_agg'
    else:
        spd = ShiftProductionData(
            business_date=business_date,
            shift_config_id=shift_id,
            workshop_id=workshop_id,
            input_weight=float(agg.total_input or 0),
            output_weight=float(agg.total_output or 0),
            scrap_weight=float(agg.total_scrap or 0),
            data_source='mobile_coil_agg',
            data_status='pending',
        )
        db.add(spd)
    db.commit()


def create_coil_entry(
    db: Session,
    *,
    payload: dict,
    current_user: User,
    ip_address: str | None = None,
) -> dict:
    assert_mobile_user_access(current_user)
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

    workshop_id = current_user.workshop_id
    if not workshop_id:
        scope = build_scope_summary(current_user)
        workshop_id = scope.workshop_id

    entry = WorkOrderEntry(
        work_order_id=wo.id,
        workshop_id=workshop_id or 0,
        machine_id=getattr(current_user, 'machine_id', None),
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
        entry_type='mobile_coil',
    )
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
        'business_date': entry.business_date,
        'created_at': None,
    }
