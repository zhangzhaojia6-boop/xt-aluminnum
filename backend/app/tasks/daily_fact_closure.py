from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.business_time import last_completed_production_business_date
from app.database import get_sessionmaker
from app.services.report.daily_fact_bundle import build_daily_fact_bundle


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
