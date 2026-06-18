from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class MesExtendedSourceSummaryOut(BaseModel):
    key: str
    label: str
    row_count: int = 0
    status: str = 'empty'
    latest_business_date: date | None = None
    latest_seen_at: datetime | None = None


class MesExtendedSummaryOut(BaseModel):
    sources: list[MesExtendedSourceSummaryOut] = Field(default_factory=list)


class MesWorkshopProcessRecordOut(BaseModel):
    source_id: str
    batch_no: str | None = None
    customer_alias: str | None = None
    workshop_name: str | None = None
    process_name: str | None = None
    worker_name: str | None = None
    device_name: str | None = None
    input_weight_tons: float | None = None
    output_weight_tons: float | None = None
    yield_rate: float | None = None
    end_time: datetime | None = None
    business_date: date | None = None
    last_seen_from_mes_at: datetime | None = None


class MesStockRecordOut(BaseModel):
    source_id: str
    batch_no: str | None = None
    contract_no: str | None = None
    customer_alias: str | None = None
    net_weight_tons: float | None = None
    gross_weight_tons: float | None = None
    in_stock_date: datetime | None = None
    business_date: date | None = None
    status_name: str | None = None
    last_seen_from_mes_at: datetime | None = None


class MesMaterialRecordOut(BaseModel):
    source_id: str
    material_code: str | None = None
    workshop_name: str | None = None
    line_name: str | None = None
    position_name: str | None = None
    alloy_grade: str | None = None
    spec_display: str | None = None
    weight_tons: float | None = None
    production_date: datetime | None = None
    business_date: date | None = None
    status_name: str | None = None
    last_seen_from_mes_at: datetime | None = None


class MesYieldRecordOut(BaseModel):
    source_id: str
    batch_no: str | None = None
    contract_no: str | None = None
    customer_alias: str | None = None
    contract_total_weight_tons: float | None = None
    feeding_weight_tons: float | None = None
    in_stock_net_weight_tons: float | None = None
    yield_rate: float | None = None
    report_time: datetime | None = None
    business_date: date | None = None
    last_seen_from_mes_at: datetime | None = None


class MesWipTotalSnapshotOut(BaseModel):
    source_id: str
    workshop_name: str
    process_name: str | None = None
    doing_count: int | None = None
    doing_weight_tons: float | None = None
    snapshot_at: datetime
    source_page: str | None = None
    source_path: str | None = None
    source_table: str | None = None
    source_workshop_field: str | None = None
    source_process_field: str | None = None
    source_weight_field: str | None = None


class MesReferenceItemOut(BaseModel):
    source_type: str
    source_id: str
    code: str | None = None
    name: str | None = None
    parent_id: str | None = None
    workshop_name: str | None = None
    status_name: str | None = None
    last_seen_from_mes_at: datetime | None = None
