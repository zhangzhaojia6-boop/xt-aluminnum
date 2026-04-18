"""试点运行指标服务。
用于替代人工日报口径对齐，输出试点复盘所需最小指标。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.production import MobileShiftReport, ShiftProductionData
from app.services.mobile_report_service import summarize_mobile_reporting


def _to_utc(dt: datetime | None) -> datetime | None:
    """将时间统一转换为 UTC 感知时间。"""

    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    """计算百分位数。"""

    ordered = sorted(float(item) for item in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = max(0.0, min(1.0, percentile)) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    fraction = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def collect_pilot_metrics(db: Session, *, target_date: date, workshop_id: int | None = None) -> dict:
    """汇总试点运行最小指标。"""

    mobile_summary = summarize_mobile_reporting(db, target_date=target_date, workshop_id=workshop_id)
    report_query = db.query(MobileShiftReport).filter(MobileShiftReport.business_date == target_date)
    if workshop_id is not None:
        report_query = report_query.filter(MobileShiftReport.workshop_id == workshop_id)
    report_rows = report_query.all()

    ttr_minutes: list[float] = []
    for row in report_rows:
        submitted_at = _to_utc(getattr(row, "submitted_at", None))
        created_at = _to_utc(getattr(row, "created_at", None))
        if submitted_at is None or created_at is None:
            continue
        delta = (submitted_at - created_at).total_seconds() / 60.0
        if delta >= 0:
            ttr_minutes.append(delta)

    reported_count = int(mobile_summary.get("reported_count") or 0)
    returned_count = int(mobile_summary.get("returned_count") or 0)
    return_rate = round((returned_count / reported_count) * 100, 2) if reported_count > 0 else 0.0

    spd_query = db.query(ShiftProductionData).filter(ShiftProductionData.business_date == target_date)
    if workshop_id is not None:
        spd_query = spd_query.filter(ShiftProductionData.workshop_id == workshop_id)
    flagged_count = int(
        spd_query.filter(ShiftProductionData.data_status == "flagged")
        .with_entities(func.count(ShiftProductionData.id))
        .scalar()
        or 0
    )
    stable_count = int(
        db.query(func.count(ShiftProductionData.id))
        .filter(
            ShiftProductionData.business_date == target_date,
            ShiftProductionData.data_status.in_(("confirmed", "flagged")),
            *( [ShiftProductionData.workshop_id == workshop_id] if workshop_id is not None else [] ),
        )
        .scalar()
        or 0
    )
    diff_rate = round((flagged_count / stable_count) * 100, 2) if stable_count > 0 else 0.0

    ttr_p50 = _percentile(ttr_minutes, 0.5)
    ttr_p90 = _percentile(ttr_minutes, 0.9)
    return {
        "business_date": target_date.isoformat(),
        "workshop_id": workshop_id,
        "ttr_minutes_p50": round(ttr_p50, 2) if ttr_p50 is not None else None,
        "ttr_minutes_p90": round(ttr_p90, 2) if ttr_p90 is not None else None,
        "ttr_sample_size": len(ttr_minutes),
        "reporting_rate": float(mobile_summary.get("reporting_rate") or 0.0),
        "reported_count": reported_count,
        "expected_count": int(mobile_summary.get("expected_count") or 0),
        "return_rate": return_rate,
        "returned_count": returned_count,
        "difference_rate": diff_rate,
        "flagged_count": flagged_count,
        "stable_count": stable_count,
        "config_warnings": list(mobile_summary.get("config_warnings") or []),
    }

