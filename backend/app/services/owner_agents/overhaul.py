"""§3.8 overhaul owner-agent — single-row daily upsert keyed on business_date."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.production import OverhaulDaily


def upsert_daily(
    db: Session,
    *,
    business_date: date,
    roller_grind_count: int | None,
    energy_kwh: float | None,
    gas_m3: float | None,
    note: str | None,
) -> OverhaulDaily:
    row = db.query(OverhaulDaily).filter(OverhaulDaily.business_date == business_date).one_or_none()
    if row is None:
        row = OverhaulDaily(business_date=business_date)
        db.add(row)
    row.roller_grind_count = roller_grind_count
    row.energy_kwh = energy_kwh
    row.gas_m3 = gas_m3
    row.note = note
    db.flush()
    return row
