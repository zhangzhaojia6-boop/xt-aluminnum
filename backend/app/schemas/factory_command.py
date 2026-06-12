from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FactoryCommandFreshnessOut(BaseModel):
    status: str
    lag_seconds: float | None = None
    last_synced_at: str | None = None
    last_event_at: str | None = None
    source: str = 'mes_projection'
    configured: bool = True
    migration_ready: bool = True
    action_required: str = 'none'
    risk_tone: str = 'normal'


class FactoryEstimateOut(BaseModel):
    label: str
    estimated_cost: float | None = None
    estimated_gross_margin: float | None = None
    missing_data: list[str] = Field(default_factory=list)


class FactoryOverviewOut(BaseModel):
    business_date: str | None = None
    source: str = 'mes_projection'
    freshness: FactoryCommandFreshnessOut
    wip_tons: float = 0.0
    today_output_tons: float = 0.0
    stock_tons: float = 0.0
    total_input_tons: float = 0.0
    total_output_tons: float = 0.0
    process_output_tons: float | None = None
    yield_rate: float | None = None
    process_yield_rate: float | None = None
    output_basis: str | None = None
    process_output_basis: str | None = None
    workshop_summary: list[dict[str, Any]] = Field(default_factory=list)
    abnormal_count: int = 0
    cost_estimate: FactoryEstimateOut
    missing_data: list[str] = Field(default_factory=list)


class FactoryWorkshopOut(BaseModel):
    workshop_name: str
    active_coil_count: int = 0
    active_tons: float = 0.0
    stalled_count: int = 0
    freshness: FactoryCommandFreshnessOut | None = None


class FactoryMachineLineOut(BaseModel):
    line_code: str
    line_name: str | None = None
    workshop_name: str | None = None
    active_coil_count: int = 0
    active_tons: float = 0.0
    finished_tons: float = 0.0
    stalled_count: int = 0
    machine_binding_status: str = 'bound'
    mes_binding: dict[str, Any] = Field(default_factory=dict)
    cost_estimate: FactoryEstimateOut
    margin_estimate: FactoryEstimateOut
    freshness: FactoryCommandFreshnessOut | None = None


class FactoryCoilListItemOut(BaseModel):
    coil_key: str
    tracking_card_no: str
    batch_no: str | None = None
    material_code: str | None = None
    mes_input_weight_tons: float | None = None
    mes_output_weight_tons: float | None = None
    auto_scrap_weight_tons: float | None = None
    auto_scrap_rate: float | None = None
    scrap_status: str = 'no_mes_process_record'
    line_code: str | None = None
    machine_code: str | None = None
    previous_workshop: str | None = None
    previous_process: str | None = None
    current_workshop: str | None = None
    current_process: str | None = None
    next_workshop: str | None = None
    next_process: str | None = None
    destination: dict[str, Any]


class FactoryCoilFlowOut(BaseModel):
    coil_key: str
    tracking_card_no: str | None = None
    mes_input_weight_tons: float | None = None
    mes_output_weight_tons: float | None = None
    auto_scrap_weight_tons: float | None = None
    auto_scrap_rate: float | None = None
    scrap_status: str = 'no_mes_process_record'
    previous_workshop: str | None = None
    previous_process: str | None = None
    current_workshop: str | None = None
    current_process: str | None = None
    next_workshop: str | None = None
    next_process: str | None = None
    destination: dict[str, Any]
    freshness: FactoryCommandFreshnessOut


class FactoryCostBenefitOut(BaseModel):
    freshness: FactoryCommandFreshnessOut
    label: str
    estimated_cost: float | None = None
    estimated_gross_margin: float | None = None
    missing_data: list[str] = Field(default_factory=list)


class FactoryDestinationOut(BaseModel):
    kind: str
    label: str
    coil_count: int = 0
    tons: float = 0.0
    freshness: FactoryCommandFreshnessOut | None = None


class FactoryRawPayloadOut(BaseModel):
    model_config = ConfigDict(extra='allow')
