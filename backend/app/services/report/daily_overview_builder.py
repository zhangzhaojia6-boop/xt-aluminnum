from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.master import Workshop
from app.models.mes import MesCoilSnapshot
from app.models.production import MobileShiftReport, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.services.mobile_report._utils import SUBMITTED_STATUSES
from app.services import energy_service
from app.services.contract_canonical_service import build_contract_projection
from app.services.report._utils import _to_float


DEFAULT_ELECTRICITY_PRICE = 0.65
DEFAULT_GAS_PRICE = 3.60
SHIFT_ORDER = ('A', 'B', 'C')


def _workshop_map(db: Session) -> dict[int, str]:
    return {w.id: w.name for w in db.query(Workshop).filter(Workshop.is_active.is_(True)).all()}


def _round2(v: float | None) -> float | None:
    if v is None:
        return None
    return round(v, 2)


def _fmt_delta_label(delta: float | None, *, suffix: str = '') -> str | None:
    if delta is None:
        return None
    d = round(delta, 2)
    if d == 0:
        return None
    arrow = '↑' if d > 0 else '↓'
    return f'比昨日 {arrow}{abs(d)}{suffix}'


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
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
            WorkOrderEntry.entry_type == 'mobile_coil',
            Workshop.is_active.is_(True),
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
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
            WorkOrderEntry.entry_type == 'mobile_coil',
            Workshop.is_active.is_(True),
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
    all_ids = (set(today) | set(monthly)) & set(ws_map)
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


def _build_wip_distribution(db: Session, target_date: date) -> list[dict]:
    def present(column):
        return and_(column.isnot(None), column != '')

    workshop_label = func.coalesce(
        func.nullif(MesCoilSnapshot.current_workshop, ''),
        func.nullif(MesCoilSnapshot.workshop_code, ''),
        func.nullif(MesCoilSnapshot.next_process, ''),
    )
    not_finished_stock = and_(
        MesCoilSnapshot.in_stock_date.is_(None),
        or_(MesCoilSnapshot.status_name.is_(None), MesCoilSnapshot.status_name != '已入库'),
    )
    rows = (
        db.query(
            workshop_label,
            func.count(MesCoilSnapshot.id),
            func.sum(MesCoilSnapshot.material_weight),
        )
        .filter(
            MesCoilSnapshot.business_date == target_date,
            MesCoilSnapshot.delivery_date.is_(None),
            MesCoilSnapshot.allocation_date.is_(None),
            not_finished_stock,
            or_(present(MesCoilSnapshot.current_process), present(MesCoilSnapshot.next_process)),
        )
        .group_by(workshop_label)
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
    def normalize_yield(value: float | None) -> float | None:
        if value is None:
            return None
        raw = float(value)
        if raw < 0:
            return None
        percent = raw * 100 if raw <= 1.5 else raw
        if percent > 100:
            return None
        return percent

    def yield_from_entries(start: date, end: date) -> float | None:
        values = (
            db.query(WorkOrderEntry.yield_rate)
            .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
            .filter(
                WorkOrderEntry.business_date >= start,
                WorkOrderEntry.business_date <= end,
                WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
                WorkOrderEntry.entry_type == 'mobile_coil',
                WorkOrderEntry.yield_rate.isnot(None),
                Workshop.is_active.is_(True),
            )
            .all()
        )
        normalized = [v for (item,) in values if (v := normalize_yield(item)) is not None]
        if not normalized:
            return None
        return round(sum(normalized) / len(normalized), 2)

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

    daily = yield_from_entries(target_date, target_date) or calc_yield(today_data)
    yesterday = yield_from_entries(target_date - timedelta(days=1), target_date - timedelta(days=1)) or calc_yield(yesterday_data)
    monthly = yield_from_entries(month_start, target_date) or calc_yield(monthly_data)

    return {
        'daily': daily,
        'daily_delta': _delta(daily, yesterday),
        'monthly': monthly,
        'owner_daily': _owner_daily_value(db, target_date, 'plant_wide_yield_rate'),
        'basis': 'mobile_coil_yield_rate',
    }


def _owner_daily_value(db: Session, target_date: date, field_name: str) -> float | None:
    rows = (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.business_date == target_date,
            WorkOrderEntry.entry_type == 'owner_daily',
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
        )
        .order_by(WorkOrderEntry.updated_at.asc(), WorkOrderEntry.id.asc())
        .all()
    )
    value = None
    for row in rows:
        payload = row.extra_payload or {}
        if payload.get(field_name) is not None:
            value = _to_float(payload.get(field_name))
    return value


def _build_energy(db: Session, target_date: date) -> dict:
    try:
        summary = energy_service.summarize_energy_for_date(db, business_date=target_date)
    except Exception:
        summary = {'electricity_value': 0, 'gas_value': 0, 'rows': [], 'total_output_weight': 0, 'energy_per_ton': None}

    elec = _to_float(summary.get('electricity_value'))
    gas = _to_float(summary.get('gas_value'))
    owner_totals = summary.get('owner_totals') or {}
    mobile_totals = summary.get('mobile_totals') or {}
    system_totals = summary.get('system_totals') or {}
    has_energy_data = bool(summary.get('rows')) and summary.get('primary_source') != 'none'
    has_owner_data = int(owner_totals.get('row_count') or 0) > 0
    has_mobile_data = int(mobile_totals.get('row_count') or 0) > 0
    has_system_data = int(system_totals.get('row_count') or 0) > 0
    if not has_energy_data:
        elec = None
        gas = None
    elec_cost = round(elec * DEFAULT_ELECTRICITY_PRICE / 10000, 2) if elec is not None else None
    gas_cost = round(gas * DEFAULT_GAS_PRICE / 10000, 2) if gas is not None else None

    by_workshop = []
    for row in summary.get('rows', []) if has_energy_data else []:
        by_workshop.append({
            'workshop': row.get('workshop_code', ''),
            'daily_electricity': _round2(_to_float(row.get('electricity_value'))),
            'daily_gas': _round2(_to_float(row.get('gas_value'))),
        })

    return {
        'total_electricity': _round2(elec),
        'total_gas': _round2(gas),
        'primary_source': summary.get('primary_source'),
        'owner_electricity': _round2(_to_float(owner_totals.get('electricity_value'))) if has_owner_data else None,
        'owner_gas': _round2(_to_float(owner_totals.get('gas_value'))) if has_owner_data else None,
        'owner_total_energy': _round2(_to_float(owner_totals.get('total_energy'))) if has_owner_data else None,
        'mobile_total_energy': _round2(_to_float(mobile_totals.get('total_energy'))) if has_mobile_data else None,
        'system_total_energy': _round2(_to_float(system_totals.get('total_energy'))) if has_system_data else None,
        'energy_per_ton': _round2(_to_float(summary.get('energy_per_ton'))) if has_energy_data else None,
        'electricity_cost': elec_cost,
        'gas_cost': gas_cost,
        'total_cost': round((elec_cost or 0) + (gas_cost or 0), 2) if elec_cost is not None or gas_cost is not None else None,
        'data_available': has_energy_data,
        'by_workshop': by_workshop,
    }


def _build_contracts(db: Session, target_date: date) -> dict:
    projection = build_contract_projection(db, target_date=target_date)
    daily_new = _round2(_to_float(projection.get('daily_contract_weight')))
    monthly_total = _round2(_to_float(projection.get('month_to_date_contract_weight')))
    remaining = _round2(_to_float(projection.get('remaining_contract_weight')))
    remaining_delta = _round2(_to_float(projection.get('remaining_contract_delta_weight')))

    return {
        'daily_new': daily_new,
        'monthly_total': monthly_total,
        'remaining': remaining,
        'remaining_delta': remaining_delta,
        'unit': '吨',
        'basis': 'owner_daily_contract_weight' if projection.get('owner_entry_count') else 'contract_projection',
        'quality_status': projection.get('quality_status'),
    }


def _build_cost(total_output: float, energy: dict) -> dict:
    elec_cost = energy.get('electricity_cost')
    gas_cost = energy.get('gas_cost')
    total = round((elec_cost or 0) + (gas_cost or 0), 2) if elec_cost is not None or gas_cost is not None else None
    cost_per_ton = round(total * 10000 / total_output, 0) if total is not None and total_output > 0 else None
    return {
        'electricity_cost': elec_cost,
        'gas_cost': gas_cost,
        'total': total,
        'cost_per_ton': cost_per_ton,
        'basis_weight': _round2(total_output),
    }


def _entry_sort_key(row: WorkOrderEntry) -> tuple:
    return (
        row.approved_at or row.verified_at or row.submitted_at or row.updated_at or row.created_at,
        row.id,
    )


def _query_latest_mobile_coil_rows(db: Session, start: date, end: date) -> list[WorkOrderEntry]:
    rows = (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_status.in_(tuple(SUBMITTED_STATUSES)),
            WorkOrderEntry.entry_type == 'mobile_coil',
            WorkOrderEntry.output_weight.is_not(None),
        )
        .all()
    )

    latest_by_work_order_day: dict[tuple[date, int], WorkOrderEntry] = {}
    for row in rows:
        if row.work_order_id is None or row.business_date is None:
            continue
        key = (row.business_date, int(row.work_order_id))
        current = latest_by_work_order_day.get(key)
        if current is None or _entry_sort_key(row) >= _entry_sort_key(current):
            latest_by_work_order_day[key] = row
    return list(latest_by_work_order_day.values())


def _payload_number(payload: dict, field_name: str) -> float | None:
    value = payload.get(field_name)
    if value is None or value == '':
        return None
    return _to_float(value)


def _owner_storage_inbound_tons(payload: dict) -> float:
    direct_value = _payload_number(payload, 'storage_inbound_weight')
    if direct_value is not None:
        return direct_value
    component_total = 0.0
    has_component = False
    for field_name in ('park_inbound_daily', 'new_plant_inbound_daily', 'park_to_storage_inbound_weight'):
        value = _payload_number(payload, field_name)
        if value is None:
            continue
        component_total += value
        has_component = True
    return component_total if has_component else 0.0


def _query_owner_storage_inbound_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    rows = (
        db.query(WorkOrderEntry)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_status.in_(tuple(SUBMITTED_STATUSES)),
            WorkOrderEntry.machine_id.is_(None),
            Workshop.workshop_type == 'inventory',
        )
        .all()
    )
    totals: dict[date, float] = {}
    for row in rows:
        inbound_tons = _owner_storage_inbound_tons(dict(row.extra_payload or {}))
        if inbound_tons <= 0:
            continue
        totals[row.business_date] = totals.get(row.business_date, 0.0) + inbound_tons
    return totals


def _query_shift_report_storage_finished_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    rows = (
        db.query(
            MobileShiftReport.business_date,
            func.sum(MobileShiftReport.storage_finished),
        )
        .filter(
            MobileShiftReport.business_date >= start,
            MobileShiftReport.business_date <= end,
            MobileShiftReport.report_status.in_(tuple(SUBMITTED_STATUSES)),
            MobileShiftReport.storage_finished.is_not(None),
        )
        .group_by(MobileShiftReport.business_date)
        .all()
    )
    return {business_date: _to_float(total) for business_date, total in rows}


def _query_plant_output_totals_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    totals = _query_owner_storage_inbound_by_date(db, start, end)
    fallback_totals = _query_shift_report_storage_finished_by_date(db, start, end)
    for business_date, total in fallback_totals.items():
        totals.setdefault(business_date, total)
    return {business_date: _round2(total) or 0.0 for business_date, total in totals.items()}


def _build_plant_output(db: Session, target_date: date, energy: dict) -> dict:
    month_start = target_date.replace(day=1)
    totals_by_date = _query_plant_output_totals_by_date(db, month_start, target_date)
    daily_output = totals_by_date.get(target_date, 0.0)
    yesterday_output = totals_by_date.get(target_date - timedelta(days=1), 0.0)
    monthly_output = sum(totals_by_date.values())
    total_electricity = _to_float(energy.get('total_electricity'))
    energy_per_ton = round(total_electricity / daily_output, 2) if daily_output > 0 and total_electricity > 0 else None
    return {
        'basis': 'storage_inbound_output',
        'basis_label': '全厂入库产量',
        'daily_output': _round2(daily_output),
        'yesterday_output': _round2(yesterday_output),
        'monthly_output': _round2(monthly_output),
        'energy_per_ton': energy_per_ton,
    }


def _build_shift_breakdown(db: Session, target_date: date) -> dict:
    latest_rows = _query_latest_mobile_coil_rows(db, target_date, target_date)
    shift_meta = {
        item.id: item
        for item in db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).all()
    }

    def canonical_shift_code(meta: ShiftConfig | None) -> str | None:
        code = str(getattr(meta, 'code', '') or '').strip().upper()
        name = str(getattr(meta, 'name', '') or '').strip()
        if code in {'A', 'DAY'} or '白班' in name:
            return 'A'
        if code in {'B', 'MID'} or '中班' in name or '小夜' in name:
            return 'B'
        if code in {'C', 'NIGHT'} or '夜班' in name or '大夜' in name:
            return 'C'
        return None

    grouped: dict[str, dict[str, Any]] = {}
    for row in latest_rows:
        if row.shift_id is None:
            continue
        meta = shift_meta.get(int(row.shift_id))
        bucket = canonical_shift_code(meta)
        if bucket is None:
            continue
        payload = grouped.setdefault(
            bucket,
            {
                'meta': meta,
                'total_output': 0.0,
                'total_energy': 0.0,
                'entry_count': 0,
                'workshop_count': 0,
            },
        )
        payload['total_output'] += round((_to_float(getattr(row, 'output_weight', None)) / 1000), 2)
        payload['total_energy'] += round(_to_float(getattr(row, 'energy_kwh', None)), 1)
        payload['entry_count'] += 1
        payload['workshop_count'] += 1 if getattr(row, 'workshop_id', None) is not None else 0

    shifts: list[dict[str, Any]] = []
    grand_output = 0.0
    grand_energy = 0.0
    for code in SHIFT_ORDER:
        bucket = grouped.get(code) or {}
        meta = bucket.get('meta')
        total_output = round(float(bucket.get('total_output') or 0.0), 2)
        total_energy = round(float(bucket.get('total_energy') or 0.0), 1)
        entry_count = int(bucket.get('entry_count') or 0)
        workshop_count = int(bucket.get('workshop_count') or 0)
        grand_output += total_output
        grand_energy += total_energy
        shift_window = ''
        if meta is not None:
            shift_window = f"{meta.start_time.strftime('%H:%M')}-{meta.end_time.strftime('%H:%M')}"
        shifts.append({
            'shift_code': code,
            'shift_name': meta.name if meta is not None else code,
            'shift_window': shift_window,
            'shift_count': entry_count,
            'total_output': total_output,
            'reported_workshops': workshop_count,
            'expected_workshops': workshop_count,
            'energy_per_ton': round(total_energy / total_output, 1) if total_output > 0 and total_energy > 0 else None,
            'exception_count': 0,
        })
    return {
        'business_date': target_date.isoformat(),
        'total_output': round(grand_output, 2),
        'total_throughput': round(grand_output, 2),
        'output_basis': 'mobile_coil_process_output',
        'output_basis_label': '工序下机量',
        'total_energy_kwh': round(grand_energy, 1),
        'energy_per_ton': round(grand_energy / grand_output, 1) if grand_output > 0 and grand_energy > 0 else None,
        'shifts': shifts,
    }


def build_daily_production_overview(db: Session, *, target_date: date) -> dict[str, Any]:
    ws_map = _workshop_map(db)

    workshop_output = _build_workshop_output(db, target_date, ws_map)
    wip = _build_wip_distribution(db, target_date)
    yield_rates = _build_yield_rates(db, target_date)
    energy = _build_energy(db, target_date)
    contracts = _build_contracts(db, target_date)
    plant_output = _build_plant_output(db, target_date, energy)
    shift_breakdown = _build_shift_breakdown(db, target_date)

    total_today = sum(r['daily_output'] or 0 for r in workshop_output)
    total_yesterday = sum(r['yesterday_output'] or 0 for r in workshop_output)
    total_monthly = sum(r['monthly_output'] or 0 for r in workshop_output)
    wip_total = sum(r['total_weight'] or 0 for r in wip)

    process_cost = _build_cost(total_today, energy)
    plant_cost = _build_cost(plant_output['daily_output'] or 0, energy)

    header_kpis = [
        {'key': 'plant_inbound_output', 'label': '全厂入库产量', 'value': plant_output['daily_output'], 'unit': '吨',
         'delta': _delta(plant_output['daily_output'], plant_output['yesterday_output']),
         'delta_label': _fmt_delta_label(_delta(plant_output['daily_output'], plant_output['yesterday_output']))},
        {'key': 'plant_inbound_monthly', 'label': '入库月累计', 'value': plant_output['monthly_output'], 'unit': '吨'},
        {'key': 'wip_total', 'label': '在制料总计', 'value': _round2(wip_total), 'unit': '吨'},
        {'key': 'daily_yield', 'label': '日成品率', 'value': yield_rates.get('daily'), 'unit': '%',
         'delta': yield_rates.get('daily_delta'),
         'delta_label': _fmt_delta_label(yield_rates.get('daily_delta'), suffix='%')},
        {'key': 'daily_contracts', 'label': '当天接合同', 'value': contracts['daily_new'], 'unit': '吨'},
        {'key': 'remaining_contracts', 'label': '总余合同量', 'value': contracts['remaining'], 'unit': '吨',
         'delta': contracts['remaining_delta'],
         'delta_label': _fmt_delta_label(contracts['remaining_delta'])},
        {'key': 'energy_cost_per_ton', 'label': '综合能耗成本', 'value': plant_cost.get('cost_per_ton'), 'unit': '元/吨'},
    ]

    return {
        'target_date': target_date.isoformat(),
        'header_kpis': header_kpis,
        'plant_output': plant_output,
        'shift_breakdown': shift_breakdown,
        'workshop_output': workshop_output,
        'wip_distribution': wip,
        'yield_rates': yield_rates,
        'energy': energy,
        'contracts': contracts,
        'cost': plant_cost,
        'plant_cost': plant_cost,
        'process_cost': process_cost,
        'attendance': None,
        'oil_consumption': None,
    }
