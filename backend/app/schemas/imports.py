from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class DailyProductionMappingRowOut(BaseModel):
    row_index: int | None = None
    business_date: str | None = None
    source_unit: str | None = None
    workshop_label: str | None = None
    project_label: str | None = None
    daily_input_tons: float | None = None
    month_to_date_input_tons: float | None = None
    daily_output_tons: float | None = None
    month_to_date_output_tons: float | None = None
    daily_scrap_tons: float | None = None
    month_to_date_scrap_tons: float | None = None
    status: str
    expected_workshop_code: str | None = None
    expected_equipment_code: str | None = None
    workshop_id: int | None = None
    workshop_code: str | None = None
    workshop_name: str | None = None
    equipment_id: int | None = None
    equipment_code: str | None = None
    equipment_name: str | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)


class DailyProductionMappingPreviewOut(BaseModel):
    batch_id: int | None = None
    batch_no: str | None = None
    business_date: str | None = None
    source_unit: str | None = None
    total_rows: int
    ready_rows: int
    needs_equipment_mapping_rows: int
    unresolved_rows: int
    rows: list[DailyProductionMappingRowOut]
