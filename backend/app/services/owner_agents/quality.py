"""§3.3 quality (质检内勤) owner-agent.

Writes:
- ``quality_yield_daily`` (one row per business_date×workshop)
- ``quality_issue_log`` (append-only detail rows; exposed as a thin add helper)
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.quality import QualityIssueLog, QualityYieldDaily


def upsert_yield(
    db: Session,
    *,
    business_date: date,
    workshop_code: str,
    yield_daily: float | None = None,
    yield_monthly: float | None = None,
    yield_target_m: float | None = None,
    yield_target_p_casting: float | None = None,
    yield_target_p_hot_roll: float | None = None,
    yield_overall_company: float | None = None,
    variance_arrow: str | None = None,
) -> QualityYieldDaily:
    row = (
        db.query(QualityYieldDaily)
        .filter(
            QualityYieldDaily.business_date == business_date,
            QualityYieldDaily.workshop_code == workshop_code,
        )
        .one_or_none()
    )
    if row is None:
        row = QualityYieldDaily(business_date=business_date, workshop_code=workshop_code)
        db.add(row)
    row.yield_daily = yield_daily
    row.yield_monthly = yield_monthly
    row.yield_target_m = yield_target_m
    row.yield_target_p_casting = yield_target_p_casting
    row.yield_target_p_hot_roll = yield_target_p_hot_roll
    row.yield_overall_company = yield_overall_company
    row.variance_arrow = variance_arrow
    db.flush()
    return row


def add_issue(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None = None,
    shift_report_id: int | None = None,
    tracking_card_no: str | None = None,
    quality_issue_type: str | None = None,
    quality_issue_desc: str | None = None,
    quality_photo_path: str | None = None,
    reported_by: int | None = None,
) -> QualityIssueLog:
    item = QualityIssueLog(
        business_date=business_date,
        workshop_id=workshop_id,
        shift_report_id=shift_report_id,
        tracking_card_no=tracking_card_no,
        quality_issue_type=quality_issue_type,
        quality_issue_desc=quality_issue_desc,
        quality_photo_path=quality_photo_path,
        reported_by=reported_by,
    )
    db.add(item)
    db.flush()
    return item
