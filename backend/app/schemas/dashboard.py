from __future__ import annotations

from datetime import date as calendar_date
from datetime import datetime as calendar_datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.leader_summary import LeaderMetricsOut, LeaderSummaryOut


class RuntimeTraceFrontlineOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    status: str | None = None
    expected_count: int | None = None
    reported_count: int | None = None
    auto_confirmed_count: int | None = None
    returned_count: int | None = None
    unreported_count: int | None = None
    late_count: int | None = None
    reminder_count: int | None = None
    reporting_rate: float | None = None


class RuntimeTraceBacklineOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    status: str | None = None
    history_points: int | None = None
    energy_row_count: int | None = None
    exception_count: int | None = None
    reconciliation_open_count: int | None = None
    mes_last_run_status: str | None = None


class RuntimeTraceDeliveryOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    status: str | None = None
    delivery_ready: bool | None = None
    reports_generated: int | None = None
    reports_ready_count: int | None = None
    reports_published_count: int | None = None
    missing_steps: list[str] | None = None


class RuntimeTraceSourceLaneOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    key: str | None = None
    label: str | None = None
    actor_label: str | None = None
    detail: str | None = None
    stage_label: str | None = None
    stage_detail: str | None = None
    result_label: str | None = None
    result_targets: list[str] | None = None
    status: str | None = None


class RuntimeTraceOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    source_lanes: list[RuntimeTraceSourceLaneOut] | None = None
    frontline: RuntimeTraceFrontlineOut | None = None
    backline: RuntimeTraceBacklineOut | None = None
    delivery: RuntimeTraceDeliveryOut | None = None


class DashboardSourceMetaOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    source: str | None = None
    source_label: str | None = None
    source_variant: str | None = None


class DashboardHistorySnapshotOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    date: calendar_date | None = None
    output_weight: float | None = None
    shipment_weight: float | None = None
    contract_weight: float | None = None
    energy_per_ton: float | None = None


class DashboardArchiveOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    total_output: float | None = None
    shipment_weight: float | None = None
    contract_weight: float | None = None
    energy_per_ton: float | None = None


class DashboardHistoryDigestOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    daily_snapshots: list[DashboardHistorySnapshotOut] | None = None
    month_archive: DashboardArchiveOut | None = None
    year_archive: DashboardArchiveOut | None = None


class DashboardMobileReportingSummaryOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    expected_count: int | None = None
    reported_count: int | None = None
    submitted_count: int | None = None
    auto_confirmed_count: int | None = None
    returned_count: int | None = None
    unreported_count: int | None = None
    late_count: int | None = None
    exception_count: int | None = None
    reporting_rate: float | None = None
    returned_items: list[dict[str, Any]] | None = None


class DashboardReminderSummaryOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    unreported_count: int | None = None
    late_report_count: int | None = None
    today_reminder_count: int | None = None
    recent_items: list[dict[str, Any]] | None = None


class DashboardExceptionLaneOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    unreported_shift_count: int | None = None
    returned_shift_count: int | None = None
    late_shift_count: int | None = None
    mobile_exception_count: int | None = None
    reminder_unreported_count: int | None = None
    reminder_late_count: int | None = None
    today_reminder_count: int | None = None
    production_exception_count: int | None = None
    reconciliation_open_count: int | None = None
    pending_report_publish_count: int | None = None
    returned_items: list[dict[str, Any]] | None = None
    reminder_items: list[dict[str, Any]] | None = None
    recent_items: list[dict[str, Any]] | None = None


class DeliveryStatusOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    target_date: calendar_date | None = None
    imports_completed: bool | None = None
    reconciliation_open_count: int | None = None
    quality_open_count: int | None = None
    blocker_count: int | None = None
    reports_generated: int | None = None
    reports_reviewed_count: int | None = None
    reports_published_count: int | None = None
    reports_published: int | None = None
    reports_published_deprecated: bool | None = None
    delivery_ready: bool | None = None
    missing_steps: list[str] | None = None


class DashboardEnergySummaryOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    electricity_value: float | None = None
    gas_value: float | None = None
    water_value: float | None = None
    total_energy: float | None = None
    output_weight: float | None = None
    total_output_weight: float | None = None
    energy_per_ton: float | None = None
    rows: list[dict[str, Any]] | None = None


class ManagementEstimateAssumptionsOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    revenue_per_ton: float | None = None
    electricity_cost_per_unit: float | None = None
    gas_cost_per_unit: float | None = None
    labor_cost_per_attendance: float | None = None


class ManagementEstimateOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    estimate_ready: bool | None = None
    estimated_revenue: float | None = None
    estimated_cost: float | None = None
    estimated_margin: float | None = None
    energy_cost: float | None = None
    labor_cost: float | None = None
    active_contract_count: int | None = None
    stalled_contract_count: int | None = None
    active_coil_count: int | None = None
    stalled_coil_count: int | None = None
    today_advanced_weight: float | None = None
    remaining_weight: float | None = None
    reported_shift_count: int | None = None
    unreported_shift_count: int | None = None
    reporting_rate: float | None = None
    total_attendance: int | None = None
    sync_lag_seconds: int | None = None
    sync_status: str | None = None
    assumptions: ManagementEstimateAssumptionsOut | None = None


class ContractProgressTrackingCardOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    tracking_card_no: str | None = None
    coil_id: str | None = None
    status: str | None = None
    workshop_code: str | None = None
    process_code: str | None = None
    updated_at: str | None = None


class ContractProgressContractOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    contract_no: str | None = None
    status: str | None = None
    active_coil_count: int | None = None
    stalled_coil_count: int | None = None
    today_advanced_coil_count: int | None = None
    today_advanced_weight: float | None = None
    remaining_weight: float | None = None
    workshops: list[str] | None = None
    processes: list[str] | None = None
    statuses: list[str] | None = None
    tracking_cards: list[ContractProgressTrackingCardOut] | None = None


class ContractProgressOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    target_date: calendar_date | None = None
    active_contract_count: int | None = None
    stalled_contract_count: int | None = None
    active_coil_count: int | None = None
    stalled_coil_count: int | None = None
    today_advanced_weight: float | None = None
    remaining_weight: float | None = None
    contracts: list[ContractProgressContractOut] | None = None


class ContractLaneItemOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    business_date: calendar_date | None = None
    source_batch_id: int | None = None
    sheet_name: str | None = None
    delivery_scope: str | None = None
    daily_contract_weight: float | None = None
    month_to_date_contract_weight: float | None = None
    daily_input_weight: float | None = None
    month_to_date_input_weight: float | None = None
    lineage_hash: str | None = None
    quality_status: str | None = None


class ContractLaneOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    business_date: calendar_date | None = None
    snapshot_count: int | None = None
    owner_entry_count: int | None = None
    delivery_scopes: list[str] | None = None
    daily_contract_weight: float | None = None
    month_to_date_contract_weight: float | None = None
    daily_input_weight: float | None = None
    month_to_date_input_weight: float | None = None
    quality_status: str | None = None
    items: list[ContractLaneItemOut] | None = None


class DashboardBlockerSummaryOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    has_blockers: bool | None = None
    digest: str | None = None


class AnalysisHandoffReportingOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    status: str | None = None
    reporting_rate: float | None = None
    reported_count: int | None = None
    unreported_count: int | None = None
    auto_confirmed_count: int | None = None
    returned_count: int | None = None
    source_labels: list[str] | None = None


class AnalysisHandoffDeliveryOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    status: str | None = None
    delivery_ready: bool | None = None
    reports_generated: int | None = None
    reports_published_count: int | None = None
    missing_steps: list[str] | None = None
    source_labels: list[str] | None = None


class AnalysisHandoffEnergyOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    status: str | None = None
    energy_per_ton: float | None = None
    total_energy: float | None = None
    electricity_value: float | None = None
    gas_value: float | None = None
    water_value: float | None = None
    source_labels: list[str] | None = None


class AnalysisHandoffContractsOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    status: str | None = None
    daily_contract_weight: float | None = None
    month_to_date_contract_weight: float | None = None
    active_contract_count: int | None = None
    stalled_contract_count: int | None = None
    remaining_weight: float | None = None
    source_labels: list[str] | None = None


class AnalysisHandoffRiskOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    status: str | None = None
    has_blockers: bool | None = None
    blocker_digest: str | None = None
    reconciliation_open_count: int | None = None
    mobile_exception_count: int | None = None
    production_exception_count: int | None = None
    source_labels: list[str] | None = None


class AnalysisHandoffTrendOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    current_output: float | None = None
    yesterday_output: float | None = None
    output_delta_vs_yesterday: float | None = None
    seven_day_average_output: float | None = None


class AnalysisHandoffFreshnessOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    freshness_status: str | None = None
    sync_status: str | None = None
    sync_lag_seconds: int | None = None
    history_points: int | None = None
    published_report_at: calendar_datetime | None = None


class AnalysisHandoffSectionMatrixOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    healthy_sections: list[str] | None = None
    warning_sections: list[str] | None = None
    blocked_sections: list[str] | None = None
    idle_sections: list[str] | None = None


class AnalysisHandoffSectionReasonsOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    reporting: list[str] | None = None
    delivery: list[str] | None = None
    energy: list[str] | None = None
    contracts: list[str] | None = None
    risk: list[str] | None = None


class AnalysisHandoffSourceMatrixOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    reporting: list[str] | None = None
    delivery: list[str] | None = None
    energy: list[str] | None = None
    contracts: list[str] | None = None
    risk: list[str] | None = None


class AnalysisHandoffSourceVariantsOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    reporting: list[str] | None = None
    delivery: list[str] | None = None
    energy: list[str] | None = None
    contracts: list[str] | None = None
    risk: list[str] | None = None


class AnalysisHandoffActionMatrixOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    reporting: list[str] | None = None
    delivery: list[str] | None = None
    energy: list[str] | None = None
    contracts: list[str] | None = None
    risk: list[str] | None = None


class AnalysisHandoffOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    target_date: calendar_date | None = None
    surface: str | None = None
    readiness: bool | None = None
    blocking_reasons: list[str] | None = None
    priority: str | None = None
    attention_flags: list[str] | None = None
    data_gaps: list[str] | None = None
    section_matrix: AnalysisHandoffSectionMatrixOut | None = None
    section_reasons: AnalysisHandoffSectionReasonsOut | None = None
    source_matrix: AnalysisHandoffSourceMatrixOut | None = None
    source_variants: AnalysisHandoffSourceVariantsOut | None = None
    action_matrix: AnalysisHandoffActionMatrixOut | None = None
    freshness: AnalysisHandoffFreshnessOut | None = None
    trend: AnalysisHandoffTrendOut | None = None
    reporting: AnalysisHandoffReportingOut | None = None
    delivery: AnalysisHandoffDeliveryOut | None = None
    energy: AnalysisHandoffEnergyOut | None = None
    contracts: AnalysisHandoffContractsOut | None = None
    risk: AnalysisHandoffRiskOut | None = None


class WorkshopReportingStatusOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    workshop_id: int | None = None
    workshop_name: str | None = None
    workshop_code: str | None = None
    report_status: str | None = None
    output_weight: float | None = None
    source_label: str | None = None
    source_variant: str | None = None
    status_hint: str | None = None


class ProductionLaneRowOut(DashboardSourceMetaOut):
    workshop_id: int | None = None
    workshop_name: str | None = None
    workshop_code: str | None = None
    total_output: float | None = None
    target_value: float | None = None
    compare_value: float | None = None
    delta_vs_yesterday: float | None = None


class EnergyLaneRowOut(DashboardSourceMetaOut):
    shift_code: str | None = None
    electricity_value: float | None = None
    gas_value: float | None = None
    water_value: float | None = None
    energy_per_ton: float | None = None
    is_over_line: bool | None = None


class InventoryLaneRowOut(DashboardSourceMetaOut):
    team_name: str | None = None
    storage_prepared: float | None = None
    storage_finished: float | None = None
    storage_inbound_area: float | None = None
    shipment_weight: float | None = None
    actual_inventory_weight: float | None = None
    contract_received: float | None = None


class FactoryDashboardResponse(BaseModel):
    model_config = ConfigDict(extra='allow')

    target_date: calendar_date | None = None
    leader_summary: LeaderSummaryOut | None = None
    leader_metrics: LeaderMetricsOut | None = None
    history_digest: DashboardHistoryDigestOut | None = None
    delivery_ready: bool | None = None
    delivery_status: DeliveryStatusOut | None = None
    mobile_reporting_summary: DashboardMobileReportingSummaryOut | None = None
    reminder_summary: DashboardReminderSummaryOut | None = None
    blocker_summary: DashboardBlockerSummaryOut | None = None
    management_estimate: ManagementEstimateOut | None = None
    contract_lane: ContractLaneOut | None = None
    production_lane: list[ProductionLaneRowOut] | None = None
    energy_lane: list[EnergyLaneRowOut] | None = None
    inventory_lane: list[InventoryLaneRowOut] | None = None
    exception_lane: DashboardExceptionLaneOut | None = None
    contract_progress: ContractProgressOut | None = None
    workshop_reporting_status: list[WorkshopReportingStatusOut] | None = None
    analysis_handoff: AnalysisHandoffOut | None = None
    runtime_trace: RuntimeTraceOut | None = None


class WorkshopDashboardResponse(BaseModel):
    model_config = ConfigDict(extra='allow')

    target_date: calendar_date | None = None
    workshop_id: int | None = None
    total_output: float | None = None
    month_to_date_output: float | None = None
    pending_shift_count: int | None = None
    history_digest: DashboardHistoryDigestOut | None = None
    mobile_reporting_summary: DashboardMobileReportingSummaryOut | None = None
    reminder_summary: DashboardReminderSummaryOut | None = None
    energy_summary: DashboardEnergySummaryOut | None = None
    production_lane: list[ProductionLaneRowOut] | None = None
    energy_lane: list[EnergyLaneRowOut] | None = None
    inventory_lane: list[InventoryLaneRowOut] | None = None
    exception_lane: DashboardExceptionLaneOut | None = None
    analysis_handoff: AnalysisHandoffOut | None = None
    runtime_trace: RuntimeTraceOut | None = None
