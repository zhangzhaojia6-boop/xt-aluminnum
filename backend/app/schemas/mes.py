from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MesImportRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_batch_id: int | None = None
    source_type: str
    business_date: date
    workshop_code: str | None = None
    shift_code: str | None = None
    metric_code: str
    metric_name: str | None = None
    metric_value: float | None = None
    unit: str | None = None
    source_row_no: int | None = None
    raw_payload: Any | None = None
    created_at: datetime


class MesImportSummary(BaseModel):
    batch_no: str
    total_rows: int
    success_rows: int
    failed_rows: int
    columns: list[str]


class MesImportResponse(BaseModel):
    batch_id: int
    batch_no: str
    import_type: str
    summary: MesImportSummary
