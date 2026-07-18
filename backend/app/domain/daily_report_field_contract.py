from __future__ import annotations

from dataclasses import dataclass

from app.core.business_time import (
    BILLET_PRODUCTION_BUSINESS_DAY_START,
    OWNER_DAILY_BUSINESS_DAY_START,
    OWNER_DAILY_LATE_CUTOFF,
    PRODUCTION_BUSINESS_DAY_START,
)
from app.domain.daily_report_field_names import TEMPLATE_FIELD_GROUPS as FIELD_GROUPS


DAILY_REPORT_FIELD_CONTRACT_VERSION = "2026-07-18"

BUSINESS_TIME_STANDARD = "production_07_50"
BUSINESS_TIME_BILLET = "billet_10_00"
BUSINESS_TIME_STARTS = {
    BUSINESS_TIME_STANDARD: PRODUCTION_BUSINESS_DAY_START.strftime("%H:%M"),
    BUSINESS_TIME_BILLET: BILLET_PRODUCTION_BUSINESS_DAY_START.strftime("%H:%M"),
}
OWNER_DAILY_SUBMISSION_TIME = OWNER_DAILY_BUSINESS_DAY_START.strftime("%H:%M")
OWNER_DAILY_LATE_TIME = OWNER_DAILY_LATE_CUTOFF.strftime("%H:%M")

SOURCE_LANE_DINGTALK = "dingtalk_evidence"
SOURCE_LANE_AUTHORIZED_CORRECTION = "authorized_correction"
SOURCE_LANE_MES_WMS_READONLY = "mes_wms_readonly"
SOURCE_LANE_SCAN_SUPPLEMENT = "scan_supplement"
SOURCE_LANE_DATA_HUB_PROJECTION = "data_hub_projection"
SOURCE_LANE_HISTORICAL_RECORD = "historical_record"
SOURCE_LANE_RAG_EXPLANATION_ONLY = "rag_explanation_only"
SOURCE_LANE_OUTPUT_SKILL_REFERENCE = "output_skill_reference"

FACT_SOURCE_LANE_ORDER = (
    SOURCE_LANE_DINGTALK,
    SOURCE_LANE_AUTHORIZED_CORRECTION,
    SOURCE_LANE_MES_WMS_READONLY,
    SOURCE_LANE_SCAN_SUPPLEMENT,
    SOURCE_LANE_DATA_HUB_PROJECTION,
    SOURCE_LANE_HISTORICAL_RECORD,
    SOURCE_LANE_RAG_EXPLANATION_ONLY,
)
_SOURCE_LANE_PRIORITIES = {
    lane: (len(FACT_SOURCE_LANE_ORDER) - index) * 10
    for index, lane in enumerate(FACT_SOURCE_LANE_ORDER)
}
_SOURCE_LANE_PRIORITIES[SOURCE_LANE_OUTPUT_SKILL_REFERENCE] = -1

REFERENCE_ROLE_COMPARE_ONLY = "compare_only"

TEMPLATE_ONLY_FIELD_REASONS = {
    "recovery_daily": "legacy_template_unit_not_frozen",
    "recovery_month": "legacy_template_unit_not_frozen",
    "remaining_contract_delta": "derived_display_field_outside_normative_denominator",
}

_EXACT_UNIT_BY_FIELD = {
    "report_date": "日期",
    "cast_roll_active_lines": "条",
    "roller_grind_daily": "根",
    "roller_grind_month": "根",
    "electricity_cost_10k": "万元",
    "gas_cost_10k": "万元",
    "total_cost_10k": "万元",
    "cost_basis_weight": "吨",
    "cost_per_ton": "元/吨",
}
_TWENTY_TOLERANCE_FIELDS = {
    "total_output_daily",
    "finished_inbound_daily",
    "wip_total",
    "total_electricity_kwh",
}
_BILLET_FIELD_PREFIXES = (
    "cast_2_",
    "cast_3_",
    "hot_roll_",
    "east_furnace_",
    "west_furnace_",
    "medium_plate_",
)


@dataclass(frozen=True, slots=True)
class DailyReportFieldContract:
    field_name: str
    group: str
    unit: str
    business_time_scope: str
    tolerance: float
    source_lanes: tuple[str, ...]
    reference_role: str = REFERENCE_ROLE_COMPARE_ONLY
    contract_version: str = DAILY_REPORT_FIELD_CONTRACT_VERSION


def _ordered_template_fields() -> tuple[str, ...]:
    return tuple(
        field_name
        for group_fields in FIELD_GROUPS.values()
        for field_name in group_fields
    )


def normative_daily_report_fields() -> tuple[str, ...]:
    return tuple(
        field_name
        for field_name in _ordered_template_fields()
        if field_name not in TEMPLATE_ONLY_FIELD_REASONS
    )


def _field_group(field_name: str) -> str:
    for group_name, group_fields in FIELD_GROUPS.items():
        if field_name in group_fields:
            return group_name
    raise KeyError(field_name)


def _field_unit(field_name: str) -> str:
    exact = _EXACT_UNIT_BY_FIELD.get(field_name)
    if exact is not None:
        return exact
    if "_pass_" in field_name:
        return "道"
    if "electricity_per_ton" in field_name:
        return "kWh/吨"
    if "gas_per_ton" in field_name:
        return "m³/吨"
    if "yield" in field_name:
        return "%"
    if field_name.endswith("electricity_kwh"):
        return "kWh"
    if field_name.endswith("gas_m3"):
        return "m³"
    return "吨"


def _field_tolerance(field_name: str, unit: str) -> float:
    if field_name in _TWENTY_TOLERANCE_FIELDS:
        return 20.0
    if unit in {"%", "kWh/吨", "m³/吨"}:
        return 0.2
    return 0.0


def _field_business_time_scope(field_name: str) -> str:
    if field_name.startswith(_BILLET_FIELD_PREFIXES):
        return BUSINESS_TIME_BILLET
    return BUSINESS_TIME_STANDARD


def _build_contract(field_name: str) -> DailyReportFieldContract:
    unit = _field_unit(field_name)
    return DailyReportFieldContract(
        field_name=field_name,
        group=_field_group(field_name),
        unit=unit,
        business_time_scope=_field_business_time_scope(field_name),
        tolerance=_field_tolerance(field_name, unit),
        source_lanes=FACT_SOURCE_LANE_ORDER,
    )


DAILY_REPORT_FIELD_CONTRACTS = {
    field_name: _build_contract(field_name)
    for field_name in normative_daily_report_fields()
}


def daily_report_field_contract_for(field_name: str) -> DailyReportFieldContract:
    return DAILY_REPORT_FIELD_CONTRACTS[field_name]


def daily_report_field_tolerance_for(field_name: str) -> float:
    return daily_report_field_contract_for(field_name).tolerance


def source_lane_for(source_type: str | None) -> str:
    normalized = str(source_type or "").strip().lower()
    if normalized in _SOURCE_LANE_PRIORITIES:
        return normalized
    if normalized in {"output_skill", "official_daily_report"}:
        return SOURCE_LANE_OUTPUT_SKILL_REFERENCE
    if normalized.startswith("dingtalk"):
        return SOURCE_LANE_DINGTALK
    if normalized == "root_owner_correction":
        return SOURCE_LANE_AUTHORIZED_CORRECTION
    if (
        normalized.startswith("mes_")
        or normalized.startswith("wms")
        or normalized in {"mes_wms", "finished_inbound_output"}
    ):
        return SOURCE_LANE_MES_WMS_READONLY
    if normalized in {
        "owner_daily",
        "owner_daily_month_sum",
        "owner_or_energy_summary",
        "manual",
        "manual_mobile_coil",
        "manual_workbook",
        "recovery_daily",
        "overhaul_daily",
    }:
        return SOURCE_LANE_SCAN_SUPPLEMENT
    if normalized in {"historical_report", "previous_final_report"}:
        return SOURCE_LANE_HISTORICAL_RECORD
    if normalized == "rag":
        return SOURCE_LANE_RAG_EXPLANATION_ONLY
    return SOURCE_LANE_DATA_HUB_PROJECTION


def source_lane_priority(source_type: str | None) -> int:
    return _SOURCE_LANE_PRIORITIES[source_lane_for(source_type)]
