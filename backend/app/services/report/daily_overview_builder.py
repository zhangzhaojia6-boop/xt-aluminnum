from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.master import Workshop
from app.models.mes import MesCoilSnapshot
from app.models.production import WorkOrder, WorkOrderEntry
from app.services import energy_service
from app.services.report._utils import _to_float


DEFAULT_ELECTRICITY_PRICE = 0.65
DEFAULT_GAS_PRICE = 3.60


def _workshop_map(db: Session) -> dict[int, str]:
    return {w.id: w.name for w in db.query(Workshop).filter(Workshop.is_active.is_(True)).all()}


def _round2(v: float | None) -> float | None:
    if v is None:
        return None
    return round(v, 2)


def _delta(today: float | None, yesterday: float | None) -> float | None:
    if today is None or yesterday is None:
        return None
    return round(today - yesterday, 2)


def _query_output_by_workshop(db: Session, start: date, end: date) -> dict[int, float]:
    rows = (
        db.query(
            WorkOrderEntry.workshop_id,
            func.sum(WorkOrderEntry.output_weight),
        )
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
        )
        .group_by(WorkOrderEntry.workshop_id)
        .all()
    )
    result: dict[int, float] = {}
    for wid, total in rows:
        if wid is None:
            continue
        result[wid] = _to_float(total) / 1000
    return result


def _query_input_output_by_workshop(db: Session, start: date, end: date) -> dict[int, dict]:
    rows = (
        db.query(
            WorkOrderEntry.workshop_id,
            func.sum(WorkOrderEntry.input_weight),
            func.sum(WorkOrderEntry.output_weight),
        )
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
        )
        .group_by(WorkOrderEntry.workshop_id)
        .all()
    )
    result: dict[int, dict] = {}
    for wid, inp, out in rows:
        if wid is None:
            continue
        result[wid] = {
            'input': _to_float(inp) / 1000,
            'output': _to_float(out) / 1000,
        }
    return result


def _build_workshop_output(db: Session, target_date: date, ws_map: dict[int, str]) -> list[dict]:
    today = _query_output_by_workshop(db, target_date, target_date)
    yesterday = _query_output_by_workshop(db, target_date - timedelta(days=1), target_date - timedelta(days=1))
    month_start = target_date.replace(day=1)
    monthly = _query_output_by_workshop(db, month_start, target_date)

    rows = []
    all_ids = set(today) | set(monthly)
    for wid in sorted(all_ids, key=lambda w: -(today.get(w, 0))):
        name = ws_map.get(wid, f'车间{wid}')
        d = _round2(today.get(wid, 0))
        m = _round2(monthly.get(wid, 0))
        yd = _round2(yesterday.get(wid, 0))
        rows.append({
            'workshop_id': wid,
            'workshop': name,
            'daily_output': d,
            'monthly_output': m,
            'yesterday_output': yd,
            'delta': _delta(d, yd),
        })
    return rows


def _build_wip_distribution(db: Session) -> list[dict]:
    rows = (
        db.query(
            MesCoilSnapshot.current_workshop,
            func.count(MesCoilSnapshot.id),
            func.sum(MesCoilSnapshot.material_weight),
        )
        .filter(
            MesCoilSnapshot.current_workshop.isnot(None),
            MesCoilSnapshot.current_workshop != '',
        )
        .group_by(MesCoilSnapshot.current_workshop)
        .all()
    )
    result = []
    for workshop, count, weight in rows:
        w = _to_float(weight) / 1000
        result.append({
            'workshop': workshop,
            'coil_count': count or 0,
            'total_weight': _round2(w),
        })
    result.sort(key=lambda x: -(x['total_weight'] or 0))
    return result


def _build_yield_rates(db: Session, target_date: date) -> dict:
    today_data = _query_input_output_by_workshop(db, target_date, target_date)
    yesterday_data = _query_input_output_by_workshop(db, target_date - timedelta(days=1), target_date - timedelta(days=1))
    month_start = target_date.replace(day=1)
    monthly_data = _query_input_output_by_workshop(db, month_start, target_date)

    def calc_yield(data: dict[int, dict]) -> float | None:
        total_in = sum(d['input'] for d in data.values())
        total_out = sum(d['output'] for d in data.values())
        if total_in <= 0:
            return None
        return round(total_out / total_in * 100, 2)

    daily = calc_yield(today_data)
    yesterday = calc_yield(yesterday_data)
    monthly = calc_yield(monthly_data)

    return {
        'daily': daily,
        'daily_delta': _delta(daily, yesterday),
        'monthly': monthly,
    }


def _build_energy(db: Session, target_date: date) -> dict:
    try:
        summary = energy_service.summarize_energy_for_date(db, business_date=target_date)
    except Exception:
        summary = {'electricity_value': 0, 'gas_value': 0, 'rows': [], 'total_output_weight': 0, 'energy_per_ton': None}

    elec = _to_float(summary.get('electricity_value'))
    gas = _to_float(summary.get('gas_value'))
    elec_cost = round(elec * DEFAULT_ELECTRICITY_PRICE / 10000, 2)
    gas_cost = round(gas * DEFAULT_GAS_PRICE / 10000, 2)

    by_workshop = []
    for row in summary.get('rows', []):
        by_workshop.append({
            'workshop': row.get('workshop_code', ''),
            'daily_electricity': _round2(_to_float(row.get('electricity_value'))),
            'daily_gas': _round2(_to_float(row.get('gas_value'))),
        })

    return {
        'total_electricity': _round2(elec),
        'total_gas': _round2(gas),
        'electricity_cost': elec_cost,
        'gas_cost': gas_cost,
        'total_cost': round(elec_cost + gas_cost, 2),
        'by_workshop': by_workshop,
    }


def _build_contracts(db: Session, target_date: date) -> dict:
    month_start = target_date.replace(day=1)

    daily_new = (
        db.query(func.count(WorkOrder.id))
        .filter(func.date(WorkOrder.created_at) == target_date)
        .scalar()
    ) or 0

    monthly_total = (
        db.query(func.count(WorkOrder.id))
        .filter(func.date(WorkOrder.created_at) >= month_start, func.date(WorkOrder.created_at) <= target_date)
        .scalar()
    ) or 0

    remaining = (
        db.query(func.count(WorkOrder.id))
        .filter(WorkOrder.overall_status.notin_(['completed', 'cancelled']))
        .scalar()
    ) or 0

    return {
        'daily_new': daily_new,
        'monthly_total': monthly_total,
        'remaining': remaining,
        'remaining_delta': daily_new,
    }


def _build_cost(total_output: float, energy: dict) -> dict:
    elec_cost = energy.get('electricity_cost', 0)
    gas_cost = energy.get('gas_cost', 0)
    total = round(elec_cost + gas_cost, 2)
    cost_per_ton = round(total * 10000 / total_output, 0) if total_output > 0 else None
    return {
        'electricity_cost': elec_cost,
        'gas_cost': gas_cost,
        'total': total,
        'cost_per_ton': cost_per_ton,
        'basis_weight': _round2(total_output),
    }


def build_daily_production_overview(db: Session, *, target_date: date) -> dict[str, Any]:
    ws_map = _workshop_map(db)

    workshop_output = _build_workshop_output(db, target_date, ws_map)
    wip = _build_wip_distribution(db)
    yield_rates = _build_yield_rates(db, target_date)
    energy = _build_energy(db, target_date)
    contracts = _build_contracts(db, target_date)

    total_today = sum(r['daily_output'] or 0 for r in workshop_output)
    total_yesterday = sum(r['yesterday_output'] or 0 for r in workshop_output)
    total_monthly = sum(r['monthly_output'] or 0 for r in workshop_output)
    wip_total = sum(r['total_weight'] or 0 for r in wip)

    cost = _build_cost(total_today, energy)

    header_kpis = [
        {'key': 'total_output', 'label': '车间总产量', 'value': _round2(total_today), 'unit': '吨',
         'delta': _delta(total_today, total_yesterday),
         'delta_label': f'比昨日 {"↑" if total_today >= total_yesterday else "↓"}{abs(round(total_today - total_yesterday, 1))}'},
        {'key': 'monthly_output', 'label': '月累计产量', 'value': _round2(total_monthly), 'unit': '吨'},
        {'key': 'wip_total', 'label': '在制料总计', 'value': _round2(wip_total), 'unit': '吨'},
        {'key': 'daily_yield', 'label': '日成品率', 'value': yield_rates.get('daily'), 'unit': '%',
         'delta': yield_rates.get('daily_delta'),
         'delta_label': f'比昨日 {"↑" if (yield_rates.get("daily_delta") or 0) >= 0 else "↓"}{abs(yield_rates.get("daily_delta") or 0)}%' if yield_rates.get('daily_delta') is not None else None},
        {'key': 'daily_contracts', 'label': '当天接合同', 'value': contracts['daily_new'], 'unit': '个'},
        {'key': 'remaining_contracts', 'label': '总余合同量', 'value': contracts['remaining'], 'unit': '个',
         'delta': contracts['remaining_delta'],
         'delta_label': f'比昨日 {"↑" if contracts["remaining_delta"] >= 0 else "↓"}{abs(contracts["remaining_delta"])}'},
        {'key': 'energy_cost_per_ton', 'label': '综合能耗成本', 'value': cost.get('cost_per_ton'), 'unit': '元/吨'},
    ]

    return {
        'target_date': target_date.isoformat(),
        'header_kpis': header_kpis,
        'workshop_output': workshop_output,
        'wip_distribution': wip,
        'yield_rates': yield_rates,
        'energy': energy,
        'contracts': contracts,
        'cost': cost,
        'attendance': None,
        'oil_consumption': None,
    }
