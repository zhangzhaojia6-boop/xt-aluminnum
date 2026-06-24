from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.reports import DailyReportHistoryRecord, OperationPeriodSnapshot
from app.services.report.daily_report_history import hash_payload


_FIELD_MAP = {
    "total_output_daily": "total_output",
    "verified_cost_total": "verified_cost_total",
    "electricity_fee": "electricity_fee",
    "gas_fee": "gas_fee",
}


def build_operation_period_snapshot(
    db: Session,
    *,
    period_type: str,
    target_date: date,
    trace_id: str | None = None,
    created_by_id: int | None = None,
) -> OperationPeriodSnapshot:
    period_start, period_end = _period_bounds(period_type, target_date)
    rows = (
        db.query(DailyReportHistoryRecord)
        .filter(DailyReportHistoryRecord.report_type == "daily")
        .filter(DailyReportHistoryRecord.business_date >= period_start)
        .filter(DailyReportHistoryRecord.business_date <= period_end)
        .order_by(DailyReportHistoryRecord.business_date.asc(), DailyReportHistoryRecord.id.asc())
        .all()
    )
    metrics = _sum_daily_metrics(rows)
    source_daily_report_ids = [row.id for row in rows]
    source_snapshot_ids = [row.source_snapshot_id for row in rows if row.source_snapshot_id is not None]
    missing_dates = _missing_dates(rows, period_start, period_end)
    payload: dict[str, Any] = {
        "period_type": period_type,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "cumulative_metrics": metrics,
        "source_daily_report_ids": source_daily_report_ids,
        "source_snapshot_ids": source_snapshot_ids,
        "missing_dates": missing_dates,
    }
    snapshot = OperationPeriodSnapshot(
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        status="ready",
        cumulative_metrics=metrics,
        analysis_payload={},
        source_daily_report_ids=source_daily_report_ids,
        source_snapshot_ids=source_snapshot_ids,
        missing_dates=missing_dates,
        payload_hash=hash_payload(payload),
        created_by_id=created_by_id,
        trace_id=trace_id,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _period_bounds(period_type: str, target_date: date) -> tuple[date, date]:
    if period_type == "month":
        return date(target_date.year, target_date.month, 1), target_date
    if period_type == "full_month":
        last_day = monthrange(target_date.year, target_date.month)[1]
        return date(target_date.year, target_date.month, 1), date(target_date.year, target_date.month, last_day)
    if period_type == "year":
        return date(target_date.year, 1, 1), target_date
    if period_type == "full_year":
        return date(target_date.year, 1, 1), date(target_date.year, 12, 31)
    raise ValueError(f"unsupported period_type: {period_type}")


def _sum_daily_metrics(rows: list[DailyReportHistoryRecord]) -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for row in rows:
        facts = row.report_payload.get("facts") if isinstance(row.report_payload, dict) else {}
        if not isinstance(facts, dict):
            continue
        for source_field, target_field in _FIELD_MAP.items():
            item = facts.get(source_field)
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            bucket = totals.setdefault(
                target_field,
                {"value": 0.0, "unit": item.get("unit"), "source_fields": []},
            )
            bucket["value"] = round(float(bucket["value"]) + float(value), 4)
            source_fields = bucket["source_fields"]
            if isinstance(source_fields, list) and source_field not in source_fields:
                source_fields.append(source_field)
    return totals


def _missing_dates(
    rows: list[DailyReportHistoryRecord],
    period_start: date,
    period_end: date,
) -> list[str]:
    present_dates = {row.business_date.isoformat() for row in rows if row.business_date is not None}
    missing: list[str] = []
    cursor = period_start
    while cursor <= period_end:
        value = cursor.isoformat()
        if value not in present_dates:
            missing.append(value)
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return missing
