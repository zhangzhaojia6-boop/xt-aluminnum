from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LeaderMetricsOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    report_date: str | None = None
    total_output_weight: float | None = None
    total_energy: float | None = None
    energy_per_ton: float | None = None
    reporting_rate: float | None = None
    total_attendance: int | None = None
    contract_weight: float | None = None
    yield_rate: float | None = None
    anomaly_total: int | None = None
    anomaly_digest: str | None = None
    in_process_weight: float | None = None
    consumable_weight: float | None = None
    today_total_output: float | None = None
    storage_finished_weight: float | None = None
    shipment_weight: float | None = None
    storage_inbound_area: float | None = None
    active_contract_count: int | None = None
    stalled_contract_count: int | None = None
    active_coil_count: int | None = None
    sync_lag_seconds: float | None = None


class LeaderSummaryOut(BaseModel):
    model_config = ConfigDict(extra='allow')

    summary_text: str | None = None
    summary_source: str | None = None
    llm_enabled: bool | None = None
    llm_error: str | None = None
    metrics: LeaderMetricsOut | None = None
