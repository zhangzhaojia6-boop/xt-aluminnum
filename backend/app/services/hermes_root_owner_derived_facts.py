from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.core.business_time import production_business_window
from app.domain.daily_report_field_contract import DAILY_REPORT_NORMATIVE_FIELD_COUNT
from app.domain.metric_contracts import DAILY_REPORT_METRIC_CONTRACTS
from app.services.report.daily_fact_bundle import _conflict_blocks_ready
from app.services.report.daily_fact_gap_closure_service import GROUP_LABELS, _field_label
from app.services.report.mes_factory_packaging_fact import query_factory_packaging_output_by_date

_DINGTALK_SOURCE_KEYS = ("dingtalk_group_file", "dingtalk_group_content")
_DINGTALK_FIELD_LABELS = {
    "daily_input_weight": "投料量",
    "cold_roll_input_daily": "冷轧投料",
    "cold_1850_input_daily": "1850 冷轧投料",
    "cold_2050_input_daily": "2050 冷轧投料",
    "medium_plate_input_daily": "中厚板投料",
    "outsourced_input_daily": "外协投料",
    "daily_contract_weight": "当天接合同",
    "daily_hot_roll_contract_weight": "当天热轧合同",
    "remaining_contract_weight": "总余合同量",
    "remaining_contract_delta": "总余合同较昨日",
    "daily_yield_rate": "日成品率",
    "daily_yield_delta": "日成品率较昨日",
    "monthly_yield_rate": "月成品率",
    "hot_roll_yield_rate": "热轧成品率",
    "hot_roll_monthly_yield_rate": "热轧月成品率",
    "hot_roll_yield_delta": "热轧成品率较昨日",
    "plate_coil_yield_rate": "板卷成品率",
}
_KEY_METRICS = (
    "total_output_daily",
    "finished_inbound_daily",
    "daily_input_weight",
    "wip_total",
    "daily_yield_rate",
    "remaining_contract_weight",
    "total_electricity_kwh",
    "cost_per_ton",
)
_KEY_METRIC_LABELS = {
    "daily_input_weight": "投料量",
    "remaining_contract_weight": "总余合同量",
    "cost_per_ton": "吨成本",
}
_MISSING_FORMAL_SOURCE_NEXT_STEP = "到数据中枢异常中心查看缺口，由对应责任人补录。"


@dataclass(frozen=True, slots=True)
class DerivedFact:
    field: str
    source_key: str
    status: str
    fact: Mapping[str, Any]
    summary: str


def build_derived_facts(
    db: Session | None,
    *,
    business_date: date,
    metric_keys: tuple[str, ...],
    normalized_text: str,
    hub_payload: Mapping[str, Any] | None,
) -> list[DerivedFact]:
    payload = hub_payload if isinstance(hub_payload, Mapping) else {}
    builders = {
        "annual_total_output": lambda: _annual_total(db, business_date),
        "electricity_per_ton": lambda: _electricity_per_ton(payload),
        "dingtalk_specialist_evidence": lambda: _specialist_evidence(payload, business_date),
        "source_status": lambda: _source_status(payload, normalized_text),
        "daily_report_readiness": lambda: _report_readiness(payload),
    }
    facts: list[DerivedFact] = []
    for metric_key in metric_keys:
        builder = builders.get(metric_key)
        fact = builder() if builder is not None else None
        if fact is not None:
            facts.append(fact)
    return facts


def _annual_total(db: Session | None, business_date: date) -> DerivedFact | None:
    year_start = date(business_date.year, 1, 1)
    totals = query_factory_packaging_output_by_date(db, year_start, business_date)
    if not totals:
        return None
    expected_days = (business_date - year_start).days + 1
    covered_days = len(totals)
    total = round(sum(totals.values()), 2)
    first_day = min(totals).isoformat()
    display = (
        f"{_number(total)} 吨，只统计到 {first_day} 起有包装记录的 {covered_days} 天，"
        f"今年到这天共 {expected_days} 天，不是完整年累计"
    )
    return DerivedFact(
        field="annual_total_output",
        source_key="data_hub_projection",
        status="candidate",
        summary="数据中枢按日累加包装产量",
        fact={
            "value": total,
            "status": "candidate",
            "unit": "吨",
            "source_key": "data_hub_projection",
            "source_type": "mes_packaging_output",
            "display": display,
            "reason": f"annual_coverage_incomplete:{covered_days}/{expected_days}",
            "action": "补齐缺失日期的包装投影，或由负责人给出年初累计后再转正式口径。",
        },
    )


def _electricity_per_ton(payload: Mapping[str, Any]) -> DerivedFact | None:
    facts = _facts(payload)
    electricity = (facts.get("total_electricity_kwh") or {}).get("value")
    output = (facts.get("total_output_daily") or {}).get("value")
    if electricity in (None, "") or not output:
        return None
    value = round(float(electricity) / float(output), 2)
    return DerivedFact(
        field="electricity_per_ton",
        source_key="data_hub_projection",
        status="candidate",
        summary="高压合计用电量除以当天包装产量",
        fact={
            "value": value,
            "status": "candidate",
            "unit": "度/吨",
            "source_key": "data_hub_projection",
            "source_type": "data_hub",
            "display": f"{_number(value)} 度/吨（高压合计 {_number(electricity)} 度 ÷ 包装产量 {_number(output)} 吨）",
            "reason": "derived:total_electricity_kwh/total_output_daily",
            "action": "分子来自能耗表，分母来自包装产量；任一项更正后重新计算。",
        },
    )


def _specialist_evidence(payload: Mapping[str, Any], business_date: date) -> DerivedFact | None:
    items: list[dict[str, Any]] = []
    parts: list[str] = []
    anchor: Mapping[str, Any] | None = None
    for field_name, fact in _facts(payload).items():
        if not isinstance(fact, Mapping) or fact.get("source_type") != "dingtalk_supplement":
            continue
        source_ref = fact.get("source_ref")
        if not isinstance(source_ref, Mapping) or fact.get("value") in (None, ""):
            continue
        evidence_id = source_ref.get("evidence_id")
        if evidence_id in (None, "") or source_ref.get("source_key") not in _DINGTALK_SOURCE_KEYS:
            continue
        label = _DINGTALK_FIELD_LABELS.get(str(field_name)) or _field_label(str(field_name))
        unit = str(fact.get("unit") or "").strip()
        items.append({"label": label, "value": fact["value"], "evidence_id": evidence_id})
        parts.append(f"{label} {_number(fact['value'])}{f' {unit}' if unit else ''}（证据 {evidence_id}）")
        anchor = anchor or source_ref
    if anchor is None:
        return None
    start_at, end_at = production_business_window(business_date)
    contract = DAILY_REPORT_METRIC_CONTRACTS["dingtalk_specialist_evidence"]
    source_key = str(anchor["source_key"])
    trace_id = str(anchor.get("trace_id") or "")
    return DerivedFact(
        field="dingtalk_specialist_evidence",
        source_key=source_key,
        status="confirmed",
        summary="钉钉证据已被日报事实采信",
        fact={
            "value": items,
            "status": "confirmed",
            "source_key": source_key,
            "source_type": "dingtalk_supplement",
            "source_ref": {
                "source_key": source_key,
                "evidence_id": anchor["evidence_id"],
                "trace_id": trace_id,
                "business_date": business_date.isoformat(),
            },
            "business_date": business_date.isoformat(),
            "business_window": f"{start_at.isoformat()}/{end_at.isoformat()}",
            "metric_contract_version": contract.metric_contract_version,
            "trace_id": trace_id,
            "source_trace_id": trace_id,
            "display": f"共 {len(items)} 个数字：{'；'.join(parts)}",
        },
    )


def _source_status(payload: Mapping[str, Any], normalized_text: str) -> DerivedFact | None:
    if not _facts(payload) and not payload.get("missing_fields"):
        return None
    if "不可信" in normalized_text:
        return _least_trusted(payload)
    return _missing_formal_sources(payload)


def _least_trusted(payload: Mapping[str, Any]) -> DerivedFact:
    facts = _facts(payload)
    conflicts = {
        str(item.get("field") or "")
        for item in payload.get("conflicts") or []
        if isinstance(item, Mapping) and _conflict_blocks_ready(item)
    }
    ranked: list[tuple[int, str, str]] = []
    for field_name in _KEY_METRICS:
        fact = facts.get(field_name)
        has_value = isinstance(fact, Mapping) and fact.get("value") not in (None, "")
        label = _KEY_METRIC_LABELS.get(field_name) or _field_label(field_name)
        if field_name in conflicts:
            ranked.append((0, label, "来源互相冲突"))
        elif not has_value:
            ranked.append((1, label, "没有来源"))
        elif fact.get("evidence_gaps"):
            ranked.append((2, label, "有值但缺读取证据"))
    ranked.sort(key=lambda item: item[0])
    if ranked:
        display = "；".join(f"{label}（{why}）" for _rank, label, why in ranked)
        display = f"最不可信的依次是：{display}；其余关键数字都有读取证据"
    else:
        display = "这几个关键数字都有读取证据，没有明显不可信的"
    return DerivedFact(
        field="source_status",
        source_key="data_hub_projection",
        status="candidate",
        summary="按事实包的来源证据排查",
        fact={
            "value": {"least_trusted": [label for _rank, label, _why in ranked]},
            "status": "candidate",
            "source_key": "data_hub_projection",
            "source_type": "data_hub",
            "display": display,
            "reason": f"least_trusted_key_metrics:{len(ranked)}",
            "action": _first_next_step(payload),
        },
    )


def _missing_formal_sources(payload: Mapping[str, Any]) -> DerivedFact:
    missing = [str(item) for item in payload.get("missing_fields") or []]
    unread = sum(
        1 for fact in _facts(payload).values() if isinstance(fact, Mapping) and fact.get("evidence_gaps")
    )
    groups = _group_counts(payload)
    display = f"共 {len(missing)} 项缺正式来源"
    if groups:
        display += f"：{groups}"
    if unread:
        display += f"；另有 {unread} 项有值但缺读取证据"
    return DerivedFact(
        field="source_status",
        source_key="data_hub_projection",
        status="candidate",
        summary="按事实包的缺口清单统计",
        fact={
            "value": {"missing_count": len(missing), "unread_count": unread},
            "status": "candidate",
            "source_key": "data_hub_projection",
            "source_type": "data_hub",
            "display": display,
            "reason": f"missing_formal_source_count:{len(missing)}",
            "action": _first_next_step(payload),
        },
    )


def _report_readiness(payload: Mapping[str, Any]) -> DerivedFact | None:
    if not _facts(payload) and not payload.get("missing_fields"):
        return None
    missing = [str(item) for item in payload.get("missing_fields") or []]
    closure = payload.get("fact_closure") if isinstance(payload.get("fact_closure"), Mapping) else {}
    can_generate = not missing and closure.get("status") == "pass"
    if can_generate:
        display = "可以自动生成，事实已闭环"
    else:
        display = f"不能自动生成：{DAILY_REPORT_NORMATIVE_FIELD_COUNT} 项里缺 {len(missing)} 项"
        groups = _group_counts(payload)
        if groups:
            display += f"（{groups}）"
    return DerivedFact(
        field="daily_report_readiness",
        source_key="data_hub_projection",
        status="candidate",
        summary="按事实闭环和缺口清单判断",
        fact={
            "value": {"can_auto_generate": can_generate, "missing_count": len(missing)},
            "status": "candidate",
            "source_key": "data_hub_projection",
            "source_type": "data_hub",
            "display": display,
            "reason": f"daily_report_missing_fields:{len(missing)}",
            "action": _first_next_step(payload),
        },
    )


def _facts(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    facts = payload.get("facts")
    return facts if isinstance(facts, Mapping) else {}


def _gap_plan(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    gap_plan = payload.get("gap_plan")
    return gap_plan if isinstance(gap_plan, Mapping) else {}


def _group_counts(payload: Mapping[str, Any]) -> str:
    summary = _gap_plan(payload).get("summary")
    by_group = summary.get("by_group") if isinstance(summary, Mapping) else None
    if not isinstance(by_group, Mapping):
        return ""
    ordered = sorted(by_group.items(), key=lambda item: -int(item[1]))
    return "、".join(f"{GROUP_LABELS.get(str(group), '日报')} {count} 项" for group, count in ordered)


def _first_next_step(payload: Mapping[str, Any]) -> str:
    for item in _gap_plan(payload).get("items") or []:
        if isinstance(item, Mapping) and str(item.get("next_step") or "").strip():
            return str(item["next_step"]).strip()
    return _MISSING_FORMAL_SOURCE_NEXT_STEP


def _number(value: Any) -> str:
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    return str(value)
