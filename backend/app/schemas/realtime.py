from __future__ import annotations

from pydantic import BaseModel, Field


class LiveShiftCellOut(BaseModel):
    shift_id: int
    shift_name: str
    submitted_count: int = 0
    draft_count: int = 0
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
    machine_binding_status: str = 'bound'
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
    business_date_context: dict = Field(default_factory=dict)
    overall_progress: dict = Field(default_factory=dict)
    workshops: list[LiveWorkshopSummaryOut] = Field(default_factory=list)
    factory_total: dict = Field(default_factory=dict)
    data_quality: dict = Field(default_factory=dict)
    mes_machine_binding: dict = Field(default_factory=dict)
    yield_matrix_lane: dict = Field(default_factory=dict)
    owner_daily_status: dict = Field(default_factory=dict)
    mes_sync_status: dict = Field(default_factory=dict)
    data_source: str = 'work_order_runtime'


class LiveMissingOutputWeightResolveRequest(BaseModel):
    output_weight: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)


class LiveMissingOutputWeightResolveOut(BaseModel):
    entry_id: int
    work_order_id: int
    output_weight: float
    yield_rate: float | None = None
    entry_status: str


class LiveActiveBusinessDateOut(BaseModel):
    business_date: str
    source: str = 'current_date'
    recent_entry_count: int = 0


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


class LivePendingAssignmentSummaryOut(BaseModel):
    entry_count: int = 0
    draft_entry_count: int = 0
    formal_entry_count: int = 0
    missing_machine_count: int = 0
    missing_shift_count: int = 0
    input: float = 0
    output: float = 0
    scrap: float = 0


class LivePendingMachineCandidateOut(BaseModel):
    machine_id: int
    machine_name: str


class LivePendingAssignmentItemOut(BaseModel):
    tracking_card_no: str
    entry_id: int
    work_order_id: int | None = None
    business_date: str
    workshop_id: int
    workshop_name: str
    shift_id: int | None = None
    shift_name: str | None = None
    machine_id: int | None = None
    entry_status: str
    entry_type: str
    input_weight: float | None = None
    output_weight: float | None = None
    scrap_weight: float | None = None
    missing_fields: list[str] = Field(default_factory=list)
    created_by_user_id: int | None = None
    created_by_user_name: str | None = None
    created_by_username: str | None = None
    mes_match_count: int = 0
    mes_machine_id: int | None = None
    mes_machine_name: str | None = None
    machine_candidate_count: int = 0
    machine_candidate_names: list[str] = Field(default_factory=list)
    machine_candidates: list[LivePendingMachineCandidateOut] = Field(default_factory=list)
    created_at: str | None = None


class LivePendingAssignmentOut(BaseModel):
    business_date: str
    workshop_id: int | None = None
    total: int = 0
    summary: LivePendingAssignmentSummaryOut = Field(default_factory=LivePendingAssignmentSummaryOut)
    items: list[LivePendingAssignmentItemOut] = Field(default_factory=list)


class LiveMesFillGapSummaryOut(BaseModel):
    total: int = 0
    status_counts: dict = Field(default_factory=dict)


class LiveMesFillGapItemOut(BaseModel):
    status: str
    workshop_id: int | None = None
    workshop_name: str | None = None
    process_name: str | None = None
    batch_no: str | None = None
    tracking_card_no: str | None = None
    local_entry_id: int | None = None
    mes_input_weight: float | None = None
    mes_output_weight: float | None = None
    local_input_weight: float | None = None
    local_output_weight: float | None = None
    mes_machine_name: str | None = None
    mes_resolved_machine_id: int | None = None
    mes_resolved_machine_name: str | None = None
    mes_machine_binding_source: str | None = None
    mes_machine_binding_confidence: str | None = None
    local_machine_name: str | None = None
    shift_name: str | None = None
    shift_window: str | None = None
    mes_end_time: str | None = None


class LiveMesFillGapOut(BaseModel):
    business_date: str
    workshop_id: int | None = None
    total: int = 0
    summary: LiveMesFillGapSummaryOut = Field(default_factory=LiveMesFillGapSummaryOut)
    items: list[LiveMesFillGapItemOut] = Field(default_factory=list)


class LiveFillDetailSummaryOut(BaseModel):
    entry_count: int = 0
    machine_count: int = 0
    owner_count: int = 0
    output: float = 0
    energy_kwh: float = 0
    gas_m3: float = 0
    source_counts: dict = Field(default_factory=dict)


class LiveFillDetailItemOut(BaseModel):
    row_id: str
    source_type: str
    source_label: str
    entry_id: int | None = None
    report_id: int | None = None
    tracking_card_no: str | None = None
    business_date: str
    workshop_id: int | None = None
    workshop_name: str | None = None
    machine_id: int | None = None
    machine_name: str | None = None
    shift_id: int | None = None
    shift_name: str | None = None
    responsible_user_id: int | None = None
    responsible_name: str | None = None
    responsible_username: str | None = None
    status: str | None = None
    entry_type: str | None = None
    input_weight: float | None = None
    output_weight: float | None = None
    scrap_weight: float | None = None
    yield_rate: float | None = None
    energy_kwh: float | None = None
    gas_m3: float | None = None
    submitted_at: str | None = None
    updated_at: str | None = None
    metrics: list[dict] = Field(default_factory=list)
    search_text: str = ''


class LiveFillDetailOut(BaseModel):
    business_date: str
    workshop_id: int | None = None
    total: int = 0
    summary: LiveFillDetailSummaryOut = Field(default_factory=LiveFillDetailSummaryOut)
    items: list[LiveFillDetailItemOut] = Field(default_factory=list)
