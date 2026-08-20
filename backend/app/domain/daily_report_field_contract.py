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
DAILY_REPORT_NORMATIVE_FIELD_COUNT = 127

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
    SOURCE_LANE_DINGTALK: 100,
    SOURCE_LANE_AUTHORIZED_CORRECTION: 90,
    SOURCE_LANE_MES_WMS_READONLY: 80,
    SOURCE_LANE_SCAN_SUPPLEMENT: 70,
    SOURCE_LANE_DATA_HUB_PROJECTION: 60,
    SOURCE_LANE_HISTORICAL_RECORD: 40,
    SOURCE_LANE_RAG_EXPLANATION_ONLY: 30,
    SOURCE_LANE_OUTPUT_SKILL_REFERENCE: -1,
}

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
    gap_source_lane: str
    owner_role: str
    deadline: str
    fill_strategy: str
    entry_route: str
    entry_fields: tuple[str, ...]
    next_step: str
    reference_role: str = REFERENCE_ROLE_COMPARE_ONLY
    contract_version: str = DAILY_REPORT_FIELD_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class DailyReportGapAction:
    field: str
    group: str
    source_lane: str
    entry_route: str
    fill_strategy: str
    owner_role: str
    deadline: str
    entry_fields: tuple[str, ...]
    next_step: str


_GROUP_GAP_DEFAULTS: dict[str, dict[str, object]] = {
    "opening": {
        "source_lane": "dingtalk_or_mes_final",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "factory_dispatch",
        "entry_fields": (),
        "next_step": "先查钉钉日报消息和 MES/WMS 最终口径；没有最终来源时由负责人扫码补录。",
    },
    "workshop_output": {
        "source_lane": "dingtalk_or_scan_fill_workshop",
        "entry_route": "/entry/fill",
        "fill_strategy": "shift_report",
        "owner_role": "machine_operator",
        "entry_fields": ("output_weight",),
        "next_step": "优先查钉钉车间日报；MES 过程数据只做证据，最终缺口由车间或日报负责人扫码补录。",
    },
    "manual_supplement": {
        "source_lane": "scan_fill_owner_daily",
        "entry_route": "/manage/alerts",
        "fill_strategy": "source_recheck",
        "owner_role": "factory_dispatch",
        "entry_fields": (),
        "next_step": "这类字段通常不在 MES 最终页里，优先由专项负责人扫码补录或提交钉钉证据。",
    },
    "wip": {
        "source_lane": "mes_readonly_or_dingtalk_wip",
        "entry_route": "/manage/alerts",
        "fill_strategy": "source_recheck",
        "owner_role": "planning_owner",
        "entry_fields": (),
        "next_step": "先查 MES 在制快照并复核单位；MES 口径缺失或截图为准时，由专项负责人补在制证据。",
    },
    "energy": {
        "source_lane": "dingtalk_or_scan_fill_energy",
        "entry_route": "/manage/alerts",
        "fill_strategy": "source_recheck",
        "owner_role": "energy_chief",
        "entry_fields": (),
        "next_step": "优先采用钉钉能耗表或电工扫码填报；物联网能耗库未配置时不要强算正式值。",
    },
    "contract_input": {
        "source_lane": "mes_wms_or_scan_fill_contract",
        "entry_route": "/manage/alerts",
        "fill_strategy": "source_recheck",
        "owner_role": "planning_owner",
        "entry_fields": (),
        "next_step": "合同、投料、入库先查 MES/WMS 最终单据；缺少最终口径时由内勤或日报负责人补录。",
    },
    "yield": {
        "source_lane": "computed_or_quality_confirmation",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "quality_owner",
        "entry_fields": (),
        "next_step": "成品率必须保留分子分母；缺任一输入时由质量或日报负责人确认后补录。",
    },
    "cost": {
        "source_lane": "computed_or_root_owner",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "factory_dispatch",
        "entry_fields": (),
        "next_step": "成本依赖电费、气费和折算吨数；缺输入时先补能耗和产量，再由负责人确认。",
    },
}

_COMPUTED_GAP_DEFAULTS: dict[str, object] = {
    "entry_route": "/manage/alerts",
    "fill_strategy": "dependency_fill",
    "owner_role": "factory_dispatch",
    "entry_fields": (),
}

_FIELD_GAP_OVERRIDES: dict[str, dict[str, object]] = {
    "total_output_daily": {
        "source_lane": "dingtalk_or_final_daily_report",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "factory_dispatch",
        "entry_fields": (),
        "next_step": "车间总产量不能直接用包装过程量替代，优先查钉钉最终日报或负责人补录。",
    },
    "finished_inbound_daily": {
        "source_lane": "dingtalk_or_wms_final",
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "storage_owner",
        "entry_fields": ("park_inbound_daily", "new_plant_inbound_daily"),
        "next_step": "先查 WMS 和钉钉入库确认；仍缺失时由成品库分别补园区和新厂入库量。",
    },
    "cast_roll_daily": {
        "source_lane": "computed_from_cast_2_cast_3",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "factory_dispatch",
        "entry_fields": (),
        "next_step": "铸轧总产量由铸二和铸三日产量相加生成；先补齐或核对这两项，不能直接填一个总数覆盖。",
    },
    "wip_total": {
        "source_lane": "mes_wip_snapshot_or_dingtalk",
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ("wip_total",),
        "next_step": "先复核 MES 在制快照和单位；仍缺失或需人工确认时，由计划内勤扫码补录并保留任务 trace。",
    },
    "total_electricity_kwh": {
        "source_lane": "dingtalk_or_scan_fill_energy",
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ("total_electricity_kwh",),
        "next_step": "高压总用电优先采用钉钉能耗表或电工扫码填报；物联网能耗库未配置时标缺失。",
    },
    "total_gas_m3": {
        "source_lane": "dingtalk_or_scan_fill_energy",
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ("total_gas_m3",),
        "next_step": "全厂用气优先采用钉钉能耗表或电工扫码填报，不能用局部机列明细替代全厂总量。",
    },
    "cast_roll_gas_m3": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ("cast_roll_gas_m3",),
    },
    "smelting_gas_m3": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ("smelting_gas_m3",),
    },
    "hot_roll_furnace_gas_m3": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ("heating_furnace_gas_m3",),
    },
    "hot_roll_boiler_gas_m3": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ("boiler_gas_m3",),
    },
    "consignment_weight": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "storage_owner",
        "entry_fields": ("consignment_weight",),
    },
    "daily_contract_weight": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ("daily_contract_weight",),
    },
    "daily_hot_roll_contract_weight": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ("daily_hot_roll_contract_weight",),
    },
    "remaining_contract_weight": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ("remaining_contract_weight",),
    },
    "remaining_contract_delta": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ("remaining_contract_delta_weight",),
    },
    "cold_roll_input_daily": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ("daily_input_weight",),
    },
    "daily_yield_rate": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_confirmation",
        "owner_role": "quality_owner",
        "entry_fields": ("plant_wide_yield_rate",),
        "next_step": "先核对成品率分子分母；缺少最终确认时由质检内勤补全厂成品率并保留依据。",
    },
    "recovery_daily": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "recovery_owner",
        "entry_fields": ("recovery_weight",),
    },
    "roller_grind_daily": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "overhaul_owner",
        "entry_fields": ("roller_grinding_count",),
    },
    "shearing_daily": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "shipment_outflow_owner",
        "entry_fields": ("daily_shearing_output",),
    },
}


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


def _is_computed_gap_field(field_name: str) -> bool:
    return (
        field_name.endswith(("_month", "_monthly_yield_rate", "_delta"))
        or "_per_ton_" in field_name
        or "_pass_" in field_name
        or field_name
        in {
            "total_output_daily",
            "electricity_cost_10k",
            "gas_cost_10k",
            "total_cost_10k",
            "cost_basis_weight",
            "cost_per_ton",
        }
    )


def _gap_contract_data(field_name: str, group: str) -> dict[str, object]:
    data = dict(_GROUP_GAP_DEFAULTS[group])
    if _is_computed_gap_field(field_name):
        data.update(_COMPUTED_GAP_DEFAULTS)
    data.update(_FIELD_GAP_OVERRIDES.get(field_name) or {})
    return data


def _gap_deadline(action: dict[str, object]) -> str:
    if str(action["entry_route"]) == "/entry/fill":
        return OWNER_DAILY_LATE_TIME
    return BUSINESS_TIME_STARTS[BUSINESS_TIME_BILLET]


def _build_contract(field_name: str) -> DailyReportFieldContract:
    unit = _field_unit(field_name)
    group = _field_group(field_name)
    gap_action = _gap_contract_data(field_name, group)
    return DailyReportFieldContract(
        field_name=field_name,
        group=group,
        unit=unit,
        business_time_scope=_field_business_time_scope(field_name),
        tolerance=_field_tolerance(field_name, unit),
        source_lanes=FACT_SOURCE_LANE_ORDER,
        gap_source_lane=str(gap_action["source_lane"]),
        owner_role=str(gap_action["owner_role"]),
        deadline=_gap_deadline(gap_action),
        fill_strategy=str(gap_action["fill_strategy"]),
        entry_route=str(gap_action["entry_route"]),
        entry_fields=tuple(str(value) for value in gap_action["entry_fields"]),
        next_step=str(gap_action["next_step"]),
    )


DAILY_REPORT_FIELD_CONTRACTS = {
    field_name: _build_contract(field_name)
    for field_name in normative_daily_report_fields()
}

DAILY_REPORT_GAP_ACTIONS = {
    field_name: DailyReportGapAction(
        field=field_name,
        group=contract.group,
        source_lane=contract.gap_source_lane,
        entry_route=contract.entry_route,
        fill_strategy=contract.fill_strategy,
        owner_role=contract.owner_role,
        deadline=contract.deadline,
        entry_fields=contract.entry_fields,
        next_step=contract.next_step,
    )
    for field_name, contract in DAILY_REPORT_FIELD_CONTRACTS.items()
}


def daily_report_field_contract_for(field_name: str) -> DailyReportFieldContract:
    return DAILY_REPORT_FIELD_CONTRACTS[field_name]


def daily_report_gap_action_for(field_name: str) -> DailyReportGapAction:
    return DAILY_REPORT_GAP_ACTIONS[field_name]


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
    if normalized in {"root_owner", "root_owner_correction"}:
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
        "verified_owner_daily",
        "owner_or_energy_summary",
        "manual",
        "manual_mobile_coil",
        "manual_workbook",
        "recovery_daily",
        "overhaul_daily",
    }:
        return SOURCE_LANE_SCAN_SUPPLEMENT
    if normalized in {"historical_report", "history_report", "previous_final_report"}:
        return SOURCE_LANE_HISTORICAL_RECORD
    if normalized == "rag":
        return SOURCE_LANE_RAG_EXPLANATION_ONLY
    return SOURCE_LANE_DATA_HUB_PROJECTION


def source_lane_priority(source_type: str | None) -> int:
    return _SOURCE_LANE_PRIORITIES[source_lane_for(source_type)]
