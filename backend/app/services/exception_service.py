from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.attendance import AttendanceException, AttendanceResult, ClockRecord
from app.models.production import ProductionException, ShiftProductionData


@dataclass(slots=True)
class ExceptionDraft:
    exception_type: str
    exception_desc: str
    severity: str = 'warning'


@dataclass(slots=True)
class ProductionExceptionDraft:
    exception_type: str
    exception_desc: str
    severity: str = 'warning'


def _has_duplicate_clock(clocks: list[ClockRecord]) -> bool:
    in_count = len([clock for clock in clocks if clock.clock_type == 'in'])
    out_count = len([clock for clock in clocks if clock.clock_type == 'out'])
    return in_count > 1 or out_count > 1


def detect_exceptions(
    *,
    result: AttendanceResult,
    has_schedule: bool,
    schedule_shift_config_id: int | None,
    clocks: list[ClockRecord],
) -> list[ExceptionDraft]:
    drafts: list[ExceptionDraft] = []

    if has_schedule and not clocks:
        drafts.append(ExceptionDraft('no_clock_with_schedule', 'Scheduled shift exists but no clock records found', 'error'))

    if not has_schedule:
        drafts.append(ExceptionDraft('no_schedule', 'No schedule found for this employee on this business date', 'warning'))

    if result.check_in_time is None and clocks:
        drafts.append(ExceptionDraft('missing_checkin', 'Missing check-in record', 'error'))

    if result.check_out_time is None and clocks:
        drafts.append(ExceptionDraft('missing_checkout', 'Missing check-out record', 'error'))

    if result.late_minutes > 0:
        drafts.append(ExceptionDraft('late', f'Late by {result.late_minutes} minutes', 'warning'))

    if result.early_leave_minutes > 0:
        drafts.append(ExceptionDraft('early_leave', f'Early leave by {result.early_leave_minutes} minutes', 'warning'))

    if has_schedule and schedule_shift_config_id and result.auto_shift_config_id and schedule_shift_config_id != result.auto_shift_config_id:
        drafts.append(ExceptionDraft('shift_mismatch', 'Inferred shift does not match scheduled shift', 'warning'))

    if _has_duplicate_clock(clocks):
        drafts.append(ExceptionDraft('duplicate_clock', 'Duplicate clock records detected in same business date', 'warning'))

    return drafts


def replace_result_exceptions(
    db: Session,
    *,
    result: AttendanceResult,
    has_schedule: bool,
    schedule_shift_config_id: int | None,
    clocks: list[ClockRecord],
) -> list[AttendanceException]:
    existing = (
        db.query(AttendanceException)
        .filter(
            AttendanceException.employee_id == result.employee_id,
            AttendanceException.business_date == result.business_date,
            AttendanceException.status.in_(['open', 'confirmed', 'corrected', 'ignored']),
        )
        .all()
    )

    for item in existing:
        db.delete(item)
    db.flush()

    drafts = detect_exceptions(
        result=result,
        has_schedule=has_schedule,
        schedule_shift_config_id=schedule_shift_config_id,
        clocks=clocks,
    )

    created: list[AttendanceException] = []
    for draft in drafts:
        entity = AttendanceException(
            attendance_result_id=result.id,
            employee_id=result.employee_id,
            business_date=result.business_date,
            shift_config_id=result.shift_config_id,
            exception_type=draft.exception_type,
            exception_desc=draft.exception_desc,
            severity=draft.severity,
            status='open',
            resolve_action=None,
            resolve_note=None,
            resolved_by=None,
            resolved_at=None,
        )
        db.add(entity)
        created.append(entity)

    db.flush()
    return created


def resolve_exception(
    db: Session,
    *,
    exception: AttendanceException,
    action: str,
    note: str | None,
    user_id: int,
) -> AttendanceException:
    exception.status = action
    exception.resolve_action = action
    exception.resolve_note = note
    exception.resolved_by = user_id
    exception.resolved_at = datetime.utcnow()
    db.flush()
    return exception


def detect_production_exceptions(
    *,
    data: ShiftProductionData,
    today: date,
) -> list[ProductionExceptionDraft]:
    drafts: list[ProductionExceptionDraft] = []

    required_values = [data.input_weight, data.output_weight, data.qualified_weight, data.scrap_weight]
    if any(value is None for value in required_values):
        drafts.append(
            ProductionExceptionDraft(
                'missing_data',
                'Missing one or more key production values (input/output/qualified/scrap)',
                'error',
            )
        )

    numeric_values = [value for value in required_values if value is not None]
    if any(float(value) < 0 for value in numeric_values):
        drafts.append(ProductionExceptionDraft('abnormal_value', 'Negative production value detected', 'error'))

    if data.input_weight is not None and data.output_weight is not None and float(data.output_weight) > float(data.input_weight):
        drafts.append(ProductionExceptionDraft('abnormal_value', 'Output weight is greater than input weight', 'warning'))
    if (
        data.qualified_weight is not None
        and data.output_weight is not None
        and float(data.qualified_weight) > float(data.output_weight)
    ):
        drafts.append(ProductionExceptionDraft('abnormal_value', 'Qualified weight is greater than output weight', 'warning'))
    if data.scrap_weight is not None and data.input_weight is not None and float(data.scrap_weight) > float(data.input_weight):
        drafts.append(ProductionExceptionDraft('abnormal_value', 'Scrap weight is greater than input weight', 'warning'))

    if (
        data.planned_headcount is not None
        and data.actual_headcount is not None
        and data.actual_headcount < data.planned_headcount
    ):
        drafts.append(
            ProductionExceptionDraft(
                'inconsistent_headcount',
                f'Actual headcount {data.actual_headcount} is less than planned {data.planned_headcount}',
                'warning',
            )
        )

    if data.business_date < today:
        drafts.append(ProductionExceptionDraft('late_report', 'Shift data was reported after business date', 'info'))

    return drafts


def replace_production_exceptions(
    db: Session,
    *,
    data: ShiftProductionData,
    today: date,
) -> list[ProductionException]:
    existing = (
        db.query(ProductionException)
        .filter(
            ProductionException.production_data_id == data.id,
            ProductionException.status.in_(['open', 'confirmed', 'ignored', 'corrected']),
        )
        .all()
    )
    for item in existing:
        db.delete(item)
    db.flush()

    drafts = detect_production_exceptions(data=data, today=today)
    created: list[ProductionException] = []

    for draft in drafts:
        entity = ProductionException(
            production_data_id=data.id,
            business_date=data.business_date,
            workshop_id=data.workshop_id,
            team_id=data.team_id,
            equipment_id=data.equipment_id,
            shift_config_id=data.shift_config_id,
            exception_type=draft.exception_type,
            exception_desc=draft.exception_desc,
            severity=draft.severity,
            status='open',
        )
        db.add(entity)
        created.append(entity)
    db.flush()
    return created


def create_duplicate_production_exception(
    db: Session,
    *,
    data: ShiftProductionData,
    message: str,
) -> ProductionException:
    entity = ProductionException(
        production_data_id=data.id,
        business_date=data.business_date,
        workshop_id=data.workshop_id,
        team_id=data.team_id,
        equipment_id=data.equipment_id,
        shift_config_id=data.shift_config_id,
        exception_type='duplicate_record',
        exception_desc=message,
        severity='warning',
        status='open',
    )
    db.add(entity)
    db.flush()
    return entity


def bulk_update_production_exception_status(
    db: Session,
    *,
    production_data_id: int,
    status: str,
    user_id: int,
) -> int:
    rows = (
        db.query(ProductionException)
        .filter(ProductionException.production_data_id == production_data_id, ProductionException.status == 'open')
        .all()
    )
    if not rows:
        return 0

    now = datetime.utcnow()
    for item in rows:
        item.status = status
        item.resolved_by = user_id
        item.resolved_at = now
    db.flush()
    return len(rows)
