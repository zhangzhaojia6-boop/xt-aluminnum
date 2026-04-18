from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_no: str
    import_type: str
    template_code: str | None = None
    mapping_template_code: str | None = None
    source_type: str | None = None
    file_name: str
    file_size: int | None = None
    file_path: str | None = None
    total_rows: int
    success_rows: int
    failed_rows: int
    skipped_rows: int
    status: str
    quality_status: str | None = None
    parsed_successfully: bool | None = None
    error_summary: str | None = None
    imported_by: int | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ImportRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    row_number: int
    raw_data: Any
    mapped_data: Any | None = None
    status: str
    error_msg: str | None = None
    created_at: datetime


class ImportSummary(BaseModel):
    batch_no: str
    total_rows: int
    success_rows: int
    failed_rows: int
    skipped_rows: int
    columns: list[str]


class ImportUploadResponse(BaseModel):
    batch: ImportBatchOut
    rows: list[ImportRowOut]
    summary: ImportSummary
