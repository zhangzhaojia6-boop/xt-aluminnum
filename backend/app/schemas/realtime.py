from __future__ import annotations

from pydantic import BaseModel, Field


class LiveShiftCellOut(BaseModel):
    shift_id: int
    shift_name: str
    submitted_count: int = 0
    total_expected: int = 0
    total_input: float = 0
    total_output: float = 0
    total_scrap: float = 0
    yield_rate: float | None = None
    yield_rate_source: str | None = None
    attendance_status: str = 'not_started'
    attendance_exception_count: int = 0
    submission_status: str = 'not_started'
    is_applicable: bool = True
    status_tone: str = 'muted'
    status_text: str = ''


class LiveMachineSummaryOut(BaseModel):
    machine_id: int
    machine_name: str
    shifts: list[LiveShiftCellOut] = Field(default_factory=list)
    day_total: dict = Field(default_factory=dict)


class LiveWorkshopSummaryOut(BaseModel):
    workshop_id: int
    workshop_name: str
    machines: list[LiveMachineSummaryOut] = Field(default_factory=list)
    shift_totals: list[dict] = Field(default_factory=list)
    workshop_total: dict = Field(default_factory=dict)


class LiveAggregationOut(BaseModel):
    business_date: str
    overall_progress: dict = Field(default_factory=dict)
    workshops: list[LiveWorkshopSummaryOut] = Field(default_factory=list)
    factory_total: dict = Field(default_factory=dict)
    yield_matrix_lane: dict = Field(default_factory=dict)
    mes_sync_status: dict = Field(default_factory=dict)
    data_source: str = 'work_order_runtime'


class LiveCellBatchOut(BaseModel):
    tracking_card_no: str
    entry_id: int
    work_order_id: int | None = None
    entry_status: str
    entry_type: str
    input_weight: float | None = None
    output_weight: float | None = None
    scrap_weight: float | None = None
    yield_rate: float | None = None
    yield_rate_source: str | None = None
    machine_id: int | None = None
    shift_id: int | None = None


class LiveCellDetailOut(BaseModel):
    business_date: str
    workshop_id: int
    machine_id: int
    shift_id: int
    items: list[LiveCellBatchOut] = Field(default_factory=list)
