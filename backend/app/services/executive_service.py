"""经营驾驶舱聚合服务。

给 executive router 用，输入日期 → 全厂毛利 + 机列盈亏榜 + 铝价 + 趋势。
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.executive import (
    AluminumPriceDaily,
    MachineDailyCostSnapshot,
    MachineDailyProfitSnapshot,
)
from app.models.master import Workshop


def build_executive_dashboard(db: Session, *, business_date: date) -> dict:
    snapshots = list(
        db.execute(
            select(MachineDailyProfitSnapshot).where(
                MachineDailyProfitSnapshot.business_date == business_date
            )
        ).scalars().all()
    )

    total_revenue = Decimal('0')
    total_cost = Decimal('0')
    total_profit = Decimal('0')
    total_tons = Decimal('0')
    workshops_pnl: dict[int, dict] = {}

    for s in snapshots:
        total_revenue += Decimal(str(s.processing_revenue or 0))
        total_cost += Decimal(str(s.total_cost or 0))
        if s.gross_profit is not None:
            total_profit += Decimal(str(s.gross_profit))
        if s.output_tons is not None:
            total_tons += Decimal(str(s.output_tons))
        entry = workshops_pnl.setdefault(
            s.workshop_id,
            {
                'workshop_id': s.workshop_id,
                'revenue': Decimal('0'),
                'cost': Decimal('0'),
                'profit': Decimal('0'),
                'output_tons': Decimal('0'),
                'has_missing_fee_rule': False,
            },
        )
        entry['revenue'] += Decimal(str(s.processing_revenue or 0))
        entry['cost'] += Decimal(str(s.total_cost or 0))
        if s.gross_profit is not None:
            entry['profit'] += Decimal(str(s.gross_profit))
        if s.output_tons is not None:
            entry['output_tons'] += Decimal(str(s.output_tons))
        if s.has_missing_fee_rule:
            entry['has_missing_fee_rule'] = True

    # 补车间名
    workshops_map = {
        w.id: w for w in db.execute(select(Workshop).where(Workshop.id.in_(workshops_pnl.keys()))).scalars().all()
    }
    workshops_out = []
    for wid, entry in workshops_pnl.items():
        ws = workshops_map.get(wid)
        workshops_out.append({
            **entry,
            'workshop_code': ws.code if ws else None,
            'workshop_name': ws.name if ws else f'#{wid}',
        })
    workshops_out.sort(key=lambda x: x['profit'], reverse=True)

    # 昨日对比
    yesterday = business_date - timedelta(days=1)
    prev_profit = db.execute(
        select(MachineDailyProfitSnapshot).where(
            MachineDailyProfitSnapshot.business_date == yesterday
        )
    ).scalars().all()
    prev_total_profit = sum(
        (Decimal(str(p.gross_profit or 0)) for p in prev_profit),
        Decimal('0'),
    )
    vs_delta = total_profit - prev_total_profit
    vs_delta_pct = (
        (vs_delta / prev_total_profit * Decimal('100'))
        if prev_total_profit != 0
        else None
    )

    # 月累计（本月 1 号至 business_date）
    month_start = business_date.replace(day=1)
    month_snapshots = db.execute(
        select(MachineDailyProfitSnapshot).where(
            MachineDailyProfitSnapshot.business_date >= month_start,
            MachineDailyProfitSnapshot.business_date <= business_date,
        )
    ).scalars().all()
    mtd_revenue = sum((Decimal(str(s.processing_revenue or 0)) for s in month_snapshots), Decimal('0'))
    mtd_cost = sum((Decimal(str(s.total_cost or 0)) for s in month_snapshots), Decimal('0'))
    mtd_profit = sum(
        (Decimal(str(s.gross_profit or 0)) for s in month_snapshots if s.gross_profit is not None),
        Decimal('0'),
    )

    # 铝价
    al = db.execute(
        select(AluminumPriceDaily).where(AluminumPriceDaily.price_date <= business_date)
        .order_by(AluminumPriceDaily.price_date.desc()).limit(2)
    ).scalars().all()
    al_today = al[0] if len(al) > 0 else None
    al_prev = al[1] if len(al) > 1 else None

    profit_margin = (
        (total_profit / total_revenue * Decimal('100')) if total_revenue > 0 else None
    )

    is_estimated = any(s.is_estimated for s in snapshots) if snapshots else True
    has_missing = any(s.has_missing_fee_rule for s in snapshots)

    return {
        'business_date': business_date.isoformat(),
        'total_output_tons': _q(total_tons, 3),
        'total_revenue': _q(total_revenue, 2),
        'total_cost': _q(total_cost, 2),
        'total_profit': _q(total_profit, 2),
        'profit_margin_pct': _q(profit_margin, 2) if profit_margin is not None else None,
        'vs_yesterday_profit_delta': _q(vs_delta, 2),
        'vs_yesterday_profit_delta_pct': _q(vs_delta_pct, 2) if vs_delta_pct is not None else None,
        'mtd_revenue': _q(mtd_revenue, 2),
        'mtd_cost': _q(mtd_cost, 2),
        'mtd_profit': _q(mtd_profit, 2),
        'workshops': [
            {
                'workshop_id': w['workshop_id'],
                'workshop_code': w['workshop_code'],
                'workshop_name': w['workshop_name'],
                'output_tons': _q(w['output_tons'], 3),
                'revenue': _q(w['revenue'], 2),
                'cost': _q(w['cost'], 2),
                'profit': _q(w['profit'], 2),
                'has_missing_fee_rule': w['has_missing_fee_rule'],
            }
            for w in workshops_out
        ],
        'aluminum_price': {
            'price_date': al_today.price_date.isoformat() if al_today else None,
            'price_per_ton': _q(Decimal(str(al_today.price_per_ton)), 2) if al_today else None,
            'delta_vs_prev': (
                _q(Decimal(str(al_today.price_per_ton)) - Decimal(str(al_prev.price_per_ton)), 2)
                if al_today and al_prev
                else None
            ),
        },
        'is_estimated': is_estimated,
        'has_missing_fee_rule': has_missing,
        'estimation_note': (
            '阶段 1：±20%精度，按车间粒度 × 默认合金映射。'
            '阶段 2 引入核算员日报录入后升级至 ±3% 并按机列拆分。'
        ),
    }


def build_machine_ranking(db: Session, *, business_date: date) -> list[dict]:
    snapshots = list(
        db.execute(
            select(MachineDailyProfitSnapshot).where(
                MachineDailyProfitSnapshot.business_date == business_date
            ).order_by(MachineDailyProfitSnapshot.gross_profit.desc().nullslast())
        ).scalars().all()
    )
    ws_map = {
        w.id: w
        for w in db.execute(select(Workshop)).scalars().all()
    }
    result = []
    for s in snapshots:
        ws = ws_map.get(s.workshop_id)
        result.append({
            'workshop_id': s.workshop_id,
            'workshop_code': ws.code if ws else None,
            'workshop_name': ws.name if ws else f'#{s.workshop_id}',
            'machine_line_id': s.machine_line_id,
            'alloy_grade': s.alloy_grade,
            'process_type': s.process_type,
            'output_tons': _q(Decimal(str(s.output_tons)), 3) if s.output_tons is not None else None,
            'processing_fee_per_ton': _q(Decimal(str(s.processing_fee_per_ton)), 2) if s.processing_fee_per_ton is not None else None,
            'revenue': _q(Decimal(str(s.processing_revenue or 0)), 2),
            'cost': _q(Decimal(str(s.total_cost or 0)), 2),
            'gross_profit': _q(Decimal(str(s.gross_profit)), 2) if s.gross_profit is not None else None,
            'gross_margin_pct': _q(Decimal(str(s.gross_margin_pct)), 2) if s.gross_margin_pct is not None else None,
            'has_missing_fee_rule': s.has_missing_fee_rule,
            'is_estimated': s.is_estimated,
            'note': s.estimation_note,
        })
    return result


def build_aluminum_price_trend(db: Session, *, days: int = 30) -> list[dict]:
    rows = list(
        db.execute(
            select(AluminumPriceDaily).order_by(AluminumPriceDaily.price_date.desc()).limit(days)
        ).scalars().all()
    )
    rows.reverse()
    return [
        {
            'price_date': r.price_date.isoformat(),
            'price_per_ton': _q(Decimal(str(r.price_per_ton)), 2),
            'source': r.source,
        }
        for r in rows
    ]


def _q(v: Optional[Decimal], digits: int) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(round(v, digits))
    except Exception:
        return None


__all__ = [
    'build_executive_dashboard',
    'build_machine_ranking',
    'build_aluminum_price_trend',
]
