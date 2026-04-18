from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.imports import ImportSummary


class AttendanceImportResponse(BaseModel):
    batch_id: int
    batch_no: str
    import_type: str
    summary: ImportSummary


class AttendanceScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_no: str
    employee_name: str
    business_date: date
    shift_config_id: int | None
    shift_code: str | None
    shift_name: str | None
    team_id: int | None
    workshop_id: int | None
    source: str
    import_batch_id: int | None


class ClockRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int | None
    employee_no: str
    employee_name: str | None
    dingtalk_user_id: str | None
    clock_datetime: datetime
    clock_type: str
    dingtalk_record_id: str | None
    device_id: str
    location_name: str | None
    source: str
    import_batch_id: int | None


class AttendanceProcessRequest(BaseModel):
    start_date: date
    end_date: date


class AttendanceProcessResponse(BaseModel):
    processed_dates: list[date]
    processed_results: int
    generated_exceptions: int


class AttendanceResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_no: str
    employee_name: str
    business_date: date
    team_id: int | None
    workshop_id: int | None
    auto_shift_config_id: int | None
    shift_config_id: int | None
    attendance_status: str
    check_in_time: datetime | None
    check_out_time: datetime | None
    late_minutes: int
    early_leave_minutes: int
    overtime_minutes: int
    data_status: str
    is_manual_override: bool
    override_reason: str | None
    override_by: int | None
    override_at: datetime | None
    remark: str | None


class AttendanceResultListResponse(BaseModel):
    summary: dict
    items: list[AttendanceResultOut]


class AttendanceExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attendance_result_id: int | None
    employee_id: int
    employee_no: str
    employee_name: str
    business_date: date
    shift_config_id: int | None
    exception_type: str
    exception_desc: str
    severity: str
    status: str
    resolve_action: str | None
    resolve_note: str | None
    resolved_by: int | None
    resolved_at: datetime | None


class ExceptionResolveRequest(BaseModel):
    action: str = Field(pattern='^(confirmed|corrected|ignored)$')
    note: str | None = None


class AttendanceResultOverrideRequest(BaseModel):
    attendance_status: str | None = None
    shift_config_id: int | None = None
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    late_minutes: int | None = None
    early_leave_minutes: int | None = None
    remark: str | None = None
    override_reason: str


class AttendanceDetailResponse(BaseModel):
    result: AttendanceResultOut
    schedules: list[AttendanceScheduleOut]
    clocks: list[ClockRecordOut]
    exceptions: list[AttendanceExceptionOut]


class AttendanceConfirmationDetailSubmit(BaseModel):
    employee_id: int
    leader_status: str
    override_reason: str | None = None
    notes: str | None = None


class AttendanceConfirmationSubmitRequest(BaseModel):
    machine_id: int
    shift_id: int
    business_date: date
    items: list[AttendanceConfirmationDetailSubmit]


class AttendanceConfirmationDetailOut(BaseModel):
    employee_id: int
    employee_no: str | None = None
    employee_name: str | None = None
    dingtalk_clock_in: str | None = None
    dingtalk_clock_out: str | None = None
    auto_status: str | None = None
    leader_status: str | None = None
    late_minutes: int = 0
    early_leave_minutes: int = 0
    override_reason: str | None = None
    notes: str | None = None
    hr_status: str = 'pending'
    is_anomaly: bool = False


class AttendanceConfirmationOut(BaseModel):
    id: int | None = None
    workshop_id: int | None = None
    workshop_name: str | None = None
    machine_id: int
    machine_name: str | None = None
    shift_id: int
    shift_name: str | None = None
    business_date: date
    headcount_expected: int = 0
    status: str = 'draft'
    confirmed_by: int | None = None
    confirmed_at: datetime | None = None
    items: list[AttendanceConfirmationDetailOut] = Field(default_factory=list)


class AttendanceAnomalyOut(BaseModel):
    detail_id: int | None = None
    business_date: date
    workshop_id: int | None = None
    workshop_name: str | None = None
    machine_id: int | None = None
    machine_name: str | None = None
    shift_id: int | None = None
    shift_name: str | None = None
    employee_id: int | None = None
    employee_no: str | None = None
    employee_name: str
    dingtalk_clock_in: str | None = None
    dingtalk_clock_out: str | None = None
    auto_status: str
    leader_status: str
    override_reason: str | None = None
    notes: str | None = None
    hr_status: str = 'pending'


class AttendanceAnomalyReviewRequest(BaseModel):
    hr_status: str
    note: str | None = None


class AttendanceSummaryOut(BaseModel):
    business_date: date
    pending_count: int = 0
    confirmed_count: int = 0
    hr_reviewed_count: int = 0
    items: list[dict] = Field(default_factory=list)
