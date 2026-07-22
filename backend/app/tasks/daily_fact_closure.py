from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.business_time import last_completed_production_business_date
from app.database import get_sessionmaker
from app.services.report.daily_fact_bundle import build_daily_fact_bundle
from app.services.report.daily_fact_gap_closure_service import (
    list_open_daily_fact_gap_dates,
    sync_daily_fact_gap_events,
)


LOGGER = logging.getLogger(__name__)


def run_daily_fact_closure(
    db: Session,
    *,
    target_date: date | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    business_date = target_date or last_completed_production_business_date(now)
    trace_id = f"daily-fact-closure:{business_date.isoformat()}"
    try:
        bundle = build_daily_fact_bundle(
            db,
            business_date=business_date,
            trace_id=trace_id,
            persist_run=True,
            snapshot_reason="scheduled_daily_closure",
            allow_output_skill_reference_adoption=False,
            now=now,
        )
        sync_daily_fact_gap_events(
            db,
            business_date=business_date,
            bundle=bundle,
            trace_id=trace_id,
            now=now,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "business_date": business_date.isoformat(),
        "trace_id": trace_id,
        "status": bundle["fact_closure"]["status"],
    }


def run_scheduled_daily_fact_closure() -> dict[str, Any]:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        return run_daily_fact_closure(session)


def run_startup_daily_fact_closure(*, now: datetime) -> dict[str, Any]:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        return run_daily_fact_closure(session, now=now)


def run_daily_fact_gap_refresh_for_date(*, target_date: date) -> dict[str, Any]:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        return run_daily_fact_closure(session, target_date=target_date)


def run_open_daily_fact_gap_refresh() -> dict[str, Any]:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        business_dates = list_open_daily_fact_gap_dates(session)
        results: list[dict[str, Any]] = []
        for business_date in business_dates:
            try:
                results.append(run_daily_fact_closure(session, target_date=business_date))
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                LOGGER.exception(
                    "daily_fact_gap_refresh_failed business_date=%s",
                    business_date.isoformat(),
                )
                results.append({
                    "business_date": business_date.isoformat(),
                    "status": "failed",
                    "error": exc.__class__.__name__,
                })
        return {
            "status": "partial" if any(item.get("status") == "failed" for item in results) else "pass",
            "checked_dates": len(business_dates),
            "results": results,
        }
