"""经营驾驶舱聚合服务。

给 executive router 用，输入日期 → 全厂毛利 + 机列盈亏榜 + 铝价 + 趋势。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.executive import (
    AluminumPriceDaily,
    CostDailyResult,
    CostMonthlyReviewStatus,
    CostMonthlyRollup,
    CostPriceMaster,
    CostVarianceRecord,
    CostWorkshopStrategy,
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


def persist_cost_strategy_snapshot(db: Session, *, table_models: dict[str, list[dict]]) -> dict:
    saved = {
        'cost_price_master': 0,
        'cost_workshop_strategy': 0,
        'cost_daily_result': 0,
        'cost_monthly_rollup': 0,
        'cost_variance_record': 0,
    }
    if not isinstance(table_models, dict):
        raise ValueError('table_models must be an object')

    handlers = {
        'cost_price_master': _upsert_cost_price_master,
        'cost_workshop_strategy': _upsert_cost_workshop_strategy,
        'cost_daily_result': _upsert_cost_daily_result,
        'cost_monthly_rollup': _upsert_cost_monthly_rollup,
        'cost_variance_record': _upsert_cost_variance_record,
    }
    unknown_tables = sorted(set(table_models) - set(handlers))
    if unknown_tables:
        raise ValueError(f"unsupported_cost_table: {', '.join(unknown_tables)}")

    for table_name, rows in table_models.items():
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise ValueError(f'{table_name} must be a list')
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f'{table_name} rows must be objects')
            handlers[table_name](db, row)
            saved[table_name] += 1

    return {'saved': saved}


def build_cost_strategy_review_status(db: Session, *, month: str) -> dict:
    month = _required_month(month)
    rollups = list(
        db.execute(
            select(CostMonthlyRollup)
            .where(CostMonthlyRollup.month == month)
            .order_by(CostMonthlyRollup.workshop_code, CostMonthlyRollup.strategy_code)
        ).scalars().all()
    )
    statuses = {
        (row.month, row.workshop_code, row.strategy_code): row
        for row in db.execute(
            select(CostMonthlyReviewStatus).where(CostMonthlyReviewStatus.month == month)
        ).scalars().all()
    }

    rows = []
    counts = {'pending_review': 0, 'reviewed': 0, 'month_closed': 0}
    for rollup in rollups:
        status_row = statuses.get((rollup.month, rollup.workshop_code, rollup.strategy_code))
        status = status_row.status if status_row else 'pending_review'
        if status not in counts:
            status = 'pending_review'
        counts[status] += 1
        rows.append(_cost_review_status_out(rollup, status_row, status=status))

    return {
        'summary': {
            'month': month,
            'rollup_count': len(rows),
            'pending_review': counts['pending_review'],
            'reviewed': counts['reviewed'],
            'month_closed': counts['month_closed'],
        },
        'rows': rows,
    }


def update_cost_strategy_review_status(
    db: Session,
    *,
    month: str,
    workshop_code: str,
    strategy_code: str,
    action: str,
    note: Optional[str],
    operator_id: int,
) -> dict:
    month = _required_month(month)
    workshop_code = str(workshop_code or '').strip()
    strategy_code = str(strategy_code or '').strip()
    action = str(action or '').strip()
    if action not in {'review', 'close'}:
        raise ValueError('unsupported_cost_review_action')
    if not workshop_code or not strategy_code:
        raise ValueError('workshop_code and strategy_code are required')

    rollup = db.execute(
        select(CostMonthlyRollup).where(
            CostMonthlyRollup.month == month,
            CostMonthlyRollup.workshop_code == workshop_code,
            CostMonthlyRollup.strategy_code == strategy_code,
        )
    ).scalar_one_or_none()
    if rollup is None:
        raise ValueError('cost_monthly_rollup_not_found')

    status_row = db.execute(
        select(CostMonthlyReviewStatus).where(
            CostMonthlyReviewStatus.month == month,
            CostMonthlyReviewStatus.workshop_code == workshop_code,
            CostMonthlyReviewStatus.strategy_code == strategy_code,
        )
    ).scalar_one_or_none()
    if status_row is None:
        status_row = CostMonthlyReviewStatus(
            month=month,
            workshop_code=workshop_code,
            strategy_code=strategy_code,
            status='pending_review',
        )
        db.add(status_row)

    now = datetime.now(timezone.utc)
    clean_note = str(note or '').strip() or None
    if action == 'review':
        if status_row.status == 'month_closed':
            raise ValueError('cost_monthly_rollup_already_closed')
        status_row.status = 'reviewed'
        status_row.reviewed_by = operator_id
        status_row.reviewed_at = now
        status_row.review_note = clean_note
    else:
        if status_row.status != 'reviewed' or status_row.reviewed_at is None:
            raise ValueError('cost_monthly_rollup_requires_review')
        status_row.status = 'month_closed'
        status_row.closed_by = operator_id
        status_row.closed_at = now
        status_row.close_note = clean_note

    db.flush()
    return _cost_review_status_out(rollup, status_row, status=status_row.status)


def _cost_review_status_out(
    rollup: CostMonthlyRollup,
    status_row: Optional[CostMonthlyReviewStatus],
    *,
    status: str,
) -> dict:
    return {
        'month': rollup.month,
        'workshop_code': rollup.workshop_code,
        'strategy_code': rollup.strategy_code,
        'month_total_cost': _q(Decimal(str(rollup.month_total_cost or 0)), 2),
        'month_output_ton_cost': _q(Decimal(str(rollup.month_output_ton_cost or 0)), 2),
        'month_throughput_ton_cost': _q(Decimal(str(rollup.month_throughput_ton_cost or 0)), 2),
        'source': rollup.source,
        'status': status,
        'reviewed_by': status_row.reviewed_by if status_row else None,
        'reviewed_at': _iso_datetime(status_row.reviewed_at) if status_row else None,
        'closed_by': status_row.closed_by if status_row else None,
        'closed_at': _iso_datetime(status_row.closed_at) if status_row else None,
        'review_note': status_row.review_note if status_row else None,
        'close_note': status_row.close_note if status_row else None,
    }


def _upsert_cost_price_master(db: Session, row: dict[str, Any]) -> None:
    effective_from = _required_date(row, 'effective_from')
    workshop_scope = _text(row, 'workshop_scope', default='ALL')
    process_scope = _text(row, 'process_scope', default='ALL')
    values = {
        'item_code': _required_text(row, 'item_code', 'code'),
        'item_name': _required_text(row, 'item_name'),
        'unit': _required_text(row, 'unit'),
        'unit_price': _decimal(row, 'unit_price', 'unitPrice'),
        'effective_from': effective_from,
        'effective_to': _optional_date(row, 'effective_to'),
        'workshop_scope': workshop_scope,
        'process_scope': process_scope,
        'source_note': _optional_text(row, 'source_note'),
    }
    _upsert(
        db,
        CostPriceMaster,
        {
            'item_code': values['item_code'],
            'effective_from': effective_from,
            'workshop_scope': workshop_scope,
            'process_scope': process_scope,
        },
        values,
    )


def _upsert_cost_workshop_strategy(db: Session, row: dict[str, Any]) -> None:
    effective_from = _required_date(row, 'effective_from')
    values = {
        'workshop_code': _required_text(row, 'workshop_code'),
        'strategy_code': _required_text(row, 'strategy_code'),
        'enabled': _bool(row.get('enabled', True)),
        'effective_from': effective_from,
        'caliber': _text(row, 'caliber', default='output'),
        'config_snapshot': row.get('config_snapshot'),
    }
    _upsert(
        db,
        CostWorkshopStrategy,
        {
            'workshop_code': values['workshop_code'],
            'strategy_code': values['strategy_code'],
            'effective_from': effective_from,
        },
        values,
    )


def _upsert_cost_daily_result(db: Session, row: dict[str, Any]) -> None:
    business_date = _required_date(row, 'business_date')
    caliber = _text(row, 'caliber', default='output')
    values = {
        'business_date': business_date,
        'workshop_code': _required_text(row, 'workshop_code'),
        'strategy_code': _required_text(row, 'strategy_code'),
        'total_cost': _decimal(row, 'total_cost'),
        'output_ton_cost': _decimal(row, 'output_ton_cost'),
        'throughput_ton_cost': _decimal(row, 'throughput_ton_cost'),
        'caliber': caliber,
        'breakdown_count': _integer(row, 'breakdown_count'),
        'process_count': _integer(row, 'process_count'),
    }
    _upsert(
        db,
        CostDailyResult,
        {
            'business_date': business_date,
            'workshop_code': values['workshop_code'],
            'strategy_code': values['strategy_code'],
            'caliber': caliber,
        },
        values,
    )


def _upsert_cost_monthly_rollup(db: Session, row: dict[str, Any]) -> None:
    values = {
        'month': _required_text(row, 'month'),
        'workshop_code': _required_text(row, 'workshop_code'),
        'strategy_code': _required_text(row, 'strategy_code'),
        'month_total_cost': _decimal(row, 'month_total_cost'),
        'month_output_ton_cost': _decimal(row, 'month_output_ton_cost'),
        'month_throughput_ton_cost': _decimal(row, 'month_throughput_ton_cost'),
        'source': _text(row, 'source', default='frontend_strategy_snapshot'),
    }
    _upsert(
        db,
        CostMonthlyRollup,
        {
            'month': values['month'],
            'workshop_code': values['workshop_code'],
            'strategy_code': values['strategy_code'],
        },
        values,
    )


def _upsert_cost_variance_record(db: Session, row: dict[str, Any]) -> None:
    business_date = _required_date(row, 'business_date')
    values = {
        'business_date': business_date,
        'workshop_code': _required_text(row, 'workshop_code'),
        'variance_type': _required_text(row, 'variance_type'),
        'baseline_value': _decimal(row, 'baseline_value'),
        'current_value': _decimal(row, 'current_value'),
        'diff_value': _decimal(row, 'diff_value'),
        'status': _text(row, 'status', default='normal'),
    }
    _upsert(
        db,
        CostVarianceRecord,
        {
            'business_date': business_date,
            'workshop_code': values['workshop_code'],
            'variance_type': values['variance_type'],
        },
        values,
    )


def _upsert(db: Session, model: type, key_values: dict[str, Any], values: dict[str, Any]) -> None:
    stmt = select(model)
    for field, value in key_values.items():
        stmt = stmt.where(getattr(model, field) == value)
    rec = db.execute(stmt).scalar_one_or_none()
    if rec is None:
        db.add(model(**values))
        return
    for field, value in values.items():
        setattr(rec, field, value)


def _get(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return default


def _required_text(row: dict[str, Any], *keys: str) -> str:
    value = _get(row, *keys)
    text = str(value or '').strip()
    if not text:
        raise ValueError(f"{'/'.join(keys)} is required")
    return text


def _optional_text(row: dict[str, Any], key: str) -> Optional[str]:
    text = str(row.get(key) or '').strip()
    return text or None


def _text(row: dict[str, Any], key: str, *, default: str) -> str:
    text = str(row.get(key) or '').strip()
    return text or default


def _required_date(row: dict[str, Any], key: str) -> date:
    value = row.get(key)
    if isinstance(value, date):
        return value
    text = str(value or '').strip()
    if not text:
        raise ValueError(f'{key} is required')
    return date.fromisoformat(text)


def _optional_date(row: dict[str, Any], key: str) -> Optional[date]:
    value = row.get(key)
    if value in (None, ''):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def _required_month(value: str) -> str:
    month = str(value or '').strip()
    if len(month) != 7:
        raise ValueError('month must be YYYY-MM')
    date.fromisoformat(f'{month}-01')
    return month


def _decimal(row: dict[str, Any], *keys: str) -> Decimal:
    value = _get(row, *keys, default=0)
    if value in (None, ''):
        value = 0
    return Decimal(str(value))


def _integer(row: dict[str, Any], key: str) -> int:
    value = row.get(key, 0)
    if value in (None, ''):
        value = 0
    return int(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {'0', 'false', 'no', 'off'}
    return bool(value)


def _q(v: Optional[Decimal], digits: int) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(round(v, digits))
    except Exception:
        return None


def _iso_datetime(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


__all__ = [
    'build_executive_dashboard',
    'build_machine_ranking',
    'build_aluminum_price_trend',
    'persist_cost_strategy_snapshot',
    'build_cost_strategy_review_status',
    'update_cost_strategy_review_status',
]
