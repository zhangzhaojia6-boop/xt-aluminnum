from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any
from urllib.parse import urlencode

from app.services.report.template_daily_field_contract import field_group


GROUP_ACTIONS: dict[str, dict[str, Any]] = {
    "opening": {
        "source_lane": "dingtalk_or_mes_final",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "factory_dispatch",
        "entry_fields": [],
        "next_step": "先查钉钉日报消息和 MES/WMS 最终口径；没有最终来源时由负责人扫码补录。",
    },
    "workshop_output": {
        "source_lane": "dingtalk_or_scan_fill_workshop",
        "entry_route": "/entry/fill",
        "fill_strategy": "shift_report",
        "owner_role": "machine_operator",
        "entry_fields": ["output_weight"],
        "next_step": "优先查钉钉车间日报；MES 过程数据只做证据，最终缺口由车间或日报负责人扫码补录。",
    },
    "manual_supplement": {
        "source_lane": "scan_fill_owner_daily",
        "entry_route": "/manage/alerts",
        "fill_strategy": "source_recheck",
        "owner_role": "factory_dispatch",
        "entry_fields": [],
        "next_step": "这类字段通常不在 MES 最终页里，优先由专项负责人扫码补录或提交钉钉证据。",
    },
    "wip": {
        "source_lane": "mes_readonly_or_dingtalk_wip",
        "entry_route": "/manage/alerts",
        "fill_strategy": "source_recheck",
        "owner_role": "planning_owner",
        "entry_fields": [],
        "next_step": "先查 MES 在制快照并复核单位；MES 口径缺失或截图为准时，由专项负责人补在制证据。",
    },
    "energy": {
        "source_lane": "dingtalk_or_scan_fill_energy",
        "entry_route": "/manage/alerts",
        "fill_strategy": "source_recheck",
        "owner_role": "energy_chief",
        "entry_fields": [],
        "next_step": "优先采用钉钉能耗表或电工扫码填报；物联网能耗库未配置时不要强算正式值。",
    },
    "contract_input": {
        "source_lane": "mes_wms_or_scan_fill_contract",
        "entry_route": "/manage/alerts",
        "fill_strategy": "source_recheck",
        "owner_role": "planning_owner",
        "entry_fields": [],
        "next_step": "合同、投料、入库先查 MES/WMS 最终单据；缺少最终口径时由内勤或日报负责人补录。",
    },
    "yield": {
        "source_lane": "computed_or_quality_confirmation",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "quality_owner",
        "entry_fields": [],
        "next_step": "成品率必须保留分子分母；缺任一输入时由质量或日报负责人确认后补录。",
    },
    "cost": {
        "source_lane": "computed_or_root_owner",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "factory_dispatch",
        "entry_fields": [],
        "next_step": "成本依赖电费、气费和折算吨数；缺输入时先补能耗和产量，再由负责人确认。",
    },
}

FIELD_ACTIONS: dict[str, dict[str, Any]] = {
    "total_output_daily": {
        "source_lane": "dingtalk_or_final_daily_report",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "factory_dispatch",
        "entry_fields": [],
        "next_step": "车间总产量不能直接用包装过程量替代，优先查钉钉最终日报或负责人补录。",
    },
    "finished_inbound_daily": {
        "source_lane": "dingtalk_or_wms_final",
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "storage_owner",
        "entry_fields": ["park_inbound_daily", "new_plant_inbound_daily"],
        "next_step": "先查 WMS 和钉钉入库确认；仍缺失时由成品库分别补园区和新厂入库量。",
    },
    "cast_roll_daily": {
        "source_lane": "computed_from_cast_2_cast_3",
        "entry_route": "/manage/alerts",
        "fill_strategy": "dependency_fill",
        "owner_role": "factory_dispatch",
        "entry_fields": [],
        "next_step": "铸轧总产量由铸二和铸三日产量相加生成；先补齐或核对这两项，不能直接填一个总数覆盖。",
    },
    "wip_total": {
        "source_lane": "mes_wip_snapshot_or_dingtalk",
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ["wip_total"],
        "next_step": "先复核 MES 在制快照和单位；仍缺失或需人工确认时，由计划内勤扫码补录并保留任务 trace。",
    },
    "total_electricity_kwh": {
        "source_lane": "dingtalk_or_scan_fill_energy",
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ["total_electricity_kwh"],
        "next_step": "高压总用电优先采用钉钉能耗表或电工扫码填报；物联网能耗库未配置时标缺失。",
    },
    "total_gas_m3": {
        "source_lane": "dingtalk_or_scan_fill_energy",
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ["total_gas_m3"],
        "next_step": "全厂用气优先采用钉钉能耗表或电工扫码填报，不能用局部机列明细替代全厂总量。",
    },
    "cast_roll_gas_m3": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ["cast_roll_gas_m3"],
    },
    "smelting_gas_m3": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ["smelting_gas_m3"],
    },
    "hot_roll_furnace_gas_m3": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ["heating_furnace_gas_m3"],
    },
    "hot_roll_boiler_gas_m3": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "energy_chief",
        "entry_fields": ["boiler_gas_m3"],
    },
    "consignment_weight": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "storage_owner",
        "entry_fields": ["consignment_weight"],
    },
    "daily_contract_weight": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ["daily_contract_weight"],
    },
    "daily_hot_roll_contract_weight": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ["daily_hot_roll_contract_weight"],
    },
    "remaining_contract_weight": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ["remaining_contract_weight"],
    },
    "remaining_contract_delta": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ["remaining_contract_delta_weight"],
    },
    "cold_roll_input_daily": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "planning_owner",
        "entry_fields": ["daily_input_weight"],
    },
    "daily_yield_rate": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_confirmation",
        "owner_role": "quality_owner",
        "entry_fields": ["plant_wide_yield_rate"],
        "next_step": "先核对成品率分子分母；缺少最终确认时由质检内勤补全厂成品率并保留依据。",
    },
    "recovery_daily": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "recovery_owner",
        "entry_fields": ["recovery_weight"],
    },
    "roller_grind_daily": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "overhaul_owner",
        "entry_fields": ["roller_grinding_count"],
    },
    "shearing_daily": {
        "entry_route": "/entry/fill",
        "fill_strategy": "owner_daily",
        "owner_role": "shipment_outflow_owner",
        "entry_fields": ["daily_shearing_output"],
    },
}


def _is_computed_field(field_name: str) -> bool:
    return (
        field_name.endswith(("_month", "_monthly_yield_rate", "_delta"))
        or "_per_ton_" in field_name
        or "_pass_" in field_name
        or field_name in {"total_output_daily", "electricity_cost_10k", "gas_cost_10k", "total_cost_10k", "cost_basis_weight", "cost_per_ton"}
    )


def classify_daily_report_field_gap(field_name: str) -> dict[str, Any]:
    group = field_group(field_name)
    base = dict(GROUP_ACTIONS.get(group) or GROUP_ACTIONS["opening"])
    if _is_computed_field(field_name):
        base.update({
            "entry_route": "/manage/alerts",
            "fill_strategy": "dependency_fill",
            "owner_role": "factory_dispatch",
            "entry_fields": [],
        })
    base.update(FIELD_ACTIONS.get(field_name) or {})
    entry_fields = [str(value) for value in base.get("entry_fields") or [] if str(value).strip()]
    return {
        "field": field_name,
        "group": group,
        "source_lane": base["source_lane"],
        "entry_route": base["entry_route"],
        "fill_strategy": base["fill_strategy"],
        "owner_role": base["owner_role"],
        "entry_fields": entry_fields,
        "entry_field": entry_fields[0] if entry_fields else None,
        "next_step": base["next_step"],
    }


def build_daily_report_gap_action_route(
    *,
    business_date: date,
    field: str,
    trace_id: str | None,
    action: Mapping[str, Any],
) -> str:
    normalized_trace_id = str(trace_id or "").strip()
    if str(action.get("entry_route") or "") != "/entry/fill":
        if not normalized_trace_id:
            return "/manage/alerts"
        return f"/manage/alerts?{urlencode({'trace_id': normalized_trace_id})}"

    entry_fields = [
        str(value).strip()
        for value in action.get("entry_fields") or []
        if str(value).strip()
    ]
    params = {
        "business_date": business_date.isoformat(),
        "field": str(field),
    }
    if entry_fields:
        params["entry_fields"] = ",".join(entry_fields)
        params["entry_field"] = entry_fields[0]
    owner_role = str(action.get("owner_role") or "").strip()
    if owner_role:
        params["owner_role"] = owner_role
    if normalized_trace_id:
        params["trace_id"] = normalized_trace_id
    return f"/entry/fill?{urlencode(params)}"


def build_daily_report_gap_plan(
    *,
    missing_fields: Sequence[str] | None = None,
    alignment: Mapping[str, Any] | None = None,
    sources: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_map = sources or {}

    for field_name in missing_fields or []:
        field = str(field_name)
        seen.add(field)
        items.append(
            _gap_item(
                field,
                problem_type="missing_field",
                actual=None,
                expected=None,
                source=source_map.get(field),
            )
        )

    for difference in _alignment_differences(alignment):
        field = str(difference.get("field") or "")
        if not field or field in seen:
            continue
        seen.add(field)
        items.append(
            _gap_item(
                field,
                problem_type="alignment_difference",
                actual=difference.get("actual"),
                expected=difference.get("expected"),
                source=source_map.get(field),
            )
        )

    group_counts = Counter(str(item["group"]) for item in items)
    lane_counts = Counter(str(item["source_lane"]) for item in items)
    return {
        "status": "needs_action" if items else "ready",
        "item_count": len(items),
        "summary": {
            "by_group": dict(sorted(group_counts.items())),
            "by_source_lane": dict(sorted(lane_counts.items())),
        },
        "items": items,
    }


def _alignment_differences(alignment: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not alignment:
        return []
    raw = alignment.get("differences")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _gap_item(
    field_name: str,
    *,
    problem_type: str,
    actual: Any,
    expected: Any,
    source: Any,
) -> dict[str, Any]:
    action = classify_daily_report_field_gap(field_name)
    current_source = source.get("source_type") or source.get("source") if isinstance(source, Mapping) else None
    return {
        **action,
        "problem_type": problem_type,
        "actual": actual,
        "expected": expected,
        "current_source": current_source,
        "blocking": True,
    }
