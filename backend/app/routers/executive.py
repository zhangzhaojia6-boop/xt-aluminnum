"""孟总经营驾驶舱 API。

- GET /executive/dashboard              昨日 / 指定日毛利概览
- GET /executive/machine-ranking        机列盈亏榜
- GET /executive/aluminum-price-trend   铝价 N 天走势
- GET /executive/processing-fees        加工费规则列表（admin 可改）
- POST/PUT/DELETE 加工费规则（admin）
- POST /executive/recompute             手动触发当日成本+利润重算（admin）
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.aluminum_price_fetcher import aluminum_price_fetcher_agent
from app.agents.cost_aggregator import cost_aggregator_agent
from app.agents.profit_snapshot import profit_snapshot_agent
from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
from app.models.executive import (
    AluminumPriceDaily,
    ProcessingFeeRule,
    ProcessingFeeSurcharge,
)
from app.models.system import User
from app.services import executive_service


router = APIRouter(tags=['executive'])


def _ensure_view_access(user: User) -> None:
    summary = build_scope_summary(user)
    if not bool(summary.is_admin or summary.is_manager or summary.is_reviewer):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Executive dashboard access denied')


def _ensure_admin(user: User) -> None:
    summary = build_scope_summary(user)
    if not summary.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin required')


def _resolve_business_date(q: Optional[str]) -> date:
    if q:
        return date.fromisoformat(q)
    # 默认取昨日
    return date.today() - timedelta(days=1)


@router.get('/dashboard')
def dashboard(
    date_str: Optional[str] = Query(default=None, alias='date'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_view_access(current_user)
    business_date = _resolve_business_date(date_str)
    return executive_service.build_executive_dashboard(db, business_date=business_date)


@router.get('/machine-ranking')
def machine_ranking(
    date_str: Optional[str] = Query(default=None, alias='date'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_view_access(current_user)
    business_date = _resolve_business_date(date_str)
    return executive_service.build_machine_ranking(db, business_date=business_date)


@router.get('/aluminum-price-trend')
def aluminum_price_trend(
    days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_view_access(current_user)
    return executive_service.build_aluminum_price_trend(db, days=days)


class ProcessingFeeRuleOut(BaseModel):
    id: int
    customer_tier: str
    alloy_grade: str
    process_type: str
    temper: Optional[str] = None
    thickness_min_mm: Optional[float] = None
    thickness_max_mm: Optional[float] = None
    fee_per_ton: float
    is_vat_inclusive: bool
    effective_from: date
    effective_to: Optional[date] = None
    note: Optional[str] = None


class ProcessingFeeRuleIn(BaseModel):
    customer_tier: str = 'default'
    alloy_grade: str
    process_type: str
    temper: Optional[str] = None
    thickness_min_mm: Optional[float] = None
    thickness_max_mm: Optional[float] = None
    fee_per_ton: float = Field(gt=0)
    is_vat_inclusive: bool = True
    effective_from: date
    effective_to: Optional[date] = None
    note: Optional[str] = None


class CostStrategySnapshotIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    table_models: dict[str, list[dict]] = Field(default_factory=dict, alias='tableModels')


class CostReviewStatusUpdateIn(BaseModel):
    month: str
    workshop_code: str
    strategy_code: str
    action: str = Field(pattern='^(review|close)$')
    note: Optional[str] = None


@router.get('/processing-fees', response_model=list[ProcessingFeeRuleOut])
def list_processing_fees(
    customer_tier: Optional[str] = None,
    effective_on: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProcessingFeeRuleOut]:
    _ensure_view_access(current_user)
    stmt = select(ProcessingFeeRule)
    if customer_tier:
        stmt = stmt.where(ProcessingFeeRule.customer_tier == customer_tier)
    if effective_on:
        stmt = stmt.where(ProcessingFeeRule.effective_from <= effective_on)
    rows = db.execute(stmt.order_by(
        ProcessingFeeRule.customer_tier,
        ProcessingFeeRule.alloy_grade,
        ProcessingFeeRule.process_type,
        ProcessingFeeRule.thickness_min_mm,
    )).scalars().all()
    if effective_on:
        rows = [r for r in rows if r.effective_to is None or r.effective_to >= effective_on]
    return [
        ProcessingFeeRuleOut(
            id=r.id,
            customer_tier=r.customer_tier,
            alloy_grade=r.alloy_grade,
            process_type=r.process_type,
            temper=r.temper,
            thickness_min_mm=float(r.thickness_min_mm) if r.thickness_min_mm is not None else None,
            thickness_max_mm=float(r.thickness_max_mm) if r.thickness_max_mm is not None else None,
            fee_per_ton=float(r.fee_per_ton),
            is_vat_inclusive=r.is_vat_inclusive,
            effective_from=r.effective_from,
            effective_to=r.effective_to,
            note=r.note,
        )
        for r in rows
    ]


@router.post('/processing-fees', response_model=ProcessingFeeRuleOut)
def create_processing_fee(
    body: ProcessingFeeRuleIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessingFeeRuleOut:
    _ensure_admin(current_user)
    rec = ProcessingFeeRule(
        **body.model_dump(),
        created_by=current_user.id,
    )
    db.add(rec)
    db.flush()
    db.commit()
    return ProcessingFeeRuleOut.model_validate(rec.__dict__)


@router.put('/processing-fees/{rule_id}', response_model=ProcessingFeeRuleOut)
def update_processing_fee(
    rule_id: int,
    body: ProcessingFeeRuleIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessingFeeRuleOut:
    _ensure_admin(current_user)
    rec = db.get(ProcessingFeeRule, rule_id)
    if rec is None:
        raise HTTPException(status_code=404, detail='rule not found')
    for k, v in body.model_dump().items():
        setattr(rec, k, v)
    db.flush()
    db.commit()
    return ProcessingFeeRuleOut.model_validate(rec.__dict__)


@router.delete('/processing-fees/{rule_id}')
def delete_processing_fee(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_admin(current_user)
    rec = db.get(ProcessingFeeRule, rule_id)
    if rec is None:
        raise HTTPException(status_code=404, detail='rule not found')
    db.delete(rec)
    db.commit()
    return {'ok': True}


@router.post('/recompute')
def recompute(
    date_str: Optional[str] = Query(default=None, alias='date'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_admin(current_user)
    business_date = _resolve_business_date(date_str)
    agg_decisions = cost_aggregator_agent.execute(db=db, target_date=business_date)
    db.flush()
    profit_decisions = profit_snapshot_agent.execute(db=db, target_date=business_date)
    db.commit()
    return {
        'business_date': business_date.isoformat(),
        'cost_aggregated': len(agg_decisions),
        'profit_snapshots': len(profit_decisions),
    }


@router.post('/cost-strategy-snapshots')
def persist_cost_strategy_snapshot(
    body: CostStrategySnapshotIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_admin(current_user)
    try:
        result = executive_service.persist_cost_strategy_snapshot(
            db,
            table_models=body.table_models,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return result


@router.get('/cost-strategy-snapshots/review-status')
def cost_strategy_review_status(
    month: str = Query(..., min_length=7, max_length=7),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_view_access(current_user)
    try:
        return executive_service.build_cost_strategy_review_status(db, month=month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post('/cost-strategy-snapshots/review-status')
def update_cost_strategy_review_status(
    body: CostReviewStatusUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_admin(current_user)
    try:
        result = executive_service.update_cost_strategy_review_status(
            db,
            month=body.month,
            workshop_code=body.workshop_code,
            strategy_code=body.strategy_code,
            action=body.action,
            note=body.note,
            operator_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return result


@router.post('/aluminum-price/fetch')
def fetch_aluminum_price(
    date_str: Optional[str] = Query(default=None, alias='date'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_admin(current_user)
    target = date.fromisoformat(date_str) if date_str else date.today()
    decisions = aluminum_price_fetcher_agent.execute(db=db, target_date=target)
    db.commit()
    latest = db.execute(
        select(AluminumPriceDaily).where(AluminumPriceDaily.price_date == target)
    ).scalar_one_or_none()
    return {
        'target_date': target.isoformat(),
        'fetched': bool(latest and latest.fetched_at),
        'price_per_ton': float(latest.price_per_ton) if latest else None,
        'decisions': len(decisions),
    }
