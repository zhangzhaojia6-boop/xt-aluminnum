from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyReportHistoryRecord


def archive_daily_report(
    db: Session,
    *,
    business_date: date,
    report_text: str,
    report_payload: dict[str, Any],
    source_snapshot: DailyFactBundleSnapshot,
    trace_id: str | None = None,
    created_by_id: int | None = None,
) -> DailyReportHistoryRecord:
    run = _source_run(db, source_snapshot)
    source_summary: dict[str, Any] = {
        "snapshot_id": source_snapshot.id,
        "run_id": source_snapshot.run_id,
        "snapshot_reason": source_snapshot.snapshot_reason,
        "payload_hash": source_snapshot.payload_hash,
        "source_status": _source_status(source_snapshot, run),
        "conflicts": source_snapshot.conflicts,
        "correction_refs": source_snapshot.correction_refs,
        "dingtalk_refs": source_snapshot.dingtalk_refs,
    }
    if run is not None and isinstance(run.source_status, dict) and run.source_status:
        source_summary["run_source_status"] = run.source_status
    row = DailyReportHistoryRecord(
        report_type="daily",
        business_date=business_date,
        period_type="day",
        period_start=business_date,
        period_end=business_date,
        source_snapshot_id=source_snapshot.id,
        source_run_id=source_snapshot.run_id,
        report_text=report_text,
        report_payload=report_payload,
        source_summary=source_summary,
        facts_hash=source_snapshot.payload_hash,
        text_hash=_hash_text(report_text),
        created_by_id=created_by_id,
        trace_id=trace_id,
    )
    db.add(row)
    db.flush()
    return row


def hash_payload(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_run(db: Session, source_snapshot: DailyFactBundleSnapshot) -> DailyFactBundleRun | None:
    if source_snapshot.run_id is None:
        return None
    return db.get(DailyFactBundleRun, source_snapshot.run_id)


def _source_status(
    source_snapshot: DailyFactBundleSnapshot,
    run: DailyFactBundleRun | None,
) -> dict[str, Any]:
    sources = source_snapshot.sources or {}
    status = sources.get("source_status") if isinstance(sources, dict) else None
    if isinstance(status, dict):
        return status

    if run is None:
        return {}
    return {"daily_fact_bundle_run": str(run.status or "unknown")}


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)
