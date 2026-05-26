"""§3.4 planning (计划内勤) owner-agent.

Writes:
- ``production_plan_daily`` (one row per business_date×workshop)
- ``alloy_spec_breakdown`` (replace-all detail rows per business_date×workshop)
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, TypedDict

from sqlalchemy.orm import Session

from app.models.production import AlloySpecBreakdown, ProductionPlanDaily


class AlloyBreakdownRow(TypedDict, total=False):
    alloy_grade: str
    spec_text: str | None
    weight_tons: float | None
    scrap_count_casting1: int | None
    scrap_count_casting2: int | None


def upsert_plan(
    db: Session,
    *,
    business_date: date,
    workshop_code: str,
    input_daily: float | None,
    input_monthly: float | None,
    contract_today: float | None,
    contract_total_remaining: float | None,
    billet_total: float | None,
) -> ProductionPlanDaily:
    row = (
        db.query(ProductionPlanDaily)
        .filter(
            ProductionPlanDaily.business_date == business_date,
            ProductionPlanDaily.workshop_code == workshop_code,
        )
        .one_or_none()
    )
    if row is None:
        row = ProductionPlanDaily(business_date=business_date, workshop_code=workshop_code)
        db.add(row)
    row.input_daily = input_daily
    row.input_monthly = input_monthly
    row.contract_today = contract_today
    row.contract_total_remaining = contract_total_remaining
    row.billet_total = billet_total
    db.flush()
    return row


def replace_alloy_breakdown(
    db: Session,
    *,
    business_date: date,
    workshop_code: str,
    rows: Iterable[AlloyBreakdownRow],
) -> list[AlloySpecBreakdown]:
    db.query(AlloySpecBreakdown).filter(
        AlloySpecBreakdown.business_date == business_date,
        AlloySpecBreakdown.workshop_code == workshop_code,
    ).delete(synchronize_session=False)

    created: list[AlloySpecBreakdown] = []
    for raw in rows:
        item = AlloySpecBreakdown(
            business_date=business_date,
            workshop_code=workshop_code,
            alloy_grade=raw['alloy_grade'],
            spec_text=raw.get('spec_text'),
            weight_tons=raw.get('weight_tons'),
            scrap_count_casting1=raw.get('scrap_count_casting1'),
            scrap_count_casting2=raw.get('scrap_count_casting2'),
        )
        db.add(item)
        created.append(item)
    db.flush()
    return created
