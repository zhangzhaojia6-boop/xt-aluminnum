from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.models.reports import OperationPeriodSnapshot


def analyze_operation_period(snapshot: OperationPeriodSnapshot) -> dict[str, Any]:
    metrics = snapshot.cumulative_metrics or {}
    output = _metric_value(metrics, "total_output")
    cost_total = _metric_value(metrics, "verified_cost_total")
    cost_per_ton = _cost_per_ton(cost_total, output)
    invalid_metrics = _invalid_metrics(snapshot)
    risks: list[str] = []
    if snapshot.missing_dates:
        risks.append(f"缺少{len(snapshot.missing_dates)}天历史日报，月/年累计可能不完整")
    if invalid_metrics:
        risks.append(f"存在无效关键指标{len(invalid_metrics)}项，月/年累计已跳过这些异常项")
    if output == 0 and cost_total != 0:
        risks.append("累计产量为0但成本不为0，无法计算吨成本")

    electricity_fee = _format_metric(
        _metric_value(metrics, "electricity_fee"),
        _metric_unit(metrics, "electricity_fee"),
    )
    gas_fee = _format_metric(_metric_value(metrics, "gas_fee"), _metric_unit(metrics, "gas_fee"))
    snapshot_count = len(snapshot.source_snapshot_ids or [])

    return {
        "period_type": snapshot.period_type,
        "period_label": f"{snapshot.period_start.isoformat()} 至 {snapshot.period_end.isoformat()}",
        "sections": {
            "production": {
                "total_output": _format_metric(output, _metric_unit(metrics, "total_output")),
            },
            "cost": {
                "verified_cost_total": _format_metric(cost_total, _metric_unit(metrics, "verified_cost_total")),
                "electricity_fee": electricity_fee,
                "gas_fee": gas_fee,
                "cost_per_ton": f"{cost_per_ton}元/吨" if cost_per_ton is not None else None,
            },
            "energy": {
                "electricity_fee": electricity_fee,
                "gas_fee": gas_fee,
            },
            "trace": {
                "daily_report_count": len(snapshot.source_daily_report_ids or []),
                "snapshot_count": snapshot_count,
                "source_snapshot_count": snapshot_count,
                "missing_dates": snapshot.missing_dates or [],
                "invalid_metrics": invalid_metrics,
            },
        },
        "risks": risks,
    }


def _metric_value(metrics: dict[str, Any], key: str) -> float:
    item = metrics.get(key)
    value = item.get("value") if isinstance(item, dict) else None
    if not isinstance(value, bool) and isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _metric_unit(metrics: dict[str, Any], key: str) -> str:
    item = metrics.get(key)
    if isinstance(item, dict) and item.get("unit"):
        return str(item["unit"])
    return ""


def _format_metric(value: float, unit: str) -> str:
    return f"{round(value, 2)}{unit}"


def _cost_per_ton(cost_total: float, output: float) -> str | None:
    if output == 0:
        return None
    value = Decimal(str(cost_total)) / Decimal(str(output))
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _invalid_metrics(snapshot: OperationPeriodSnapshot) -> list[dict[str, Any]]:
    payload = snapshot.analysis_payload if isinstance(snapshot.analysis_payload, dict) else {}
    raw_items = payload.get("invalid_metrics")
    if raw_items is None:
        sections = payload.get("sections")
        trace = sections.get("trace") if isinstance(sections, dict) else None
        raw_items = trace.get("invalid_metrics") if isinstance(trace, dict) else None
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]
