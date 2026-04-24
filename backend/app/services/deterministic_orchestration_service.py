from __future__ import annotations

from typing import Any


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float, *, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _build_status(*, score: float, has_blocker: bool) -> str:
    if has_blocker:
        return "blocked"
    if score >= 80:
        return "healthy"
    if score >= 60:
        return "warning"
    return "alert"


def build_runtime_orchestration_snapshot(
    *,
    mobile_summary: dict[str, Any] | None,
    exception_lane: dict[str, Any] | None,
    delivery_status: dict[str, Any] | None,
    reminder_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build deterministic runtime orchestration metrics for dashboard rendering."""

    mobile_summary = mobile_summary or {}
    exception_lane = exception_lane or {}
    delivery_status = delivery_status or {}
    reminder_summary = reminder_summary or {}

    reporting_rate = _as_float(mobile_summary.get("reporting_rate"))
    unreported_count = _as_int(mobile_summary.get("unreported_count"))
    returned_count = _as_int(mobile_summary.get("returned_count"))
    late_count = _as_int(mobile_summary.get("late_count"))

    mobile_exception_count = _as_int(exception_lane.get("mobile_exception_count"))
    production_exception_count = _as_int(exception_lane.get("production_exception_count"))
    reconciliation_open_count = _as_int(exception_lane.get("reconciliation_open_count"))
    reminder_count = _as_int(reminder_summary.get("today_reminder_count"))

    missing_steps = [str(item) for item in (delivery_status.get("missing_steps") or []) if item]
    delivery_ready = bool(delivery_status.get("delivery_ready")) and not missing_steps

    coverage_penalty = unreported_count * 5 + returned_count * 4 + late_count * 2
    coverage_score = _clamp(reporting_rate - coverage_penalty)

    quality_penalty = (
        mobile_exception_count * 4
        + production_exception_count * 4
        + reconciliation_open_count * 6
        + returned_count * 3
    )
    quality_score = _clamp(100 - quality_penalty)

    delivery_penalty = len(missing_steps) * 14 + _as_int(delivery_status.get("blocker_count")) * 12
    delivery_score = _clamp((100 if delivery_ready else 65) - delivery_penalty)

    reliability_score = round(
        coverage_score * 0.4 + quality_score * 0.35 + delivery_score * 0.25,
        1,
    )

    bottlenecks: list[str] = []
    if unreported_count > 0:
        bottlenecks.append("班次缺报")
    if returned_count > 0:
        bottlenecks.append("自动校验退回")
    if mobile_exception_count + production_exception_count > 0:
        bottlenecks.append("异常待清理")
    if reconciliation_open_count > 0:
        bottlenecks.append("差异未闭环")
    if missing_steps:
        bottlenecks.append("交付链路未完成")
    if reminder_count > 0 and "班次缺报" not in bottlenecks:
        bottlenecks.append("催报仍在进行")

    blocking_count = len(bottlenecks)
    if reliability_score >= 85 and blocking_count == 0:
        risk_level = "low"
    elif reliability_score >= 70 and blocking_count <= 2:
        risk_level = "medium"
    else:
        risk_level = "high"

    algorithm_status = _build_status(
        score=coverage_score,
        has_blocker=unreported_count > 0 or returned_count > 0,
    )
    analysis_status = _build_status(
        score=quality_score,
        has_blocker=mobile_exception_count + production_exception_count + reconciliation_open_count > 0,
    )
    execution_status = _build_status(
        score=delivery_score,
        has_blocker=not delivery_ready,
    )

    return {
        "reliability_score": reliability_score,
        "risk_level": risk_level,
        "blocking_count": blocking_count,
        "bottlenecks": bottlenecks,
        "scores": {
            "coverage": round(coverage_score, 1),
            "quality": round(quality_score, 1),
            "delivery": round(delivery_score, 1),
        },
        "workers": [
            {
                "key": "algorithm_pipeline",
                "label": "算法流水线",
                "status": algorithm_status,
                "value": f"覆盖 {round(coverage_score, 1)}",
            },
            {
                "key": "analysis_agent",
                "label": "分析决策助手",
                "status": analysis_status,
                "value": f"质量 {round(quality_score, 1)}",
            },
            {
                "key": "execution_agent",
                "label": "执行交付助手",
                "status": execution_status,
                "value": f"交付 {round(delivery_score, 1)}",
            },
        ],
    }
