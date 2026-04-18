from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.event_bus import event_bus
from app.core.permissions import assert_mobile_user_access, assert_review_access
from app.core.workflow_events import attach_workflow_event, build_workflow_event
from app.models.attendance import AttendanceClockRecord, AttendanceSchedule, EmployeeAttendanceDetail, ShiftAttendanceConfirmation
from app.models.master import Employee, Equipment, Workshop
from app.models.production import WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.audit_service import record_audit

LOCAL_TZ = ZoneInfo(settings.DEFAULT_TIMEZONE)
LEADER_STATUSES = {'present', 'absent', 'late', 'early_leave', 'on_leave', 'business_trip'}
HR_STATUSES = {'pending', 'verified', 'resolved'}


def _http_error(detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


def _localize(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ)


def _shift_window_for_date(business_date: date, shift: ShiftConfig) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(business_date, shift.start_time, tzinfo=LOCAL_TZ)
    end_dt = datetime.combine(business_date, shift.end_time, tzinfo=LOCAL_TZ)
    if shift.business_day_offset:
        start_dt += timedelta(days=shift.business_day_offset)
        end_dt += timedelta(days=shift.business_day_offset)
    if shift.is_cross_day or shift.end_time <= shift.start_time:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def _resolve_confirmation_context(
    db: Session,
    *,
    machine_id: int,
    shift_id: int,
    business_date: date,
    current_user: User,
) -> dict:
    summary = assert_mobile_user_access(current_user)
    if current_user.workshop_id is None:
        raise _http_error('current user is not bound to a workshop', status.HTTP_403_FORBIDDEN)
    workshop = db.get(Workshop, current_user.workshop_id)
    machine = db.get(Equipment, machine_id)
    shift = db.get(ShiftConfig, shift_id)
    if workshop is None or machine is None or shift is None:
        raise _http_error('attendance confirmation context is invalid', status.HTTP_404_NOT_FOUND)
    if machine.workshop_id != workshop.id and not summary.is_admin:
        raise _http_error('machine does not belong to current workshop', status.HTTP_403_FORBIDDEN)
    return {
        'workshop_id': workshop.id,
        'workshop_name': workshop.name,
        'team_id': current_user.team_id,
        'machine_id': machine.id,
        'machine_name': machine.name,
        'shift': shift,
        'business_date': business_date,
    }


def _load_roster_employees(
    db: Session,
    *,
    workshop_id: int,
    team_id: int | None,
    shift_id: int,
    business_date: date,
) -> list[Employee]:
    query = (
        db.query(Employee)
        .join(AttendanceSchedule, AttendanceSchedule.employee_id == Employee.id)
        .filter(
            Employee.is_active.is_(True),
            AttendanceSchedule.business_date == business_date,
            AttendanceSchedule.workshop_id == workshop_id,
            AttendanceSchedule.shift_config_id == shift_id,
        )
    )
    if team_id is not None:
        query = query.filter(
            or_(
                AttendanceSchedule.team_id == team_id,
                AttendanceSchedule.team_id.is_(None),
                Employee.team_id == team_id,
            )
        )
    return query.order_by(Employee.employee_no.asc(), Employee.id.asc()).all()


def _load_dingtalk_clock_map(
    db: Session,
    *,
    employee_ids: list[int],
    start_dt: datetime,
    end_dt: datetime,
) -> dict[int, dict]:
    if not employee_ids:
        return {}
    rows = (
        db.query(AttendanceClockRecord)
        .filter(
            AttendanceClockRecord.employee_id.in_(employee_ids),
            AttendanceClockRecord.clock_time >= start_dt.astimezone(UTC),
            AttendanceClockRecord.clock_time <= end_dt.astimezone(UTC),
        )
        .order_by(AttendanceClockRecord.clock_time.asc(), AttendanceClockRecord.id.asc())
        .all()
    )
    payload: dict[int, dict] = {}
    for row in rows:
        bucket = payload.setdefault(row.employee_id, {'clock_in': None, 'clock_out': None})
        clock_local = _localize(row.clock_time).time().replace(tzinfo=None)
        if row.clock_type == 'in':
            if bucket['clock_in'] is None or clock_local < bucket['clock_in']:
                bucket['clock_in'] = clock_local
        elif row.clock_type == 'out':
            if bucket['clock_out'] is None or clock_local > bucket['clock_out']:
                bucket['clock_out'] = clock_local
    return payload


def _load_existing_confirmation(
    db: Session,
    *,
    workshop_id: int,
    machine_id: int,
    shift_id: int,
    business_date: date,
) -> ShiftAttendanceConfirmation | None:
    return (
        db.query(ShiftAttendanceConfirmation)
        .filter(
            ShiftAttendanceConfirmation.workshop_id == workshop_id,
            ShiftAttendanceConfirmation.machine_id == machine_id,
            ShiftAttendanceConfirmation.shift_id == shift_id,
            ShiftAttendanceConfirmation.business_date == business_date,
        )
        .first()
    )


def _detect_auto_status(
    *,
    shift: ShiftConfig,
    business_date: date,
    clock_in: time | None,
    clock_out: time | None,
) -> dict:
    if clock_in is None:
        return {'status': 'absent', 'late_minutes': 0, 'early_leave_minutes': 0}

    start_dt, end_dt = _shift_window_for_date(business_date, shift)
    start_limit = (start_dt + timedelta(minutes=15)).time().replace(tzinfo=None)
    end_limit = (end_dt - timedelta(minutes=15)).time().replace(tzinfo=None)

    if clock_in > start_limit:
        late_minutes = int(
            (
                datetime.combine(business_date, clock_in, tzinfo=LOCAL_TZ)
                - datetime.combine(business_date, shift.start_time, tzinfo=LOCAL_TZ)
            ).total_seconds()
            // 60
        )
        return {'status': 'late', 'late_minutes': max(late_minutes, 0), 'early_leave_minutes': 0}

    if clock_out is not None and clock_out < end_limit:
        early_leave_minutes = int(
            (
                datetime.combine(business_date, shift.end_time, tzinfo=LOCAL_TZ)
                - datetime.combine(business_date, clock_out, tzinfo=LOCAL_TZ)
            ).total_seconds()
            // 60
        )
        return {'status': 'early_leave', 'late_minutes': 0, 'early_leave_minutes': max(early_leave_minutes, 0)}

    return {'status': 'present', 'late_minutes': 0, 'early_leave_minutes': 0}


def calculate_auto_status(
    *,
    shift: ShiftConfig,
    business_date: date,
    clock_in: time | None,
    clock_out: time | None,
) -> dict:
    return _detect_auto_status(
        shift=shift,
        business_date=business_date,
        clock_in=clock_in,
        clock_out=clock_out,
    )


def _serialize_time(value: time | None) -> str | None:
    return value.isoformat() if value is not None else None


def _build_confirmation_payload(
    db: Session,
    *,
    confirmation: ShiftAttendanceConfirmation | None,
    context: dict,
    employees: list[Employee],
    clock_map: dict[int, dict],
) -> dict:
    shift: ShiftConfig = context['shift']

    persisted_details: dict[int, EmployeeAttendanceDetail] = {}
    if confirmation is not None:
        details = (
            db.query(EmployeeAttendanceDetail)
            .filter(EmployeeAttendanceDetail.confirmation_id == confirmation.id)
            .order_by(EmployeeAttendanceDetail.id.asc())
            .all()
        )
        persisted_details = {item.employee_id: item for item in details}

    items = []
    for employee in employees:
        clock_payload = clock_map.get(employee.id, {'clock_in': None, 'clock_out': None})
        detail = persisted_details.get(employee.id)
        auto = _detect_auto_status(
            shift=shift,
            business_date=context['business_date'],
            clock_in=detail.dingtalk_clock_in if detail else clock_payload.get('clock_in'),
            clock_out=detail.dingtalk_clock_out if detail else clock_payload.get('clock_out'),
        )
        items.append(
            {
                'employee_id': employee.id,
                'employee_no': employee.employee_no,
                'employee_name': employee.name,
                'dingtalk_clock_in': _serialize_time(detail.dingtalk_clock_in if detail else clock_payload.get('clock_in')),
                'dingtalk_clock_out': _serialize_time(detail.dingtalk_clock_out if detail else clock_payload.get('clock_out')),
                'auto_status': auto['status'],
                'leader_status': detail.leader_status if detail else auto['status'],
                'late_minutes': detail.late_minutes if detail else auto['late_minutes'],
                'early_leave_minutes': detail.early_leave_minutes if detail else auto['early_leave_minutes'],
                'override_reason': detail.override_reason if detail else None,
                'notes': detail.notes if detail else None,
                'hr_status': detail.hr_status if detail else 'pending',
                'is_anomaly': (detail.leader_status if detail else auto['status']) != auto['status'],
            }
        )

    return {
        'id': confirmation.id if confirmation else None,
        'workshop_id': context['workshop_id'],
        'workshop_name': context['workshop_name'],
        'machine_id': context['machine_id'],
        'machine_name': context['machine_name'],
        'shift_id': shift.id,
        'shift_name': shift.name,
        'business_date': context['business_date'],
        'headcount_expected': len(employees),
        'status': confirmation.status if confirmation else 'draft',
        'confirmed_by': confirmation.confirmed_by if confirmation else None,
        'confirmed_at': confirmation.confirmed_at if confirmation else None,
        'items': items,
    }


def build_draft(
    db: Session,
    *,
    machine_id: int,
    shift_id: int,
    business_date: date,
    current_user: User,
) -> dict:
    context = _resolve_confirmation_context(
        db,
        machine_id=machine_id,
        shift_id=shift_id,
        business_date=business_date,
        current_user=current_user,
    )
    context.setdefault('business_date', business_date)
    employees = _load_roster_employees(
        db,
        workshop_id=context['workshop_id'],
        team_id=context['team_id'],
        shift_id=shift_id,
        business_date=business_date,
    )
    start_dt, end_dt = _shift_window_for_date(business_date, context['shift'])
    clock_map = _load_dingtalk_clock_map(
        db,
        employee_ids=[item.id for item in employees],
        start_dt=start_dt,
        end_dt=end_dt,
    )
    confirmation = _load_existing_confirmation(
        db,
        workshop_id=context['workshop_id'],
        machine_id=machine_id,
        shift_id=shift_id,
        business_date=business_date,
    )
    return _build_confirmation_payload(
        db,
        confirmation=confirmation,
        context=context,
        employees=employees,
        clock_map=clock_map,
    )


def detect_anomalies(items: list[dict]) -> list[dict]:
    return [item for item in items if item.get('leader_status') != item.get('auto_status')]


def _load_anomaly_maps(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None = None,
) -> tuple[dict[tuple[int, int, int], int], dict[tuple[int, int], int]]:
    query = (
        db.query(EmployeeAttendanceDetail, ShiftAttendanceConfirmation, ShiftConfig)
        .join(ShiftAttendanceConfirmation, ShiftAttendanceConfirmation.id == EmployeeAttendanceDetail.confirmation_id)
        .join(ShiftConfig, ShiftConfig.id == ShiftAttendanceConfirmation.shift_id)
        .filter(ShiftAttendanceConfirmation.business_date == business_date)
    )
    if workshop_id is not None:
        query = query.filter(ShiftAttendanceConfirmation.workshop_id == workshop_id)

    by_cell: dict[tuple[int, int, int], int] = {}
    by_shift: dict[tuple[int, int], int] = {}
    for detail, confirmation, shift in query.all():
        auto = calculate_auto_status(
            shift=shift,
            business_date=confirmation.business_date,
            clock_in=detail.dingtalk_clock_in,
            clock_out=detail.dingtalk_clock_out,
        )
        if detail.leader_status == auto['status']:
            continue
        cell_key = (confirmation.workshop_id, confirmation.machine_id, confirmation.shift_id)
        shift_key = (confirmation.workshop_id, confirmation.shift_id)
        by_cell[cell_key] = int(by_cell.get(cell_key, 0)) + 1
        by_shift[shift_key] = int(by_shift.get(shift_key, 0)) + 1
    return by_cell, by_shift


def _build_attendance_event_payload(payload: dict, *, actor: User | None = None) -> dict:
    anomalies = detect_anomalies(payload['items'])
    base_payload = {
        'workshop_id': payload['workshop_id'],
        'team_id': payload.get('team_id'),
        'machine_id': payload['machine_id'],
        'shift_id': payload['shift_id'],
        'business_date': payload['business_date'].isoformat() if isinstance(payload['business_date'], date) else str(payload['business_date']),
        'workshop': payload['workshop_name'],
        'machine': payload['machine_name'],
        'shift': payload['shift_name'],
        'exception_count': len(anomalies),
    }
    workflow_event = build_workflow_event(
        event_type='attendance_confirmed',
        actor_role=getattr(actor, 'role', None),
        actor_id=getattr(actor, 'id', None),
        scope_type='machine' if payload.get('machine_id') else ('team' if payload.get('team_id') else 'workshop'),
        workshop_id=payload.get('workshop_id'),
        team_id=payload.get('team_id'),
        shift_id=payload.get('shift_id'),
        entity_type='attendance_confirmation',
        entity_id=payload.get('id'),
        status=payload.get('status'),
        payload={
            'business_date': base_payload['business_date'],
            'exception_count': len(anomalies),
        },
    )
    return attach_workflow_event(base_payload, workflow_event)


def submit_confirmation(
    db: Session,
    *,
    payload: dict,
    current_user: User,
) -> dict:
    business_date = payload['business_date']
    context = _resolve_confirmation_context(
        db,
        machine_id=int(payload['machine_id']),
        shift_id=int(payload['shift_id']),
        business_date=business_date,
        current_user=current_user,
    )
    employees = _load_roster_employees(
        db,
        workshop_id=context['workshop_id'],
        team_id=context['team_id'],
        shift_id=context['shift'].id,
        business_date=business_date,
    )
    employee_map = {item.id: item for item in employees}
    if not employee_map:
        raise _http_error('no roster employees found for this shift')

    submitted_ids = {int(item['employee_id']) for item in payload.get('items', [])}
    missing_ids = [item.id for item in employees if item.id not in submitted_ids]
    if missing_ids:
        raise _http_error('all employees must be confirmed before submit')

    confirmation = _load_existing_confirmation(
        db,
        workshop_id=context['workshop_id'],
        machine_id=context['machine_id'],
        shift_id=context['shift'].id,
        business_date=business_date,
    )
    if confirmation is None:
        confirmation = ShiftAttendanceConfirmation(
            workshop_id=context['workshop_id'],
            machine_id=context['machine_id'],
            shift_id=context['shift'].id,
            business_date=business_date,
        )
        db.add(confirmation)
        db.flush()
    elif confirmation.status in {'confirmed', 'hr_reviewed'} and current_user.role != 'admin':
        raise _http_error('attendance confirmation is already locked')

    start_dt, end_dt = _shift_window_for_date(business_date, context['shift'])
    clock_map = _load_dingtalk_clock_map(
        db,
        employee_ids=list(employee_map.keys()),
        start_dt=start_dt,
        end_dt=end_dt,
    )

    db.query(EmployeeAttendanceDetail).filter(EmployeeAttendanceDetail.confirmation_id == confirmation.id).delete()
    detail_payloads = []
    for item in payload.get('items', []):
        employee = employee_map.get(int(item['employee_id']))
        if employee is None:
            raise _http_error(f"employee {item['employee_id']} is not in current roster")
        leader_status = str(item.get('leader_status') or '').strip()
        if leader_status not in LEADER_STATUSES:
            raise _http_error(f'invalid leader_status: {leader_status}')
        clock_payload = clock_map.get(employee.id, {'clock_in': None, 'clock_out': None})
        auto = _detect_auto_status(
            shift=context['shift'],
            business_date=business_date,
            clock_in=clock_payload.get('clock_in'),
            clock_out=clock_payload.get('clock_out'),
        )
        override_reason = (item.get('override_reason') or '').strip() or None
        if leader_status != auto['status'] and not override_reason:
            raise _http_error(f'override_reason is required for employee {employee.employee_no}')
        late_minutes = auto['late_minutes'] if leader_status == 'late' else 0
        early_leave_minutes = auto['early_leave_minutes'] if leader_status == 'early_leave' else 0
        detail = EmployeeAttendanceDetail(
            confirmation_id=confirmation.id,
            employee_id=employee.id,
            dingtalk_clock_in=clock_payload.get('clock_in'),
            dingtalk_clock_out=clock_payload.get('clock_out'),
            leader_status=leader_status,
            late_minutes=late_minutes,
            early_leave_minutes=early_leave_minutes,
            override_reason=override_reason,
            notes=(item.get('notes') or '').strip() or None,
            hr_status='pending',
        )
        db.add(detail)
        detail_payloads.append(
            {
                'employee_id': employee.id,
                'employee_no': employee.employee_no,
                'employee_name': employee.name,
                'dingtalk_clock_in': _serialize_time(clock_payload.get('clock_in')),
                'dingtalk_clock_out': _serialize_time(clock_payload.get('clock_out')),
                'auto_status': auto['status'],
                'leader_status': leader_status,
                'late_minutes': late_minutes,
                'early_leave_minutes': early_leave_minutes,
                'override_reason': override_reason,
                'notes': detail.notes,
                'hr_status': 'pending',
                'is_anomaly': leader_status != auto['status'],
            }
        )

    confirmation.confirmed_by = current_user.id
    confirmation.confirmed_at = datetime.now(UTC)
    confirmation.status = 'confirmed'

    db.flush()
    record_audit(
        db,
        user=current_user,
        action='attendance_confirm',
        module='attendance',
        entity_type='shift_attendance_confirmations',
        entity_id=confirmation.id,
        detail={
            'machine_id': context['machine_id'],
            'shift_id': context['shift'].id,
            'business_date': business_date.isoformat(),
            'headcount_expected': len(employees),
        },
        auto_commit=False,
    )
    db.commit()
    db.refresh(confirmation)
    response = {
        'id': confirmation.id,
        'workshop_id': context['workshop_id'],
        'workshop_name': context['workshop_name'],
        'team_id': context['team_id'],
        'machine_id': context['machine_id'],
        'machine_name': context['machine_name'],
        'shift_id': context['shift'].id,
        'shift_name': context['shift'].name,
        'business_date': business_date,
        'headcount_expected': len(employees),
        'status': confirmation.status,
        'confirmed_by': confirmation.confirmed_by,
        'confirmed_at': confirmation.confirmed_at,
        'items': detail_payloads,
    }
    event_bus.publish('attendance_confirmed', _build_attendance_event_payload(response, actor=current_user))
    return response


def get_shift_confirmation_snapshot(
    db: Session,
    *,
    business_date: date,
    workshop_id: int,
    shift_id: int,
) -> dict:
    rows = (
        db.query(ShiftAttendanceConfirmation, Equipment)
        .join(Equipment, Equipment.id == ShiftAttendanceConfirmation.machine_id)
        .filter(
            ShiftAttendanceConfirmation.business_date == business_date,
            ShiftAttendanceConfirmation.workshop_id == workshop_id,
            ShiftAttendanceConfirmation.shift_id == shift_id,
        )
        .order_by(
            ShiftAttendanceConfirmation.confirmed_at.desc().nullslast(),
            ShiftAttendanceConfirmation.id.desc(),
        )
        .all()
    )
    if not rows:
        return {
            'attendance_confirmation_id': None,
            'attendance_machine_id': None,
            'attendance_machine_name': None,
            'attendance_status': 'not_started',
            'attendance_exception_count': 0,
            'attendance_pending_count': 1,
        }

    latest_confirmation, latest_machine = rows[0]
    _, shift_anomaly_map = _load_anomaly_maps(
        db,
        business_date=business_date,
        workshop_id=workshop_id,
    )
    exception_count = int(shift_anomaly_map.get((workshop_id, shift_id), 0))
    status_value = 'pending'
    if latest_confirmation.status in {'confirmed', 'hr_reviewed'} and exception_count == 0:
        status_value = 'confirmed'

    return {
        'attendance_confirmation_id': latest_confirmation.id,
        'attendance_machine_id': latest_confirmation.machine_id,
        'attendance_machine_name': latest_machine.name if latest_machine else None,
        'attendance_status': status_value,
        'attendance_exception_count': exception_count,
        'attendance_pending_count': 0 if latest_confirmation.status in {'confirmed', 'hr_reviewed'} else 1,
    }


def list_anomalies(
    db: Session,
    *,
    workshop_id: int | None,
    date_from: date,
    date_to: date,
    current_user: User,
) -> list[dict]:
    effective_workshop_id = workshop_id or current_user.workshop_id
    assert_review_access(current_user, workshop_id=effective_workshop_id, team_id=current_user.team_id)
    query = (
        db.query(EmployeeAttendanceDetail, ShiftAttendanceConfirmation, Employee, Workshop, Equipment, ShiftConfig)
        .join(ShiftAttendanceConfirmation, ShiftAttendanceConfirmation.id == EmployeeAttendanceDetail.confirmation_id)
        .join(Employee, Employee.id == EmployeeAttendanceDetail.employee_id)
        .join(Workshop, Workshop.id == ShiftAttendanceConfirmation.workshop_id)
        .join(Equipment, Equipment.id == ShiftAttendanceConfirmation.machine_id)
        .join(ShiftConfig, ShiftConfig.id == ShiftAttendanceConfirmation.shift_id)
        .filter(
            ShiftAttendanceConfirmation.business_date >= date_from,
            ShiftAttendanceConfirmation.business_date <= date_to,
        )
    )
    if workshop_id is not None:
        query = query.filter(ShiftAttendanceConfirmation.workshop_id == workshop_id)

    items = []
    for detail, confirmation, employee, workshop, machine, shift in query.all():
        auto = calculate_auto_status(
            shift=shift,
            business_date=confirmation.business_date,
            clock_in=detail.dingtalk_clock_in,
            clock_out=detail.dingtalk_clock_out,
        )
        if detail.leader_status == auto['status']:
            continue
        items.append(
            {
                'detail_id': detail.id,
                'business_date': confirmation.business_date,
                'workshop_id': confirmation.workshop_id,
                'workshop_name': workshop.name,
                'machine_id': confirmation.machine_id,
                'machine_name': machine.name,
                'shift_id': confirmation.shift_id,
                'shift_name': shift.name,
                'employee_id': employee.id,
                'employee_no': employee.employee_no,
                'employee_name': employee.name,
                'dingtalk_clock_in': _serialize_time(detail.dingtalk_clock_in),
                'dingtalk_clock_out': _serialize_time(detail.dingtalk_clock_out),
                'auto_status': auto['status'],
                'leader_status': detail.leader_status,
                'override_reason': detail.override_reason,
                'notes': detail.notes,
                'hr_status': detail.hr_status,
            }
        )
    items.sort(key=lambda item: (item['business_date'], item['workshop_name'], item['machine_name'], item['employee_no']), reverse=True)
    return items


def update_anomaly_review(
    db: Session,
    *,
    detail_id: int,
    hr_status: str,
    note: str | None,
    current_user: User,
) -> dict:
    detail = db.get(EmployeeAttendanceDetail, detail_id)
    if detail is None:
        raise _http_error('attendance anomaly not found', status.HTTP_404_NOT_FOUND)
    confirmation = db.get(ShiftAttendanceConfirmation, detail.confirmation_id)
    if confirmation is None:
        raise _http_error('attendance confirmation not found', status.HTTP_404_NOT_FOUND)
    assert_review_access(current_user, workshop_id=confirmation.workshop_id, team_id=current_user.team_id)
    if hr_status not in HR_STATUSES:
        raise _http_error(f'invalid hr_status: {hr_status}')

    detail.hr_status = hr_status
    detail.hr_review_note = (note or '').strip() or None
    detail.hr_reviewed_by = current_user.id
    detail.hr_reviewed_at = datetime.now(UTC)
    if hr_status in {'verified', 'resolved'}:
        confirmation.status = 'hr_reviewed'
    db.flush()
    record_audit(
        db,
        user=current_user,
        action='attendance_anomaly_review',
        module='attendance',
        entity_type='employee_attendance_details',
        entity_id=detail.id,
        detail={'hr_status': hr_status, 'note': detail.hr_review_note},
        auto_commit=False,
    )
    db.commit()
    return {'detail_id': detail.id, 'hr_status': detail.hr_status, 'note': detail.hr_review_note}


def build_summary(
    db: Session,
    *,
    business_date: date,
    current_user: User,
) -> dict:
    workshop_scope = None
    if current_user.role not in {'admin', 'manager', 'statistician', 'stat'} and current_user.workshop_id is not None:
        workshop_scope = current_user.workshop_id

    active_machine_query = (
        db.query(WorkOrderEntry.workshop_id, WorkOrderEntry.machine_id, WorkOrderEntry.shift_id)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.machine_id.is_not(None),
            WorkOrderEntry.shift_id.is_not(None),
        )
    )
    if workshop_scope is not None:
        active_machine_query = active_machine_query.filter(WorkOrderEntry.workshop_id == workshop_scope)
    active_machine_rows = active_machine_query.distinct().all()
    active_keys = {(row.workshop_id, row.machine_id, row.shift_id) for row in active_machine_rows}

    confirmation_query = (
        db.query(ShiftAttendanceConfirmation, Workshop, Equipment, ShiftConfig)
        .join(Workshop, Workshop.id == ShiftAttendanceConfirmation.workshop_id)
        .join(Equipment, Equipment.id == ShiftAttendanceConfirmation.machine_id)
        .join(ShiftConfig, ShiftConfig.id == ShiftAttendanceConfirmation.shift_id)
        .filter(ShiftAttendanceConfirmation.business_date == business_date)
    )
    if workshop_scope is not None:
        confirmation_query = confirmation_query.filter(ShiftAttendanceConfirmation.workshop_id == workshop_scope)
    confirmation_rows = confirmation_query.all()
    confirmation_map = {
        (row.workshop_id, row.machine_id, row.shift_id): (row, workshop, machine, shift)
        for row, workshop, machine, shift in confirmation_rows
    }
    active_keys.update(confirmation_map.keys())
    anomaly_by_cell, _ = _load_anomaly_maps(
        db,
        business_date=business_date,
        workshop_id=workshop_scope,
    )

    pending_count = 0
    confirmed_count = 0
    hr_reviewed_count = 0
    items = []
    for workshop_id, machine_id, shift_id in sorted(active_keys):
        joined = confirmation_map.get((workshop_id, machine_id, shift_id))
        row = joined[0] if joined else None
        workshop = joined[1] if joined else None
        machine = joined[2] if joined else None
        shift = joined[3] if joined else None
        exception_count = int(anomaly_by_cell.get((workshop_id, machine_id, shift_id), 0))
        status_value = row.status if row else 'draft'
        summary_status = 'confirmed' if row and row.status in {'confirmed', 'hr_reviewed'} and exception_count == 0 else 'pending'
        if row is None:
            summary_status = 'not_started'
        if status_value == 'hr_reviewed':
            hr_reviewed_count += 1
        elif status_value == 'confirmed':
            confirmed_count += 1
        else:
            pending_count += 1
        items.append(
            {
                'workshop_id': workshop_id,
                'workshop_name': workshop.name if workshop else None,
                'machine_id': machine_id,
                'machine_name': machine.name if machine else None,
                'shift_id': shift_id,
                'shift_name': shift.name if shift else None,
                'status': status_value,
                'summary_status': summary_status,
                'exception_count': exception_count,
            }
        )
    return {
        'business_date': business_date,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
        'hr_reviewed_count': hr_reviewed_count,
        'items': items,
    }
