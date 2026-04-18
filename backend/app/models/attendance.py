from datetime import date, datetime

from datetime import time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AttendanceSchedule(Base, TimestampMixin):
    __tablename__ = 'attendance_schedules'
    __table_args__ = (
        UniqueConstraint('employee_id', 'business_date', name='uq_schedule_emp_date'),
        Index(
            'ix_attendance_schedules_shift_lookup',
            'business_date',
            'workshop_id',
            'team_id',
            'shift_config_id',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id'), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_config_id: Mapped[int | None] = mapped_column(ForeignKey('shift_configs.id'), nullable=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id'), nullable=True)
    workshop_id: Mapped[int | None] = mapped_column(ForeignKey('workshops.id'), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default='import', nullable=False)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey('import_batches.id'), nullable=True)
    is_rest_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ClockRecord(Base, TimestampMixin):
    __tablename__ = 'clock_records'
    __table_args__ = (
        UniqueConstraint('dingtalk_record_id', name='uq_clock_dingtalk_record_id'),
        UniqueConstraint('employee_id', 'clock_datetime', 'clock_type', 'device_id', name='uq_clock_unique_key'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id'), nullable=True, index=True)
    employee_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dingtalk_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    clock_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    clock_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    dingtalk_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_id: Mapped[str] = mapped_column(String(64), default='', nullable=False)
    location_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default='import', nullable=False)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey('import_batches.id'), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class AttendanceClockRecord(Base, TimestampMixin):
    __tablename__ = 'attendance_clock_records'

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id'), nullable=True, index=True)
    clock_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    clock_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    dingtalk_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ShiftAttendanceConfirmation(Base, TimestampMixin):
    __tablename__ = 'shift_attendance_confirmations'
    __table_args__ = (
        UniqueConstraint('workshop_id', 'machine_id', 'shift_id', 'business_date', name='uq_shift_attendance_confirmation'),
        Index('ix_shift_attendance_confirmation_status_date', 'status', 'business_date'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey('workshops.id'), nullable=False, index=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey('equipment.id'), nullable=False, index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey('shift_configs.id'), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='draft', index=True)


class EmployeeAttendanceDetail(Base, TimestampMixin):
    __tablename__ = 'employee_attendance_details'
    __table_args__ = (
        UniqueConstraint('confirmation_id', 'employee_id', name='uq_employee_attendance_detail_confirmation_employee'),
        Index('ix_employee_attendance_detail_hr_status', 'hr_status'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    confirmation_id: Mapped[int] = mapped_column(
        ForeignKey('shift_attendance_confirmations.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id'), nullable=False, index=True)
    dingtalk_clock_in: Mapped[time | None] = mapped_column(Time(), nullable=True)
    dingtalk_clock_out: Mapped[time | None] = mapped_column(Time(), nullable=True)
    leader_status: Mapped[str] = mapped_column(String(32), nullable=False, default='present', index=True)
    late_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    hr_status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending', index=True)
    hr_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    hr_reviewed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    hr_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShiftSwap(Base, TimestampMixin):
    __tablename__ = 'shift_swaps'

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id'), nullable=False, index=True)
    swap_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    original_shift_id: Mapped[int | None] = mapped_column(ForeignKey('shift_configs.id'), nullable=True)
    new_shift_id: Mapped[int | None] = mapped_column(ForeignKey('shift_configs.id'), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default='pending', nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)


class AttendanceResult(Base, TimestampMixin):
    __tablename__ = 'attendance_results'
    __table_args__ = (UniqueConstraint('employee_id', 'business_date', name='uq_attendance_emp_date'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id'), nullable=False, index=True)
    employee_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    employee_name: Mapped[str] = mapped_column(String(64), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id'), nullable=True)
    workshop_id: Mapped[int | None] = mapped_column(ForeignKey('workshops.id'), nullable=True)
    auto_shift_config_id: Mapped[int | None] = mapped_column(ForeignKey('shift_configs.id'), nullable=True)
    shift_config_id: Mapped[int | None] = mapped_column(ForeignKey('shift_configs.id'), nullable=True)
    attendance_status: Mapped[str] = mapped_column(String(32), default='pending', nullable=False, index=True)
    check_in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    work_hours: Mapped[float | None] = mapped_column(nullable=True)
    data_status: Mapped[str] = mapped_column(String(16), default='auto', nullable=False, index=True)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(256), nullable=True)


class AttendanceException(Base, TimestampMixin):
    __tablename__ = 'attendance_exceptions'

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_result_id: Mapped[int | None] = mapped_column(ForeignKey('attendance_results.id'), nullable=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id'), nullable=False, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_config_id: Mapped[int | None] = mapped_column(ForeignKey('shift_configs.id'), nullable=True)
    exception_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exception_desc: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default='warning', nullable=False)
    status: Mapped[str] = mapped_column(String(16), default='open', nullable=False, index=True)
    resolve_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolve_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AttendanceProcessLog(Base):
    __tablename__ = 'attendance_process_logs'

    id: Mapped[int] = mapped_column(primary_key=True)
    process_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), default='manual', nullable=False)
    status: Mapped[str] = mapped_column(String(16), default='completed', nullable=False)
    message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
