from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class QualityCheckRequest(BaseModel):
    business_date: date


class DataQualityIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_date: date
    issue_type: str
    source_type: str | None = None
    dimension_key: str | None = None
    field_name: str | None = None
    issue_level: str
    issue_desc: str
    status: str
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    resolve_note: str | None = None
    created_at: datetime
    updated_at: datetime


class QualityIssueActionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
