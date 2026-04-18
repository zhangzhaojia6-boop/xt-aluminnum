from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MobileCurrentShiftOut(BaseModel):
    business_date: date
    shift_id: int | None = None
    shift_code: str | None = None
    shift_name: str | None = None
    workshop_id: int | None = None
    workshop_code: str | None = None
    workshop_name: str | None = None
    workshop_type: str | None = None
    machine_id: int | None = None
    machine_code: str | None = None
    machine_name: str | None = None
    is_machine_bound: bool = False
    machine_custom_fields: list[dict] = Field(default_factory=list)
    team_id: int | None = None
    team_name: str | None = None
    leader_name: str
    report_id: int | None = None
    report_status: str = 'unreported'
    entry_channel: str = 'web_debug'
    dingtalk_ready: bool = False
    dingtalk_hint: str | None = None
    ownership_note: str | None = None
    active_reminders: list[dict] = Field(default_factory=list)
    attendance_confirmation_id: int | None = None
    attendance_machine_id: int | None = None
    attendance_machine_name: str | None = None
    attendance_status: str = 'not_started'
    attendance_exception_count: int = 0
    attendance_pending_count: int = 0
    can_submit: bool = False


class MobileReportPayload(BaseModel):
    business_date: date
    shift_id: int = Field(gt=0)
    attendance_count: int | None = Field(default=None, ge=0)
    input_weight: float | None = Field(default=None, ge=0)
    output_weight: float | None = Field(default=None, ge=0)
    scrap_weight: float | None = Field(default=None, ge=0)
    storage_prepared: float | None = Field(default=None, ge=0)
    storage_finished: float | None = Field(default=None, ge=0)
    shipment_weight: float | None = Field(default=None, ge=0)
    contract_received: float | None = Field(default=None, ge=0)
    electricity_daily: float | None = Field(default=None, ge=0)
    gas_daily: float | None = Field(default=None, ge=0)
    has_exception: bool = False
    exception_type: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=1000)
    optional_photo_url: str | None = Field(default=None, max_length=512)
    override_reason: str | None = Field(default=None, max_length=2000)


class MobileShiftReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    business_date: date
    shift_id: int
    shift_code: str | None = None
    shift_name: str | None = None
    workshop_id: int
    workshop_name: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    leader_name: str | None = None
    owner_user_id: int | None = None
    submitted_by_user_id: int | None = None
    last_action_by_user_id: int | None = None
    report_status: str
    attendance_count: int | None = None
    input_weight: float | None = None
    output_weight: float | None = None
    scrap_weight: float | None = None
    storage_prepared: float | None = None
    storage_finished: float | None = None
    shipment_weight: float | None = None
    contract_received: float | None = None
    electricity_daily: float | None = None
    gas_daily: float | None = None
    has_exception: bool = False
    exception_type: str | None = None
    note: str | None = None
    optional_photo_url: str | None = None
    photo_file_path: str | None = None
    photo_file_name: str | None = None
    photo_file_url: str | None = None
    photo_uploaded_at: datetime | None = None
    linked_production_data_id: int | None = None
    returned_reason: str | None = None
    active_reminders: list[dict] = Field(default_factory=list)
    monthly_output: float | None = None
    monthly_electricity: float | None = None
    monthly_gas: float | None = None
    monthly_yield_rate: float | None = None
    target_value: float | None = None
    compare_value: float | None = None
    energy_per_ton: float | None = None
    submitted_at: datetime | None = None
    last_saved_at: datetime | None = None
    updated_at: datetime | None = None


class MobileShiftReportHistoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_date: date
    shift_id: int
    shift_code: str | None = None
    shift_name: str | None = None
    workshop_name: str | None = None
    team_name: str | None = None
    report_status: str
    output_weight: float | None = None
    electricity_daily: float | None = None
    gas_daily: float | None = None
    has_exception: bool = False
    exception_type: str | None = None
    photo_file_name: str | None = None
    submitted_at: datetime | None = None
    last_saved_at: datetime | None = None
    returned_reason: str | None = None


class MobileReportHistoryResponse(BaseModel):
    items: list[MobileShiftReportHistoryItemOut]
    total: int


class MobileReminderActionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class MobileReminderRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_date: date
    shift_config_id: int
    workshop_id: int
    team_id: int | None = None
    leader_user_id: int | None = None
    reminder_type: str
    reminder_status: str
    reminder_channel: str
    reminder_count: int
    last_reminded_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: int | None = None
    closed_at: datetime | None = None
    closed_by: int | None = None
    note: str | None = None


class MobilePhotoUploadResponse(BaseModel):
    report_id: int
    photo_file_name: str
    photo_file_path: str
    photo_file_url: str
    uploaded_at: datetime


class MobileBootstrapOut(BaseModel):
    entry_mode: str
    data_entry_mode: str = 'manual_only'
    scan_assist_enabled: bool = False
    mes_display_enabled: bool = False
    phase_notice: str | None = None
    dingtalk_enabled: bool
    user_has_dingtalk_binding: bool
    current_identity_source: str
    current_scope_summary: dict
    is_machine_bound: bool = False
    machine_id: int | None = None
    machine_code: str | None = None
    machine_name: str | None = None
    workshop_id: int | None = None
    workshop_name: str | None = None
