from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EnergyImportRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_batch_id: int | None = None
    business_date: date
    workshop_code: str | None = None
    shift_code: str | None = None
    energy_type: str
    energy_value: float | None = None
    unit: str | None = None
    source_row_no: int | None = None
    raw_payload: Any | None = None
    created_at: datetime


class EnergyImportSummary(BaseModel):
    batch_no: str
    total_rows: int
    success_rows: int
    failed_rows: int
    columns: list[str]


class EnergyImportResponse(BaseModel):
    batch_id: int
    batch_no: str
    import_type: str
    summary: EnergyImportSummary


class EnergySummaryOut(BaseModel):
    business_date: date
    workshop_id: int | None = None
    workshop_code: str | None = None
    shift_config_id: int | None = None
    shift_code: str | None = None
    electricity_value: float = 0.0
    gas_value: float = 0.0
    water_value: float = 0.0
    total_energy: float = 0.0
    output_weight: float = 0.0
    energy_per_ton: float | None = None
