"""§3.7 recovery owner-agent — single-row daily upsert keyed on business_date."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.production import RecoveryDaily


def upsert_daily(
    db: Session,
    *,
    business_date: date,
    recovery_output_tons: float | None,
    note: str | None,
) -> RecoveryDaily:
    row = db.query(RecoveryDaily).filter(RecoveryDaily.business_date == business_date).one_or_none()
    if row is None:
        row = RecoveryDaily(business_date=business_date)
        db.add(row)
    row.recovery_output_tons = recovery_output_tons
    row.note = note
    db.flush()
    return row
