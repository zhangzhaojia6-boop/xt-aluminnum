from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.attendance import (
    AttendanceException,
    AttendanceProcessLog,
    AttendanceResult,
    AttendanceSchedule,
    ClockRecord,
)
from app.models.master import Employee
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.audit_service import record_audit
from app.services.exception_service import replace_result_exceptions, resolve_exception
from app.services.shift_engine import (
    assign_shift,
    build_shift_window,
    calculate_early_leave_minutes,
    calculate_late_minutes,
    infer_shift,
)
from app.utils.date_utils import daterange


@dataclass(slots=True)
class ProcessSummary:
    processed_dates: list[date]
    processed_results: int
    generated_exceptions: int


def _day_start(target: date) -> datetime:
    return datetime.combine(target, time.min)


def _day_end(target: date) -> datetime:
    return datetime.combine(target, time.max)


def _match_schedule_for_clock(
    *,
    clock: ClockRecord,
    employee_id: int,
    schedule_map: dict[tuple[int, date], AttendanceSchedule],
    shift_map: dict[int, ShiftConfig],
) -> tuple[AttendanceSchedule, ShiftConfig] | None:
    clock_dt = clock.clock_datetime.replace(tzinfo=None) if clock.clock_datetime.tzinfo is not None else clock.clock_datetime
    for candidate_date in [clock.clock_datetime.date() - timedelta(days=1), clock.clock_datetime.date(), clock.clock_datetime.date() + timedelta(days=1)]:
        schedule = schedule_map.get((employee_id, candidate_date))
        if not schedule or not schedule.shift_config_id:
            continue
        shift = shift_map.get(schedule.shift_config_id)
        if not shift:
            continue
        window_start, window_end = build_shift_window(shift, candidate_date)
        if window_start <= clock_dt <= window_end:
            return schedule, shift
    return None


def _pick_shift_id(counter: Counter[int | None]) -> int | None:
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _pick_check_in_out(clocks: list[ClockRecord]) -> tuple[datetime | None, datetime | None]:
    if not clocks:
        return None, None

    sorted_clocks = sorted(clocks, key=lambda item: item.clock_datetime)
    in_records = [item for item in sorted_clocks if item.clock_type == 'in']
    out_records = [item for item in sorted_clocks if item.clock_type == 'out']

    check_in = in_records[0].clock_datetime if in_records else sorted_clocks[0].clock_datetime
    check_out = out_records[-1].clock_datetime if out_records else sorted_clocks[-1].clock_datetime

    if check_out and check_in and check_out < check_in:
        check_out = None

    return check_in, check_out


def _status_from_metrics(
    *,
    has_schedule: bool,
    check_in: datetime | None,
    check_out: datetime | None,
    clocks: list[ClockRecord],
    late_minutes: int,
    early_leave_minutes: int,
    shift: ShiftConfig | None,
) -> tuple[str, str]:
    if not clocks:
        return 'absent', 'pending_review' if has_schedule else 'auto'

    status = 'normal'
    if check_in is None or check_out is None:
        status = 'abnormal'
    elif shift is not None and (late_minutes > shift.late_tolerance_minutes or early_leave_minutes > shift.early_tolerance_minutes):
        status = 'abnormal'

    data_status = 'auto' if status == 'normal' and has_schedule else 'pending_review'
    return status, data_status


def list_schedules(db: Session, *, start_date: date | None, end_date: date | None, employee_id: int | None) -> list[dict]:
    query = db.query(AttendanceSchedule)
    if employee_id:
        query = query.filter(AttendanceSchedule.employee_id == employee_id)
    if start_date:
        query = query.filter(AttendanceSchedule.business_date >= start_date)
    if end_date:
        query = query.filter(AttendanceSchedule.business_date <= end_date)
    schedules = query.order_by(AttendanceSchedule.business_date.desc(), AttendanceSchedule.id.desc()).limit(500).all()

    employee_ids = [item.employee_id for item in schedules]
    shift_ids = [item.shift_config_id for item in schedules if item.shift_config_id]
    employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).all() if employee_ids else []
    shifts = db.query(ShiftConfig).filter(ShiftConfig.id.in_(shift_ids)).all() if shift_ids else []
    employee_map = {item.id: item for item in employees}
    shift_map = {item.id: item for item in shifts}

    return [
        {
            'id': item.id,
            'employee_id': item.employee_id,
            'employee_no': employee_map.get(item.employee_id).employee_no if employee_map.get(item.employee_id) else '',
            'employee_name': employee_map.get(item.employee_id).name if employee_map.get(item.employee_id) else '',
            'business_date': item.business_date,
            'shift_config_id': item.shift_config_id,
            'shift_code': shift_map.get(item.shift_config_id).code if item.shift_config_id and shift_map.get(item.shift_config_id) else None,
            'shift_name': shift_map.get(item.shift_config_id).name if item.shift_config_id and shift_map.get(item.shift_config_id) else None,
            'team_id': item.team_id,
            'workshop_id': item.workshop_id,
            'source': item.source,
            'import_batch_id': item.import_batch_id,
        }
        for item in schedules
    ]


def list_clocks(
    db: Session,
    *,
    start_date: date | None,
    end_date: date | None,
    employee_id: int | None,
) -> list[dict]:
    query = db.query(ClockRecord)
    if employee_id:
        query = query.filter(ClockRecord.employee_id == employee_id)
    if start_date:
        query = query.filter(ClockRecord.clock_datetime >= _day_start(start_date))
    if end_date:
        query = query.filter(ClockRecord.clock_datetime <= _day_end(end_date))

    records = query.order_by(ClockRecord.clock_datetime.desc(), ClockRecord.id.desc()).limit(1000).all()
    employee_ids = [item.employee_id for item in records if item.employee_id]
    employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).all() if employee_ids else []
    employee_map = {item.id: item for item in employees}

    return [
        {
            'id': item.id,
            'employee_id': item.employee_id,
            'employee_no': item.employee_no,
            'employee_name': employee_map.get(item.employee_id).name if item.employee_id and employee_map.get(item.employee_id) else None,
            'dingtalk_user_id': item.dingtalk_user_id,
            'clock_datetime': item.clock_datetime,
            'clock_type': item.clock_type,
            'dingtalk_record_id': item.dingtalk_record_id,
            'device_id': item.device_id,
            'location_name': item.location_name,
            'source': item.source,
            'import_batch_id': item.import_batch_id,
        }
        for item in records
    ]


def process_attendance(db: Session, *, start_date: date, end_date: date, operator: User) -> ProcessSummary:
    shifts = db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).order_by(ShiftConfig.sort_order.asc()).all()
    shift_map = {item.id: item for item in shifts}

    schedules = (
        db.query(AttendanceSchedule)
        .filter(
            AttendanceSchedule.business_date >= start_date,
            AttendanceSchedule.business_date <= end_date,
        )
        .all()
    )
    schedule_map = {(item.employee_id, item.business_date): item for item in schedules}

    clocks = (
        db.query(ClockRecord)
        .filter(
            ClockRecord.clock_datetime >= _day_start(start_date - timedelta(days=1)),
            ClockRecord.clock_datetime <= _day_end(end_date + timedelta(days=1)),
        )
        .order_by(ClockRecord.clock_datetime.asc())
        .all()
    )

    employees = db.query(Employee).filter(Employee.is_active.is_(True)).all()
    employee_map = {item.id: item for item in employees}

    grouped_clocks: dict[tuple[int, date], list[ClockRecord]] = defaultdict(list)
    grouped_inferred_shift: dict[tuple[int, date], Counter[int | None]] = defaultdict(Counter)

    for clock in clocks:
        if not clock.employee_id:
            continue

        schedule_match = _match_schedule_for_clock(
            clock=clock,
            employee_id=clock.employee_id,
            schedule_map=schedule_map,
            shift_map=shift_map,
        )

        if schedule_match:
            schedule, shift = schedule_match
            key = (clock.employee_id, schedule.business_date)
            grouped_clocks[key].append(clock)
            grouped_inferred_shift[key][shift.id] += 1
            continue

        inferred = infer_shift(clock.clock_datetime, shifts)
        key = (clock.employee_id, inferred.business_date)
        grouped_clocks[key].append(clock)
        grouped_inferred_shift[key][inferred.shift_config_id] += 1

    all_keys = set(grouped_clocks.keys()) | set(schedule_map.keys())
    all_keys = {key for key in all_keys if start_date <= key[1] <= end_date}

    processed_results = 0
    generated_exceptions = 0

    for employee_id, business_date in sorted(all_keys, key=lambda item: (item[1], item[0])):
        employee = employee_map.get(employee_id)
        if not employee:
            continue

        schedule = schedule_map.get((employee_id, business_date))
        schedule_shift = shift_map.get(schedule.shift_config_id) if schedule and schedule.shift_config_id else None
        clocks_for_day = grouped_clocks.get((employee_id, business_date), [])

        if schedule_shift:
            auto_shift_id = schedule_shift.id
        else:
            auto_shift_id = _pick_shift_id(grouped_inferred_shift.get((employee_id, business_date), Counter()))

        shift_id = schedule_shift.id if schedule_shift else auto_shift_id
        shift = shift_map.get(shift_id) if shift_id else None

        if not shift and clocks_for_day and shifts:
            inferred = assign_shift(clocks_for_day[0].clock_datetime, shifts)
            shift_id = inferred.shift_config_id
            auto_shift_id = inferred.auto_shift_config_id
            shift = shift_map.get(shift_id) if shift_id else None

        check_in, check_out = _pick_check_in_out(clocks_for_day)

        late_minutes = calculate_late_minutes(check_in, shift, business_date) if shift else 0
        early_leave_minutes = calculate_early_leave_minutes(check_out, shift, business_date) if shift else 0

        attendance_status, data_status = _status_from_metrics(
            has_schedule=schedule is not None,
            check_in=check_in,
            check_out=check_out,
            clocks=clocks_for_day,
            late_minutes=late_minutes,
            early_leave_minutes=early_leave_minutes,
            shift=shift,
        )

        result = (
            db.query(AttendanceResult)
            .filter(
                AttendanceResult.employee_id == employee_id,
                AttendanceResult.business_date == business_date,
            )
            .first()
        )

        if result is None:
            result = AttendanceResult(
                employee_id=employee.id,
                employee_no=employee.employee_no,
                employee_name=employee.name,
                business_date=business_date,
            )
            db.add(result)
            db.flush()

        if result.is_manual_override:
            continue

        result.team_id = schedule.team_id if schedule and schedule.team_id else employee.team_id
        result.workshop_id = schedule.workshop_id if schedule and schedule.workshop_id else employee.workshop_id
        result.auto_shift_config_id = auto_shift_id
        result.shift_config_id = shift_id
        result.attendance_status = attendance_status
        result.check_in_time = check_in
        result.check_out_time = check_out
        result.late_minutes = late_minutes
        result.early_leave_minutes = early_leave_minutes
        result.overtime_minutes = 0
        result.data_status = data_status
        result.remark = None

        db.flush()
        exceptions = replace_result_exceptions(
            db,
            result=result,
            has_schedule=schedule is not None,
            schedule_shift_config_id=schedule.shift_config_id if schedule else None,
            clocks=clocks_for_day,
        )

        processed_results += 1
        generated_exceptions += len(exceptions)

    for process_date in daterange(start_date, end_date):
        db.add(
            AttendanceProcessLog(
                process_date=process_date,
                trigger_type='manual',
                status='completed',
                message=f'processed by user {operator.id}',
                created_by=operator.id,
            )
        )

    db.flush()
    record_audit(
        db,
        user=operator,
        action='process_attendance',
        module='attendance',
        entity_type='attendance_results',
        detail={
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'processed_results': processed_results,
            'generated_exceptions': generated_exceptions,
        },
        auto_commit=False,
    )
    db.commit()

    return ProcessSummary(
        processed_dates=daterange(start_date, end_date),
        processed_results=processed_results,
        generated_exceptions=generated_exceptions,
    )


def list_results(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
    team_id: int | None,
) -> dict:
    query = db.query(AttendanceResult).filter(AttendanceResult.business_date == business_date)
    if workshop_id:
        query = query.filter(AttendanceResult.workshop_id == workshop_id)
    if team_id:
        query = query.filter(AttendanceResult.team_id == team_id)

    items = query.order_by(AttendanceResult.employee_no.asc()).all()
    total = len(items)
    normal = len([item for item in items if item.attendance_status == 'normal'])
    abnormal = len([item for item in items if item.attendance_status != 'normal'])
    pending = len([item for item in items if item.data_status == 'pending_review'])

    return {
        'summary': {
            'total': total,
            'normal': normal,
            'abnormal': abnormal,
            'pending_review': pending,
        },
        'items': items,
    }


def get_result_detail(db: Session, *, employee_id: int, business_date: date) -> tuple[AttendanceResult, list[dict], list[dict], list[dict]]:
    result = (
        db.query(AttendanceResult)
        .filter(
            AttendanceResult.employee_id == employee_id,
            AttendanceResult.business_date == business_date,
        )
        .first()
    )
    if not result:
        raise ValueError('attendance result not found')

    schedules = list_schedules(db, start_date=business_date, end_date=business_date, employee_id=employee_id)
    clocks = list_clocks(db, start_date=business_date - timedelta(days=1), end_date=business_date + timedelta(days=1), employee_id=employee_id)

    exceptions = (
        db.query(AttendanceException)
        .filter(
            AttendanceException.employee_id == employee_id,
            AttendanceException.business_date == business_date,
        )
        .order_by(AttendanceException.id.desc())
        .all()
    )

    exception_payloads = [
        {
            'id': item.id,
            'attendance_result_id': item.attendance_result_id,
            'employee_id': item.employee_id,
            'employee_no': result.employee_no,
            'employee_name': result.employee_name,
            'business_date': item.business_date,
            'shift_config_id': item.shift_config_id,
            'exception_type': item.exception_type,
            'exception_desc': item.exception_desc,
            'severity': item.severity,
            'status': item.status,
            'resolve_action': item.resolve_action,
            'resolve_note': item.resolve_note,
            'resolved_by': item.resolved_by,
            'resolved_at': item.resolved_at,
        }
        for item in exceptions
    ]

    return result, schedules, clocks, exception_payloads


def list_exceptions(
    db: Session,
    *,
    business_date: date,
    exception_type: str | None,
    status: str | None,
) -> list[dict]:
    query = db.query(AttendanceException).filter(AttendanceException.business_date == business_date)
    if exception_type:
        query = query.filter(AttendanceException.exception_type == exception_type)
    if status:
        query = query.filter(AttendanceException.status == status)

    exceptions = query.order_by(AttendanceException.id.desc()).all()
    employee_ids = [item.employee_id for item in exceptions]
    employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).all() if employee_ids else []
    employee_map = {item.id: item for item in employees}

    return [
        {
            'id': item.id,
            'attendance_result_id': item.attendance_result_id,
            'employee_id': item.employee_id,
            'employee_no': employee_map.get(item.employee_id).employee_no if employee_map.get(item.employee_id) else '',
            'employee_name': employee_map.get(item.employee_id).name if employee_map.get(item.employee_id) else '',
            'business_date': item.business_date,
            'shift_config_id': item.shift_config_id,
            'exception_type': item.exception_type,
            'exception_desc': item.exception_desc,
            'severity': item.severity,
            'status': item.status,
            'resolve_action': item.resolve_action,
            'resolve_note': item.resolve_note,
            'resolved_by': item.resolved_by,
            'resolved_at': item.resolved_at,
        }
        for item in exceptions
    ]


def resolve_attendance_exception(
    db: Session,
    *,
    exception_id: int,
    action: str,
    note: str | None,
    operator: User,
) -> AttendanceException:
    exception = db.get(AttendanceException, exception_id)
    if not exception:
        raise ValueError('attendance exception not found')

    resolve_exception(db, exception=exception, action=action, note=note, user_id=operator.id)

    record_audit(
        db,
        user=operator,
        action='resolve_exception',
        module='attendance',
        entity_type='attendance_exceptions',
        entity_id=exception.id,
        detail={'action': action, 'note': note},
        auto_commit=False,
    )
    db.commit()
    db.refresh(exception)
    return exception


def override_attendance_result(
    db: Session,
    *,
    result_id: int,
    payload: dict,
    operator: User,
) -> AttendanceResult:
    result = db.get(AttendanceResult, result_id)
    if not result:
        raise ValueError('attendance result not found')

    old_value = {
        'attendance_status': result.attendance_status,
        'shift_config_id': result.shift_config_id,
        'check_in_time': result.check_in_time.isoformat() if result.check_in_time else None,
        'check_out_time': result.check_out_time.isoformat() if result.check_out_time else None,
        'late_minutes': result.late_minutes,
        'early_leave_minutes': result.early_leave_minutes,
        'data_status': result.data_status,
    }

    if payload.get('attendance_status'):
        result.attendance_status = payload['attendance_status']
    if payload.get('shift_config_id') is not None:
        result.shift_config_id = payload['shift_config_id']
    if payload.get('check_in_time') is not None:
        result.check_in_time = payload['check_in_time']
    if payload.get('check_out_time') is not None:
        result.check_out_time = payload['check_out_time']
    if payload.get('late_minutes') is not None:
        result.late_minutes = payload['late_minutes']
    if payload.get('early_leave_minutes') is not None:
        result.early_leave_minutes = payload['early_leave_minutes']
    if payload.get('remark') is not None:
        result.remark = payload['remark']

    result.is_manual_override = True
    result.override_reason = payload.get('override_reason')
    result.override_by = operator.id
    result.override_at = datetime.utcnow()
    result.data_status = 'manual'

    open_exceptions = (
        db.query(AttendanceException)
        .filter(
            AttendanceException.attendance_result_id == result.id,
            AttendanceException.status == 'open',
        )
        .all()
    )
    for item in open_exceptions:
        item.status = 'corrected'
        item.resolve_action = 'corrected'
        item.resolve_note = payload.get('override_reason')
        item.resolved_by = operator.id
        item.resolved_at = datetime.utcnow()

    db.flush()

    record_audit(
        db,
        user=operator,
        action='override_result',
        module='attendance',
        entity_type='attendance_results',
        entity_id=result.id,
        detail={
            'old_value': old_value,
            'new_value': {
                'attendance_status': result.attendance_status,
                'shift_config_id': result.shift_config_id,
                'check_in_time': result.check_in_time.isoformat() if result.check_in_time else None,
                'check_out_time': result.check_out_time.isoformat() if result.check_out_time else None,
                'late_minutes': result.late_minutes,
                'early_leave_minutes': result.early_leave_minutes,
                'data_status': result.data_status,
                'override_reason': result.override_reason,
            },
        },
        auto_commit=False,
    )

    db.commit()
    db.refresh(result)
    return result
