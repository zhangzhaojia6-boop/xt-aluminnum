from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

from app.core.business_time import last_completed_production_business_date, local_now
from app.database import get_sessionmaker
from app.models.reports import DailyReport
from app.services.report.daily_fact_bundle import _conflict_blocks_ready, build_daily_fact_bundle
from app.services.report.daily_fact_gap_closure_service import (
    list_open_daily_fact_gap_dates,
    sync_daily_fact_gap_events,
)
from app.services.report.template_daily_report import apply_template_daily_report_to_report
from app.tasks.daily_report import generate_daily_reports

LOGGER = logging.getLogger(__name__)
REPORT_RELEASE_TIME = time(10, 0)
REPORT_REFRESH_OPEN_GAPS_KEY = "gap_refresh_open_gaps"


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
            allow_datahub_final_reference=False,
            now=now,
        )
        gap_result = sync_daily_fact_gap_events(
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
        "open_gaps": int(gap_result.get("open") or 0),
        "release_ready": (
            bundle["fact_closure"]["status"] == "pass"
            and int(gap_result.get("open") or 0) == 0
            and not any(_conflict_blocks_ready(item) for item in bundle.get("conflicts") or [])
        ),
    }


def run_scheduled_daily_fact_closure() -> dict[str, Any]:
    checked_at = local_now()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        result = run_daily_fact_closure(session, now=checked_at)
    return _release_daily_report_if_ready(result, checked_at=checked_at)


def run_startup_daily_fact_closure(*, now: datetime) -> dict[str, Any]:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        result = run_daily_fact_closure(session, now=now)
    return _release_daily_report_if_ready(result, checked_at=local_now(now))


def run_daily_fact_gap_refresh_for_date(
    *,
    target_date: date,
    now: datetime | None = None,
) -> dict[str, Any]:
    checked_at = local_now(now)
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        result = run_daily_fact_closure(session, target_date=target_date, now=checked_at)
    return _release_daily_report_if_ready(result, checked_at=checked_at)


def run_open_daily_fact_gap_refresh() -> dict[str, Any]:
    checked_at = local_now()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        business_dates = list_open_daily_fact_gap_dates(session)
        current_business_date = last_completed_production_business_date(checked_at)
        if (
            checked_at.time() >= REPORT_RELEASE_TIME
            and current_business_date not in business_dates
            and _daily_report_release_pending(session, target_date=current_business_date)
        ):
            business_dates.append(current_business_date)

    results: list[dict[str, Any]] = []
    for business_date in business_dates:
        try:
            results.append(
                run_daily_fact_gap_refresh_for_date(
                    target_date=business_date,
                    now=checked_at,
                )
            )
        except Exception as exc:
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


def _release_daily_report_if_ready(
    result: dict[str, Any],
    *,
    checked_at: datetime,
) -> dict[str, Any]:
    if not result.get("release_ready"):
        _refresh_blocked_report_row(result, checked_at=checked_at)
        return result
    if checked_at.time() < REPORT_RELEASE_TIME:
        return {
            **result,
            "report_release": {"status": "waiting_for_cutoff", "cutoff": "10:00"},
        }
    business_date = date.fromisoformat(str(result["business_date"]))
    return {
        **result,
        "report_release": generate_daily_reports(target_date=business_date),
    }


def _refresh_blocked_report_row(result: dict[str, Any], *, checked_at: datetime) -> None:
    """Keep a blocked report's facts current after 10:00; never publishes or delivers."""
    open_gaps = result.get("open_gaps")
    if open_gaps is None or checked_at.time() < REPORT_RELEASE_TIME:
        return
    target_date = date.fromisoformat(str(result["business_date"]))
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        report = (
            session.query(DailyReport)
            .filter(
                DailyReport.report_date == target_date,
                DailyReport.report_type == "production",
            )
            .order_by(DailyReport.published_at.desc().nullslast(), DailyReport.id.desc())
            .first()
        )
        if report is None or report.delivery_ready or report.status != "draft":
            return
        report_data = report.report_data if isinstance(report.report_data, dict) else {}
        recorded = report_data.get(REPORT_REFRESH_OPEN_GAPS_KEY)
        if recorded is None:
            template = report_data.get("template_daily_report") or {}
            recorded = len(template.get("missing_fields") or [])
        if recorded == open_gaps:
            return
        payload = apply_template_daily_report_to_report(
            session,
            report=report,
            target_date=target_date,
            allow_datahub_final_reference=False,
            use_fact_bundle=True,
        )
        if payload.get("status") == "ready":
            session.rollback()
            return
        report.report_data = {
            **report.report_data,
            REPORT_REFRESH_OPEN_GAPS_KEY: open_gaps,
            "daily_report_product": {
                **(report.report_data.get("daily_report_product") or {}),
                "status": payload.get("status"),
                "missing_fields": payload.get("missing_fields") or [],
            },
        }
        session.commit()


def _daily_report_release_pending(db: Session, *, target_date: date) -> bool:
    report = (
        db.query(DailyReport)
        .filter(
            DailyReport.report_date == target_date,
            DailyReport.report_type == "production",
        )
        .order_by(DailyReport.published_at.desc().nullslast(), DailyReport.id.desc())
        .first()
    )
    if report is None or not report.delivery_ready:
        return True
    report_data = report.report_data if isinstance(report.report_data, dict) else {}
    delivery = report_data.get("scheduled_daily_report_delivery")
    if not isinstance(delivery, dict):
        return True
    return not (
        delivery.get("outbox_message_id")
        or delivery.get("status") in {"disabled", "blocked_recipient"}
    )
