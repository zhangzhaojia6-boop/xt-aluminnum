from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReconciliationGenerateRequest(BaseModel):
    business_date: date
    reconciliation_type: str | None = Field(
        default=None,
        pattern='^(attendance_vs_production|production_vs_mes|energy_vs_production|report_vs_source)$',
    )


class ReconciliationItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_date: date
    reconciliation_type: str
    source_a: str
    source_b: str
    dimension_key: str
    field_name: str
    source_a_value: str | None = None
    source_b_value: str | None = None
    diff_value: float | None = None
    status: str
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    resolve_note: str | None = None
    created_at: datetime
    updated_at: datetime


class ReconciliationActionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
