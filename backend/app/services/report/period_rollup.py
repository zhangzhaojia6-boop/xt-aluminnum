from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.reports import DailyReportHistoryRecord, OperationPeriodSnapshot
from app.services.report.daily_report_history import hash_payload
from app.services.report.operation_analysis import analyze_operation_period


_FIELD_MAP = {
    "total_output_daily": "total_output",
    "verified_cost_total": "verified_cost_total",
    "electricity_fee": "electricity_fee",
    "gas_fee": "gas_fee",
}
_CRITICAL_FIELDS = ("total_output_daily", "verified_cost_total")


def build_operation_period_snapshot(
    db: Session,
    *,
    period_type: str,
    target_date: date,
    trace_id: str | None = None,
    created_by_id: int | None = None,
) -> OperationPeriodSnapshot:
    period_start, period_end = _period_bounds(period_type, target_date)
    queried_rows = (
        db.query(DailyReportHistoryRecord)
        .filter(DailyReportHistoryRecord.report_type == "daily")
        .filter(DailyReportHistoryRecord.business_date >= period_start)
        .filter(DailyReportHistoryRecord.business_date <= period_end)
        .order_by(
            DailyReportHistoryRecord.business_date.asc(),
            DailyReportHistoryRecord.created_at.asc(),
            DailyReportHistoryRecord.id.asc(),
        )
        .all()
    )
    rows = _latest_daily_rows(queried_rows)
    metrics, invalid_metrics = _sum_daily_metrics(rows)
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
        "invalid_metrics": invalid_metrics,
    }
    snapshot = (
        db.query(OperationPeriodSnapshot)
        .filter(OperationPeriodSnapshot.period_type == period_type)
        .filter(OperationPeriodSnapshot.period_start == period_start)
        .filter(OperationPeriodSnapshot.period_end == period_end)
        .one_or_none()
    )
    is_new_snapshot = snapshot is None
    if snapshot is None:
        snapshot = OperationPeriodSnapshot(
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
        )
        db.add(snapshot)

    snapshot.status = "ready"
    snapshot.cumulative_metrics = metrics
    snapshot.analysis_payload = {"invalid_metrics": invalid_metrics}
    snapshot.source_daily_report_ids = source_daily_report_ids
    snapshot.source_snapshot_ids = source_snapshot_ids
    snapshot.missing_dates = missing_dates
    snapshot.payload_hash = hash_payload(payload)
    if is_new_snapshot or created_by_id is not None:
        snapshot.created_by_id = created_by_id
    snapshot.trace_id = trace_id
    snapshot.analysis_payload = analyze_operation_period(snapshot)
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


def _latest_daily_rows(rows: list[DailyReportHistoryRecord]) -> list[DailyReportHistoryRecord]:
    latest_by_date: dict[date, DailyReportHistoryRecord] = {}
    for row in rows:
        if row.business_date is None:
            continue
        latest_by_date[row.business_date] = row
    return [latest_by_date[business_date] for business_date in sorted(latest_by_date)]


def _sum_daily_metrics(
    rows: list[DailyReportHistoryRecord],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    totals: dict[str, dict[str, Any]] = {}
    invalid_metrics: list[dict[str, str]] = []
    for row in rows:
        facts = row.report_payload.get("facts") if isinstance(row.report_payload, dict) else {}
        if not isinstance(facts, dict):
            for source_field in _CRITICAL_FIELDS:
                invalid_metrics.append(_invalid_metric_entry(row, source_field, "invalid_facts"))
            continue
        for source_field in _CRITICAL_FIELDS:
            reason = _invalid_metric_reason(facts, source_field)
            if reason is not None:
                invalid_metrics.append(_invalid_metric_entry(row, source_field, reason))
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
    return totals, invalid_metrics


def _invalid_metric_reason(facts: dict[str, Any], source_field: str) -> str | None:
    if source_field not in facts:
        return "missing"
    item = facts.get(source_field)
    if not isinstance(item, dict):
        return "invalid_structure"
    value = item.get("value")
    if value is None:
        return "missing_value"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "invalid_value"
    return None


def _invalid_metric_entry(
    row: DailyReportHistoryRecord,
    source_field: str,
    reason: str,
) -> dict[str, str]:
    business_date = row.business_date.isoformat() if row.business_date is not None else ""
    return {
        "business_date": business_date,
        "field": source_field,
        "reason": reason,
    }


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
