from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PreviousStageOutputOut(BaseModel):
    workshop: str | None = None
    output_weight: float | None = None
    output_spec: str | None = None
    completed_at: datetime | None = None


class WorkOrderCreate(BaseModel):
    tracking_card_no: str = Field(min_length=1, max_length=64)
    alloy_grade: str | None = Field(default=None, max_length=64)
    contract_no: str | None = Field(default=None, max_length=64)
    customer_name: str | None = Field(default=None, max_length=128)
    contract_weight: float | None = Field(default=None, ge=0)


class WorkOrderUpdate(BaseModel):
    alloy_grade: str | None = Field(default=None, max_length=64)
    contract_no: str | None = Field(default=None, max_length=64)
    customer_name: str | None = Field(default=None, max_length=128)
    contract_weight: float | None = Field(default=None, ge=0)


class WorkOrderListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tracking_card_no: str
    process_route_code: str
    alloy_grade: str | None = None
    contract_no: str | None = None
    customer_name: str | None = None
    contract_weight: float | None = None
    current_station: str | None = None
    previous_stage_output: PreviousStageOutputOut | None = None
    overall_status: str
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class WorkOrderEntryCreate(BaseModel):
    workshop_id: int = Field(gt=0)
    ocr_submission_id: int | None = Field(default=None, gt=0)
    machine_id: int | None = Field(default=None, gt=0)
    shift_id: int | None = Field(default=None, gt=0)
    business_date: date
    on_machine_time: time | None = None
    off_machine_time: time | None = None
    input_weight: float | None = Field(default=None, ge=0)
    output_weight: float | None = Field(default=None, ge=0)
    input_spec: str | None = Field(default=None, max_length=64)
    output_spec: str | None = Field(default=None, max_length=64)
    material_state: str | None = Field(default=None, max_length=64)
    scrap_weight: float | None = Field(default=None, ge=0)
    spool_weight: float | None = Field(default=None, ge=0)
    operator_notes: str | None = Field(default=None, max_length=2000)
    verified_input_weight: float | None = Field(default=None, ge=0)
    verified_output_weight: float | None = Field(default=None, ge=0)
    qc_grade: str | None = Field(default=None, max_length=64)
    qc_notes: str | None = Field(default=None, max_length=2000)
    energy_kwh: float | None = Field(default=None, ge=0)
    gas_m3: float | None = Field(default=None, ge=0)
    extra_payload: dict[str, Any] | None = None
    qc_payload: dict[str, Any] | None = None
    entry_type: str = Field(default='in_progress', pattern='^(in_progress|completed)$')


class WorkOrderEntryUpdate(BaseModel):
    machine_id: int | None = Field(default=None, gt=0)
    shift_id: int | None = Field(default=None, gt=0)
    business_date: date | None = None
    on_machine_time: time | None = None
    off_machine_time: time | None = None
    input_weight: float | None = Field(default=None, ge=0)
    output_weight: float | None = Field(default=None, ge=0)
    input_spec: str | None = Field(default=None, max_length=64)
    output_spec: str | None = Field(default=None, max_length=64)
    material_state: str | None = Field(default=None, max_length=64)
    scrap_weight: float | None = Field(default=None, ge=0)
    spool_weight: float | None = Field(default=None, ge=0)
    operator_notes: str | None = Field(default=None, max_length=2000)
    verified_input_weight: float | None = Field(default=None, ge=0)
    verified_output_weight: float | None = Field(default=None, ge=0)
    qc_grade: str | None = Field(default=None, max_length=64)
    qc_notes: str | None = Field(default=None, max_length=2000)
    energy_kwh: float | None = Field(default=None, ge=0)
    gas_m3: float | None = Field(default=None, ge=0)
    extra_payload: dict[str, Any] | None = None
    qc_payload: dict[str, Any] | None = None
    entry_type: str | None = Field(default=None, pattern='^(in_progress|completed)$')
    override_reason: str | None = Field(default=None, max_length=2000)


class WorkOrderEntrySubmitRequest(BaseModel):
    override_reason: str | None = Field(default=None, max_length=2000)


class WorkOrderEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    workshop_id: int
    machine_id: int | None = None
    shift_id: int | None = None
    business_date: date
    on_machine_time: time | None = None
    off_machine_time: time | None = None
    input_weight: float | None = None
    output_weight: float | None = None
    input_spec: str | None = None
    output_spec: str | None = None
    material_state: str | None = None
    scrap_weight: float | None = None
    spool_weight: float | None = None
    operator_notes: str | None = None
    verified_input_weight: float | None = None
    verified_output_weight: float | None = None
    weigher_user_id: int | None = None
    weighed_at: datetime | None = None
    qc_grade: str | None = None
    qc_notes: str | None = None
    qc_user_id: int | None = None
    qc_at: datetime | None = None
    energy_kwh: float | None = None
    gas_m3: float | None = None
    extra_payload: dict[str, Any] = Field(default_factory=dict)
    qc_payload: dict[str, Any] = Field(default_factory=dict)
    yield_rate: float | None = None
    entry_type: str
    entry_status: str
    locked_fields: list[str] = Field(default_factory=list)
    submitted_at: datetime | None = None
    verified_at: datetime | None = None
    approved_at: datetime | None = None
    created_by: int | None = None
    created_by_user_id: int | None = None
    created_by_user_name: str | None = None
    created_at: datetime
    updated_at: datetime


class WorkOrderDetailOut(WorkOrderListItemOut):
    entries: list[WorkOrderEntryOut] = Field(default_factory=list)


class FieldAmendmentCreate(BaseModel):
    table_name: str = Field(pattern='^(work_orders|work_order_entries)$')
    record_id: int = Field(gt=0)
    field_name: str = Field(min_length=1, max_length=64)
    new_value: str | None = None
    reason: str = Field(min_length=1, max_length=2000)


class FieldAmendmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    table_name: str
    record_id: int
    field_name: str
    old_value: str | None = None
    new_value: str | None = None
    reason: str
    requested_by: int | None = None
    requested_at: datetime
    approved_by: int | None = None
    approved_at: datetime | None = None
    status: str
