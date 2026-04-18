from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.imports import ImportSummary


class ProductionImportResponse(BaseModel):
    batch_id: int
    batch_no: str
    import_type: str
    summary: ImportSummary


class ShiftProductionDataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_date: date
    shift_config_id: int
    shift_code: str | None = None
    shift_name: str | None = None
    workshop_id: int
    workshop_code: str | None = None
    workshop_name: str | None = None
    team_id: int | None = None
    team_code: str | None = None
    team_name: str | None = None
    equipment_id: int | None = None
    equipment_code: str | None = None
    equipment_name: str | None = None
    input_weight: float | None = None
    output_weight: float | None = None
    qualified_weight: float | None = None
    scrap_weight: float | None = None
    planned_headcount: int | None = None
    actual_headcount: int | None = None
    downtime_minutes: int
    downtime_reason: str | None = None
    issue_count: int
    electricity_kwh: float | None = None
    data_source: str
    import_batch_id: int | None = None
    data_status: str
    version_no: int
    superseded_by_id: int | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    confirmed_by: int | None = None
    confirmed_at: datetime | None = None
    rejected_by: int | None = None
    rejected_at: datetime | None = None
    rejected_reason: str | None = None
    voided_by: int | None = None
    voided_at: datetime | None = None
    voided_reason: str | None = None
    published_by: int | None = None
    published_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductionExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    production_data_id: int | None = None
    business_date: date
    workshop_id: int
    workshop_name: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    equipment_id: int | None = None
    equipment_name: str | None = None
    shift_config_id: int | None = None
    shift_code: str | None = None
    exception_type: str
    exception_desc: str
    severity: str
    status: str
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class ShiftProductionDataDetailResponse(BaseModel):
    item: ShiftProductionDataOut
    exceptions: list[ProductionExceptionOut]
    audit_trails: list[dict] = []


class ShiftDataActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ShiftDataActionResponse(BaseModel):
    message: str
    item: ShiftProductionDataOut
