from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from app.services.report.template_daily_field_contract import field_group


GROUP_ACTIONS: dict[str, dict[str, str]] = {
    "opening": {
        "source_lane": "dingtalk_or_mes_final",
        "entry_route": "/entry/fill",
        "next_step": "先查钉钉日报消息和 MES/WMS 最终口径；没有最终来源时由负责人扫码补录。",
    },
    "workshop_output": {
        "source_lane": "dingtalk_or_scan_fill_workshop",
        "entry_route": "/entry/fill",
        "next_step": "优先查钉钉车间日报；MES 过程数据只做证据，最终缺口由车间或日报负责人扫码补录。",
    },
    "manual_supplement": {
        "source_lane": "scan_fill_owner_daily",
        "entry_route": "/entry/fill",
        "next_step": "这类字段通常不在 MES 最终页里，优先由专项负责人扫码补录或提交钉钉证据。",
    },
    "wip": {
        "source_lane": "mes_readonly_or_dingtalk_wip",
        "entry_route": "/entry/fill",
        "next_step": "先查 MES 在制快照并复核单位；MES 口径缺失或截图为准时，由专项负责人补在制证据。",
    },
    "energy": {
        "source_lane": "dingtalk_or_scan_fill_energy",
        "entry_route": "/entry/fill",
        "next_step": "优先采用钉钉能耗表或电工扫码填报；物联网能耗库未配置时不要强算正式值。",
    },
    "contract_input": {
        "source_lane": "mes_wms_or_scan_fill_contract",
        "entry_route": "/entry/fill",
        "next_step": "合同、投料、入库先查 MES/WMS 最终单据；缺少最终口径时由内勤或日报负责人补录。",
    },
    "yield": {
        "source_lane": "computed_or_quality_confirmation",
        "entry_route": "/entry/fill",
        "next_step": "成品率必须保留分子分母；缺任一输入时由质量或日报负责人确认后补录。",
    },
    "cost": {
        "source_lane": "computed_or_root_owner",
        "entry_route": "/entry/fill",
        "next_step": "成本依赖电费、气费和折算吨数；缺输入时先补能耗和产量，再由负责人确认。",
    },
}

FIELD_ACTIONS: dict[str, dict[str, str]] = {
    "total_output_daily": {
        "source_lane": "dingtalk_or_final_daily_report",
        "entry_route": "/entry/fill",
        "next_step": "车间总产量不能直接用包装过程量替代，优先查钉钉最终日报或负责人补录。",
    },
    "finished_inbound_daily": {
        "source_lane": "dingtalk_or_wms_final",
        "entry_route": "/entry/fill",
        "next_step": "成品入库优先查钉钉确认和 WMS 最终单据；口径冲突时保留差异。",
    },
    "wip_total": {
        "source_lane": "mes_wip_snapshot_or_dingtalk",
        "entry_route": "/entry/fill",
        "next_step": "先复核 MES 在制快照单位；与人工截图冲突时用钉钉/扫码证据覆盖并留 trace。",
    },
    "total_electricity_kwh": {
        "source_lane": "dingtalk_or_scan_fill_energy",
        "entry_route": "/entry/fill",
        "next_step": "高压总用电优先采用钉钉能耗表或电工扫码填报；物联网能耗库未配置时标缺失。",
    },
    "total_gas_m3": {
        "source_lane": "dingtalk_or_scan_fill_energy",
        "entry_route": "/entry/fill",
        "next_step": "全厂用气优先采用钉钉能耗表或电工扫码填报，不能用局部机列明细替代全厂总量。",
    },
}


def classify_daily_report_field_gap(field_name: str) -> dict[str, str]:
    group = field_group(field_name)
    base = dict(GROUP_ACTIONS.get(group) or GROUP_ACTIONS["opening"])
    base.update(FIELD_ACTIONS.get(field_name) or {})
    return {
        "field": field_name,
        "group": group,
        "source_lane": base["source_lane"],
        "entry_route": base["entry_route"],
        "next_step": base["next_step"],
    }


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

