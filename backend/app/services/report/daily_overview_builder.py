from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, inspect, or_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.active_workshops import get_workshop_data_source_policy, normalize_workshop_name, workshop_name_query_tokens
from app.core.business_time import production_business_day_start_label, production_business_window
from app.models.attendance import AttendanceSchedule
from app.models.master import Workshop
from app.models.mes import MesCoilSnapshot, MesDailyWipSnapshot, MesMaterialRecord, MesStockRecord, MesWipTotalSnapshot, MesWorkshopProcessRecord, MesYieldRecord
from app.models.production import WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.mobile_report._utils import SUBMITTED_STATUSES
from app.services import energy_service
from app.services.contract_canonical_service import build_contract_projection
from app.services.production_output_scope import counts_as_workshop_output, normalize_process_stage, pass_count
from app.services.report._utils import _to_float
from app.services.report import mes_factory_packaging_fact, mes_factory_production_fact, mes_home_packaging_fact
from app.services.report.daily_report_fact_closure import build_persisted_daily_fact_surface
from app.services.report.mes_workshop_mapping import resolve_mes_process_workshop_bucket


DEFAULT_ELECTRICITY_PRICE = 0.65
DEFAULT_GAS_PRICE = 3.60
SHIFT_ORDER = ('A', 'B', 'C')
SHIFT_LABELS = {'A': '长白班', 'B': '小夜班', 'C': '大夜班'}
SHIFT_WINDOWS = {'A': '07:30-15:30', 'B': '15:30-23:30', 'C': '23:30-07:30'}
PRODUCTION_SHIFT_EXCLUDED_WORKSHOP_CODES = {'FACTORY'}
FINAL_PACKAGING_WORKSHOP_CODES = {'JZ', 'LJ', 'JQ'}
FINAL_PACKAGING_MES_WORKSHOP_NAMES = {'精整', '精整车间', '拉矫', '拉矫车间', '园区精整', '园区剪切', '园区剪切车间', '剪切车间'}
MES_PACKAGING_PROCESS_KEYWORDS = ('包装',)
MES_STOCK_OUTPUT_FROM_DEPARTMENT_KEYWORDS = ('精整', '拉矫', '剪切')
MES_STOCK_HEADER_SOURCE_PATH = 'sqlserver:stock_header_records'
MES_DELIVERY_SOURCE_PATH = 'sqlserver:delivery_records'
MES_DELIVERY_STOCK_SOURCE_PATH = 'sqlserver:delivery_stock_records'
STORAGE_OWNER_ROLE = 'storage_owner'
BILLET_MATERIAL_WORKSHOP_MAPPINGS = {
    '热轧': ('热轧车间', '热轧'),
    '铸二': ('铸二车间', '铸二', '铸轧二', '铸轧二车间', '铸轧2'),
    '铸三': ('铸三车间', '铸三', '铸轧三', '铸轧三车间', '铸轧3'),
}
BILLET_BUSINESS_DAY_START = time(10, 0)
BILLET_MATERIAL_INCLUDED_STATUS_NAMES = ('已使用', '未使用')


def _workshop_map(db: Session) -> dict[int, str]:
    return {w.id: w.name for w in db.query(Workshop).filter(Workshop.is_active.is_(True)).all()}


def _is_production_shift_workshop(workshop: Workshop) -> bool:
    code = str(getattr(workshop, 'code', '') or '').strip().upper()
    name = str(getattr(workshop, 'name', '') or '').strip()
    return code not in PRODUCTION_SHIFT_EXCLUDED_WORKSHOP_CODES and name != '全厂'


def _round2(v: float | None) -> float | None:
    if v is None:
        return None
    return round(v, 2)


def _mobile_coil_output_scope_by_workshop(db: Session, start: date, end: date) -> dict[int, dict[str, Any]]:
    workshop_by_id = {
        item.id: item
        for item in db.query(Workshop).filter(Workshop.is_active.is_(True)).all()
    }
    result: dict[int, dict[str, Any]] = {}
    for row in _query_latest_mobile_coil_rows(db, start, end):
        if row.workshop_id is None:
            continue
        workshop = workshop_by_id.get(row.workshop_id)
        if workshop is None:
            continue
        wid = int(row.workshop_id)
        bucket = result.setdefault(
            wid,
            {
                'input': 0.0,
                'output': 0.0,
                'process_output': 0.0,
                'pass_count_total': 0,
                'process_stage_outputs': {},
            },
        )
        input_weight = _to_float(row.input_weight) / 1000
        output_weight = _to_float(row.output_weight) / 1000
        bucket['process_output'] += output_weight
        bucket['pass_count_total'] += pass_count(row.extra_payload)
        if str(workshop.workshop_type or '').strip() == 'cold_roll':
            stage = normalize_process_stage(row.extra_payload)
            stage_key = stage or 'unmarked'
            stage_outputs = bucket['process_stage_outputs']
            stage_outputs[stage_key] = stage_outputs.get(stage_key, 0.0) + output_weight
        if counts_as_workshop_output(workshop_type=workshop.workshop_type, extra_payload=row.extra_payload):
            bucket['input'] += input_weight
            bucket['output'] += output_weight

    for bucket in result.values():
        bucket['input'] = _round2(bucket['input']) or 0.0
        bucket['output'] = _round2(bucket['output']) or 0.0
        bucket['process_output'] = _round2(bucket['process_output']) or 0.0
        bucket['process_stage_outputs'] = {
            key: _round2(value) or 0.0
            for key, value in bucket['process_stage_outputs'].items()
        }
    return result


def _process_row_text(row: MesWorkshopProcessRecord) -> str:
    payload = getattr(row, 'source_payload', None) or {}
    payload_text = ' '.join(
        str(payload.get(key) or '')
        for key in ('process_code', 'report_process_code', 'metric_code')
    )
    return ' '.join(
        str(item or '')
        for item in (row.workshop_name, row.process_name, row.device_name, row.source_id, payload_text)
    )


def _process_row_pass_count(row: MesWorkshopProcessRecord) -> int:
    payload = getattr(row, 'source_payload', None) or {}
    for key in ('pass_count', 'passes', '道次'):
        if payload.get(key) not in (None, ''):
            return int(_to_float(payload.get(key)))
    return 1


def _mes_input_tons(row: MesWorkshopProcessRecord) -> float:
    direct = _to_float(row.input_weight_tons)
    if direct > 0:
        return direct
    return _to_float(row.input_weight_kg) / 1000


def _mes_row_matches_workshop(row: MesWorkshopProcessRecord, workshop: Workshop) -> bool:
    canonical_name = normalize_workshop_name(workshop.name)
    resolved = resolve_mes_process_workshop_bucket(row.workshop_name, row.process_name, row.device_name)
    if resolved is not None:
        return resolved == canonical_name
    tokens = set(workshop_name_query_tokens(workshop.name))
    tokens.update(workshop_name_query_tokens(workshop.code))
    text = _process_row_text(row)
    return any(token and token in text for token in tokens)


def _billet_material_business_window(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, BILLET_BUSINESS_DAY_START),
        datetime.combine(end + timedelta(days=1), BILLET_BUSINESS_DAY_START),
    )


def _mes_material_weight_tons(row: MesMaterialRecord) -> float:
    direct = _to_float(row.weight_tons)
    if direct > 0:
        return direct
    return _to_float(row.weight_kg) / 1000


def _mes_material_status_counts(row: MesMaterialRecord) -> bool:
    payload = row.source_payload if isinstance(row.source_payload, dict) else {}
    status_text = str(row.status_name or payload.get('StatusName') or payload.get('Status') or '').strip()
    if not status_text:
        return True
    return any(token in status_text for token in BILLET_MATERIAL_INCLUDED_STATUS_NAMES)


def _mes_material_row_matches_workshop(row: MesMaterialRecord, workshop: Workshop) -> bool:
    canonical_name = normalize_workshop_name(workshop.name)
    tokens = BILLET_MATERIAL_WORKSHOP_MAPPINGS.get(canonical_name)
    if tokens is None:
        return False
    row_workshop = str(row.workshop_name or '')
    if normalize_workshop_name(row_workshop) == canonical_name:
        return True
    return any(token and token in row_workshop for token in tokens)


def _query_mes_material_output_scope_by_workshop(db: Session, start: date, end: date) -> dict[int, dict[str, Any]]:
    if db is None or not _has_mes_material_record_table(db):
        return {}
    workshops = [
        item
        for item in db.query(Workshop).filter(Workshop.is_active.is_(True)).order_by(Workshop.sort_order.asc(), Workshop.id.asc()).all()
        if normalize_workshop_name(item.name) in BILLET_MATERIAL_WORKSHOP_MAPPINGS
    ]
    if not workshops:
        return {}
    start_at, end_at = _billet_material_business_window(start, end)
    rows = (
        db.query(MesMaterialRecord)
        .filter(
            MesMaterialRecord.production_date >= start_at,
            MesMaterialRecord.production_date < end_at,
        )
        .order_by(MesMaterialRecord.id.asc())
        .all()
    )
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not _mes_material_status_counts(row):
            continue
        output_weight = _mes_material_weight_tons(row)
        if output_weight <= 0:
            continue
        matched_workshop = next((workshop for workshop in workshops if _mes_material_row_matches_workshop(row, workshop)), None)
        if matched_workshop is None:
            continue
        bucket = result.setdefault(
            int(matched_workshop.id),
            {
                'input': 0.0,
                'output': 0.0,
                'process_output': 0.0,
                'pass_count_total': 0,
                'process_stage_outputs': {},
                'source_basis': 'mes_material_records',
                'source_label': '外部 MES 坯料卷产量',
            },
        )
        bucket['input'] += output_weight
        bucket['output'] += output_weight
        bucket['process_output'] += output_weight
        bucket['pass_count_total'] += 1
        line_key = str(row.line_name or '').strip() or '未分机列'
        stage_outputs = bucket['process_stage_outputs']
        stage_outputs[line_key] = stage_outputs.get(line_key, 0.0) + output_weight

    for bucket in result.values():
        bucket['input'] = _round2(bucket['input']) or 0.0
        bucket['output'] = _round2(bucket['output']) or 0.0
        bucket['process_output'] = _round2(bucket['process_output']) or 0.0
        bucket['process_stage_outputs'] = {
            key: _round2(value) or 0.0
            for key, value in bucket['process_stage_outputs'].items()
        }
    return result


def _query_mes_process_output_scope_by_workshop(db: Session, start: date, end: date) -> dict[int, dict[str, Any]]:
    if db is None or not _has_mes_workshop_process_record_table(db):
        return {}
    workshops = [
        item
        for item in db.query(Workshop).filter(Workshop.is_active.is_(True)).order_by(Workshop.sort_order.asc(), Workshop.id.asc()).all()
        if get_workshop_data_source_policy(item.name).get('primary_source') == 'mes'
    ]
    rows = (
        db.query(MesWorkshopProcessRecord)
        .filter(
            MesWorkshopProcessRecord.business_date >= start,
            MesWorkshopProcessRecord.business_date <= end,
        )
        .order_by(MesWorkshopProcessRecord.id.asc())
        .all()
    )
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        output_weight = _mes_output_tons(row)
        if output_weight <= 0:
            continue
        matched_workshop = next((workshop for workshop in workshops if _mes_row_matches_workshop(row, workshop)), None)
        if matched_workshop is None:
            continue
        bucket = result.setdefault(
            int(matched_workshop.id),
            {
                'input': 0.0,
                'output': 0.0,
                'process_output': 0.0,
                'pass_count_total': 0,
                'process_stage_outputs': {},
                'source_basis': 'mes_workshop_process_records',
                'source_label': '外部 MES 过站产量',
            },
        )
        bucket['input'] += _mes_input_tons(row)
        bucket['process_output'] += output_weight
        bucket['pass_count_total'] += _process_row_pass_count(row)
        if counts_as_workshop_output(workshop_type=matched_workshop.workshop_type, extra_payload=row.source_payload):
            bucket['output'] += output_weight
        if str(matched_workshop.workshop_type or '').strip() == 'cold_roll':
            stage = normalize_process_stage(getattr(row, 'source_payload', None) or {})
            stage_key = stage or 'unmarked'
            stage_outputs = bucket['process_stage_outputs']
            stage_outputs[stage_key] = stage_outputs.get(stage_key, 0.0) + output_weight

    for bucket in result.values():
        bucket['input'] = _round2(bucket['input']) or 0.0
        bucket['output'] = _round2(bucket['output']) or 0.0
        bucket['process_output'] = _round2(bucket['process_output']) or 0.0
        bucket['process_stage_outputs'] = {
            key: _round2(value) or 0.0
            for key, value in bucket['process_stage_outputs'].items()
        }
    return result


def _clone_output_payload(payload: dict[str, Any], *, source_basis: str, source_label: str) -> dict[str, Any]:
    return {
        'input': _round2(_to_float(payload.get('input'))) or 0.0,
        'output': _round2(_to_float(payload.get('output'))) or 0.0,
        'process_output': _round2(_to_float(payload.get('process_output'))) or 0.0,
        'pass_count_total': int(payload.get('pass_count_total') or 0),
        'process_stage_outputs': dict(payload.get('process_stage_outputs') or {}),
        'source_basis': source_basis,
        'source_label': source_label,
    }


def _mixed_workshop_output_scope_by_workshop(db: Session, start: date, end: date) -> dict[int, dict[str, Any]]:
    mobile_scope = _mobile_coil_output_scope_by_workshop(db, start, end)
    material_scope = _query_mes_material_output_scope_by_workshop(db, start, end)
    mes_scope = _query_mes_process_output_scope_by_workshop(db, start, end)
    workshops = db.query(Workshop).filter(Workshop.is_active.is_(True)).all()
    result: dict[int, dict[str, Any]] = {}
    for workshop in workshops:
        wid = int(workshop.id)
        canonical_name = normalize_workshop_name(workshop.name)
        if canonical_name in BILLET_MATERIAL_WORKSHOP_MAPPINGS:
            if wid in material_scope:
                result[wid] = _clone_output_payload(
                    material_scope[wid],
                    source_basis='mes_material_records',
                    source_label='外部 MES 坯料卷产量',
                )
            elif wid in mobile_scope:
                result[wid] = _clone_output_payload(
                    mobile_scope[wid],
                    source_basis='manual_mobile_coil_fallback',
                    source_label='人工填报兜底产量',
                )
            continue
        policy = get_workshop_data_source_policy(workshop.name)
        if policy.get('primary_source') == 'mes':
            if wid in mes_scope:
                result[wid] = _clone_output_payload(
                    mes_scope[wid],
                    source_basis='mes_workshop_process_records',
                    source_label='外部 MES 过站产量',
                )
            elif wid in mobile_scope:
                result[wid] = _clone_output_payload(
                    mobile_scope[wid],
                    source_basis='manual_mobile_coil_fallback',
                    source_label='人工填报兜底产量',
                )
            continue
        if wid in mobile_scope:
            result[wid] = _clone_output_payload(
                mobile_scope[wid],
                source_basis='manual_mobile_coil',
                source_label='人工填报产量',
            )
    return result


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
    return {
        workshop_id: payload['output']
        for workshop_id, payload in _mobile_coil_output_scope_by_workshop(db, start, end).items()
    }


def _query_input_output_by_workshop(db: Session, start: date, end: date) -> dict[int, dict]:
    return {
        workshop_id: {
            'input': payload['input'],
            'output': payload['output'],
        }
        for workshop_id, payload in _mobile_coil_output_scope_by_workshop(db, start, end).items()
    }


def _build_workshop_output(db: Session, target_date: date, ws_map: dict[int, str]) -> list[dict]:
    month_start = target_date.replace(day=1)
    today_scope = _mixed_workshop_output_scope_by_workshop(db, target_date, target_date)
    yesterday_scope = _mixed_workshop_output_scope_by_workshop(db, target_date - timedelta(days=1), target_date - timedelta(days=1))
    monthly_scope = _mixed_workshop_output_scope_by_workshop(db, month_start, target_date)
    today = {wid: payload['output'] for wid, payload in today_scope.items()}
    yesterday = {wid: payload['output'] for wid, payload in yesterday_scope.items()}
    monthly = {wid: payload['output'] for wid, payload in monthly_scope.items()}

    rows = []
    all_ids = (set(today_scope) | set(yesterday_scope) | set(monthly_scope)) & set(ws_map)
    for wid in sorted(all_ids, key=lambda w: -(today.get(w, 0))):
        name = ws_map.get(wid, f'车间{wid}')
        d = _round2(today.get(wid, 0))
        m = _round2(monthly.get(wid, 0))
        yd = _round2(yesterday.get(wid, 0))
        today_payload = today_scope.get(wid, {})
        rows.append({
            'workshop_id': wid,
            'workshop': name,
            'daily_output': d,
            'monthly_output': m,
            'yesterday_output': yd,
            'delta': _delta(d, yd),
            'process_output': today_payload.get('process_output'),
            'pass_count_total': today_payload.get('pass_count_total', 0),
            'process_stage_outputs': today_payload.get('process_stage_outputs', {}),
            'source_basis': today_payload.get('source_basis'),
            'source_label': today_payload.get('source_label'),
        })
    return rows


def _wip_workshop_key(value: Any) -> str:
    return str(value or '').strip()


def _wip_weight_tons(value: Any) -> float:
    weight = _to_float(value)
    if weight > 1000:
        return weight / 1000
    return weight


def _latest_wip_total_by_workshop(db: Session, target_date: date) -> dict[str, dict[str, Any]]:
    try:
        start_at, end_at = production_business_window(target_date)
        latest_at = (
            db.query(func.max(MesWipTotalSnapshot.snapshot_at))
            .filter(
                MesWipTotalSnapshot.snapshot_at >= start_at,
                MesWipTotalSnapshot.snapshot_at < end_at,
            )
            .scalar()
        )
        if latest_at is None:
            return {}

        rows = (
            db.query(
                MesWipTotalSnapshot.workshop_name,
                func.sum(MesWipTotalSnapshot.doing_count),
                func.sum(MesWipTotalSnapshot.doing_weight_tons),
            )
            .filter(MesWipTotalSnapshot.snapshot_at == latest_at)
            .group_by(MesWipTotalSnapshot.workshop_name)
            .all()
        )
    except (OperationalError, ProgrammingError):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for workshop, count, weight in rows:
        key = _wip_workshop_key(workshop)
        if not key:
            continue
        result[key] = {
            'key': key,
            'workshop': workshop,
            'coil_count': int(count or 0),
            'total_weight': _wip_weight_tons(weight),
            'snapshot_at': latest_at,
            'source_basis': 'mes_wip_total_snapshot',
            'source_label': 'MES 在制料统计',
        }
    return result


def _build_wip_distribution(db: Session, target_date: date) -> list[dict]:
    wip_total_rows = _latest_wip_total_by_workshop(db, target_date)
    if wip_total_rows:
        result = [
            {
                'workshop': row['workshop'],
                'coil_count': row['coil_count'],
                'total_weight': _round2(row['total_weight']),
                'feeding_weight': 0.0,
                'source_basis': row['source_basis'],
                'source_label': row['source_label'],
                'snapshot_at': row['snapshot_at'].isoformat() if row.get('snapshot_at') is not None else None,
            }
            for row in wip_total_rows.values()
            if row['total_weight'] > 0
        ]
        result.sort(key=lambda x: -(x['total_weight'] or 0))
        return result

    snapshot_rows = (
        db.query(
            MesDailyWipSnapshot.workshop_name,
            func.sum(MesDailyWipSnapshot.coil_count),
            func.sum(MesDailyWipSnapshot.material_weight_tons),
            func.sum(MesDailyWipSnapshot.feeding_weight_tons),
        )
        .filter(MesDailyWipSnapshot.business_date == target_date)
        .group_by(MesDailyWipSnapshot.workshop_name)
        .all()
    )
    if snapshot_rows:
        has_positive_daily_snapshot = any(_to_float(weight) > 0 for _workshop, _count, weight, _feeding in snapshot_rows)
        result = []
        for workshop, count, weight, feeding_weight in snapshot_rows:
            total_weight = _to_float(weight)
            if has_positive_daily_snapshot and total_weight <= 0:
                continue
            coil_count = int(count or 0)
            source_basis = 'mes_daily_wip_snapshot'
            source_label = '外部 MES 当日快照参考'
            result.append({
                'workshop': workshop,
                'coil_count': coil_count,
                'total_weight': _round2(total_weight),
                'feeding_weight': _round2(_to_float(feeding_weight)),
                'source_basis': source_basis,
                'source_label': source_label,
            })
        result.sort(key=lambda x: -(x['total_weight'] or 0))
        return result

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
            func.sum(MesCoilSnapshot.feeding_weight),
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
    for workshop, count, weight, feeding_weight in rows:
        w = _to_float(weight) / 1000
        result.append({
            'workshop': workshop,
            'coil_count': count or 0,
            'total_weight': _round2(w),
            'feeding_weight': _round2(_to_float(feeding_weight)),
            'source_basis': 'mes_coil_snapshot_business_date',
            'source_label': '外部 MES 当日快照参考',
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

    def mes_yield_from_records(start: date, end: date) -> float | None:
        if db is None or not _has_mes_yield_record_table(db):
            return None
        try:
            rows = (
                db.query(MesYieldRecord)
                .filter(
                    MesYieldRecord.business_date >= start,
                    MesYieldRecord.business_date <= end,
                )
                .all()
            )
        except (OperationalError, ProgrammingError):
            return None
        rates = []
        for row in rows:
            normalized = normalize_yield(row.yield_rate)
            if normalized is not None:
                rates.append(normalized)
        if rates:
            return round(sum(rates) / len(rates), 2)
        return None

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

    daily_mes = mes_yield_from_records(target_date, target_date)
    yesterday_mes = mes_yield_from_records(target_date - timedelta(days=1), target_date - timedelta(days=1))
    monthly_mes = mes_yield_from_records(month_start, target_date)

    owner_daily = _owner_daily_value(db, target_date, 'plant_daily_yield_rate')
    owner_yesterday = _owner_daily_value(db, target_date - timedelta(days=1), 'plant_daily_yield_rate')
    owner_monthly = _owner_daily_value(db, target_date, 'plant_monthly_yield_rate')

    daily = daily_mes or owner_daily or yield_from_entries(target_date, target_date) or calc_yield(today_data)
    yesterday = yesterday_mes or owner_yesterday or yield_from_entries(target_date - timedelta(days=1), target_date - timedelta(days=1)) or calc_yield(yesterday_data)
    monthly = monthly_mes or owner_monthly or yield_from_entries(month_start, target_date) or calc_yield(monthly_data)

    return {
        'daily': daily,
        'daily_delta': _delta(daily, yesterday),
        'monthly': monthly,
        'owner_daily': _owner_daily_value(db, target_date, 'plant_wide_yield_rate'),
        'basis': 'mes_yield_records' if any(value is not None for value in (daily_mes, yesterday_mes, monthly_mes)) else (
            'owner_daily_report' if owner_daily is not None or owner_monthly is not None else 'mobile_coil_yield_rate'
        ),
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
    available_energy_types = {
        str(energy_type).strip().lower()
        for energy_type in summary.get('available_energy_types') or []
        if energy_type
    }
    if available_energy_types:
        if 'electricity' not in available_energy_types:
            elec = None
        if 'gas' not in available_energy_types:
            gas = None
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
        'total_cost': round(elec_cost + gas_cost, 2) if elec_cost is not None and gas_cost is not None else None,
        'data_available': has_energy_data,
        'by_workshop': by_workshop,
    }


def _build_contracts(db: Session, target_date: date) -> dict:
    projection = build_contract_projection(db, target_date=target_date)
    daily_new = _round2(_to_float(projection.get('daily_contract_weight')))
    monthly_total = _round2(_to_float(projection.get('month_to_date_contract_weight')))
    remaining = _round2(_to_float(projection.get('remaining_contract_weight')))
    remaining_delta = _round2(_to_float(projection.get('remaining_contract_delta_weight')))
    projection_delta_raw = projection.get('remaining_contract_delta_weight')
    has_explicit_delta = (projection_delta_raw not in (None, '') and _to_float(projection_delta_raw) != 0) or any(
        item.get('remaining_contract_delta_weight') is not None
        for item in projection.get('items', [])
        if isinstance(item, dict)
    )
    if not has_explicit_delta and remaining is not None:
        previous_projection = build_contract_projection(db, target_date=target_date - timedelta(days=1))
        if previous_projection.get('quality_status') != 'missing':
            previous_remaining = _round2(_to_float(previous_projection.get('remaining_contract_weight')))
            if previous_remaining is not None:
                remaining_delta = _delta(remaining, previous_remaining)
    quality_status = projection.get('quality_status')
    has_contract_projection = quality_status != 'missing'

    return {
        'daily_new': daily_new,
        'monthly_total': monthly_total,
        'daily_input': (
            _round2(_to_float(projection.get('daily_input_weight'))) if has_contract_projection else None
        ),
        'monthly_input': (
            _round2(_to_float(projection.get('month_to_date_input_weight'))) if has_contract_projection else None
        ),
        'remaining': remaining,
        'remaining_delta': remaining_delta,
        'unit': '吨',
        'basis': 'owner_daily_contract_weight' if projection.get('owner_entry_count') else 'contract_projection',
        'quality_status': quality_status,
    }


def _build_cost(total_output: float, energy: dict) -> dict:
    elec_cost = energy.get('electricity_cost')
    gas_cost = energy.get('gas_cost')
    total = round(elec_cost + gas_cost, 2) if elec_cost is not None and gas_cost is not None else None
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


def _has_work_order_entry_table(db: Session) -> bool:
    try:
        return inspect(db.get_bind()).has_table(WorkOrderEntry.__tablename__)
    except Exception:
        return True


def _has_mes_stock_record_table(db: Session) -> bool:
    try:
        return inspect(db.get_bind()).has_table(MesStockRecord.__tablename__)
    except Exception:
        return True


def _has_mes_workshop_process_record_table(db: Session) -> bool:
    try:
        return inspect(db.get_bind()).has_table(MesWorkshopProcessRecord.__tablename__)
    except Exception:
        return True


def _has_mes_material_record_table(db: Session) -> bool:
    try:
        return inspect(db.get_bind()).has_table(MesMaterialRecord.__tablename__)
    except Exception:
        return True


def _has_mes_yield_record_table(db: Session) -> bool:
    try:
        return inspect(db.get_bind()).has_table(MesYieldRecord.__tablename__)
    except Exception:
        return True


def _query_latest_mobile_coil_rows(db: Session, start: date, end: date) -> list[WorkOrderEntry]:
    if not _has_work_order_entry_table(db):
        return []
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


def _plain_text(value: Any) -> str:
    return str(value or '').strip()


def _status_key(value: Any) -> str:
    text = _plain_text(value)
    return text[:-2] if text.endswith('.0') else text


def _source_payload(row: Any) -> dict:
    payload = getattr(row, 'source_payload', None)
    return dict(payload or {}) if isinstance(payload, dict) else {}


def _mes_output_tons(row: MesWorkshopProcessRecord) -> float:
    direct = _to_float(row.output_weight_tons)
    if direct > 0:
        return direct
    return _to_float(row.output_weight_kg) / 1000


def _is_mes_packaging_output(row: MesWorkshopProcessRecord) -> bool:
    return mes_factory_packaging_fact.is_factory_packaging_process(row)


def _mes_stock_output_tons(row: MesStockRecord) -> float:
    direct = _to_float(row.net_weight_tons)
    if direct > 0:
        return direct
    return _to_float(row.net_weight_kg) / 1000


def _is_mes_stock_packaging_output(row: MesStockRecord) -> bool:
    if row.source_path in {MES_DELIVERY_SOURCE_PATH, MES_DELIVERY_STOCK_SOURCE_PATH}:
        return False
    if row.source_path == MES_STOCK_HEADER_SOURCE_PATH:
        return _mes_stock_output_tons(row) > 0
    payload = _source_payload(row)
    from_department = _plain_text(payload.get('FromDepartment'))
    to_department = _plain_text(payload.get('ToDepartment'))
    status = _status_key(payload.get('Status') if 'Status' in payload else row.status_name)
    if status not in {'', '1', 'done', 'finished', '入库', '已入库', '正常'}:
        return False
    if to_department:
        if '半成品' in to_department:
            return False
        return to_department == '成品库' or '成品' in to_department or '入库' in to_department
    if from_department:
        return any(keyword in from_department for keyword in MES_STOCK_OUTPUT_FROM_DEPARTMENT_KEYWORDS)
    return _mes_stock_output_tons(row) > 0


def _is_mes_delivery_output(row: MesStockRecord) -> bool:
    if row.source_path not in {MES_DELIVERY_SOURCE_PATH, MES_DELIVERY_STOCK_SOURCE_PATH}:
        return False
    payload = _source_payload(row)
    delivery_code = _plain_text(payload.get('DeliveryCode'))
    return bool(delivery_code) and _mes_stock_output_tons(row) > 0


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


def _owner_storage_direct_inbound_tons(payload: dict) -> float:
    return _payload_number(payload, 'storage_inbound_weight') or 0.0


def _owner_storage_monthly_inbound_tons(payload: dict) -> float:
    direct_value = _payload_number(payload, 'storage_inbound_monthly')
    if direct_value is not None:
        return direct_value
    component_total = 0.0
    has_component = False
    for field_name in ('park_inbound_monthly', 'new_plant_inbound_monthly', 'park_to_storage_inbound_monthly'):
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
        .join(User, User.id == func.coalesce(WorkOrderEntry.created_by_user_id, WorkOrderEntry.created_by))
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_status.in_(tuple(SUBMITTED_STATUSES)),
            WorkOrderEntry.entry_type == 'owner_daily',
            WorkOrderEntry.machine_id.is_(None),
            User.role == STORAGE_OWNER_ROLE,
            or_(Workshop.code == 'CPK', Workshop.name == '成品库'),
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


def _query_owner_storage_direct_inbound_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    rows = (
        db.query(WorkOrderEntry)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .join(User, User.id == func.coalesce(WorkOrderEntry.created_by_user_id, WorkOrderEntry.created_by))
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_status.in_(tuple(SUBMITTED_STATUSES)),
            WorkOrderEntry.entry_type == 'owner_daily',
            WorkOrderEntry.machine_id.is_(None),
            User.role == STORAGE_OWNER_ROLE,
            or_(Workshop.code == 'CPK', Workshop.name == '成品库'),
        )
        .all()
    )
    totals: dict[date, float] = {}
    for row in rows:
        inbound_tons = _owner_storage_direct_inbound_tons(dict(row.extra_payload or {}))
        if inbound_tons <= 0:
            continue
        totals[row.business_date] = inbound_tons
    return totals


def _query_owner_storage_monthly_inbound_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    rows = (
        db.query(WorkOrderEntry)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .join(User, User.id == func.coalesce(WorkOrderEntry.created_by_user_id, WorkOrderEntry.created_by))
        .filter(
            WorkOrderEntry.business_date >= start,
            WorkOrderEntry.business_date <= end,
            WorkOrderEntry.entry_status.in_(tuple(SUBMITTED_STATUSES)),
            WorkOrderEntry.entry_type == 'owner_daily',
            WorkOrderEntry.machine_id.is_(None),
            User.role == STORAGE_OWNER_ROLE,
            or_(Workshop.code == 'CPK', Workshop.name == '成品库'),
        )
        .all()
    )
    totals: dict[date, float] = {}
    for row in rows:
        inbound_tons = _owner_storage_monthly_inbound_tons(dict(row.extra_payload or {}))
        if inbound_tons <= 0:
            continue
        totals[row.business_date] = inbound_tons
    return totals


def _query_finished_inbound_totals_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    return mes_factory_production_fact.query_finished_inbound_output_by_date(db, start, end)


def _query_mes_stock_packaging_output_by_date(
    db: Session,
    start: date,
    end: date,
    *,
    source_paths: set[str] | None = None,
) -> dict[date, float]:
    if db is None or not hasattr(db, "query") or not _has_mes_stock_record_table(db):
        return {}
    query = db.query(MesStockRecord).filter(MesStockRecord.business_date >= start, MesStockRecord.business_date <= end)
    if source_paths is not None:
        query = query.filter(MesStockRecord.source_path.in_(tuple(source_paths)))
    rows = query.all()
    totals: dict[date, float] = {}
    for row in rows:
        if row.business_date is None or not _is_mes_stock_packaging_output(row):
            continue
        output_tons = _mes_stock_output_tons(row)
        if output_tons <= 0:
            continue
        totals[row.business_date] = totals.get(row.business_date, 0.0) + output_tons
    return {business_date: _round2(total) or 0.0 for business_date, total in totals.items()}


def _query_mes_stock_packaging_row_counts_by_date(
    db: Session,
    start: date,
    end: date,
    *,
    source_paths: set[str] | None = None,
) -> dict[date, int]:
    if db is None or not hasattr(db, "query") or not _has_mes_stock_record_table(db):
        return {}
    query = db.query(MesStockRecord).filter(MesStockRecord.business_date >= start, MesStockRecord.business_date <= end)
    if source_paths is not None:
        query = query.filter(MesStockRecord.source_path.in_(tuple(source_paths)))
    counts: dict[date, int] = {}
    for row in query.all():
        if row.business_date is None or not _is_mes_stock_packaging_output(row):
            continue
        if _mes_stock_output_tons(row) <= 0:
            continue
        counts[row.business_date] = counts.get(row.business_date, 0) + 1
    return counts


def _query_mes_delivery_output_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    if db is None or not hasattr(db, "query") or not _has_mes_stock_record_table(db):
        return {}
    rows = (
        db.query(MesStockRecord)
        .filter(
            MesStockRecord.business_date >= start,
            MesStockRecord.business_date <= end,
            MesStockRecord.source_path.in_((MES_DELIVERY_SOURCE_PATH, MES_DELIVERY_STOCK_SOURCE_PATH)),
        )
        .all()
    )
    totals: dict[date, float] = {}
    for row in rows:
        if row.business_date is None or not _is_mes_delivery_output(row):
            continue
        output_tons = _mes_stock_output_tons(row)
        totals[row.business_date] = totals.get(row.business_date, 0.0) + output_tons
    return {business_date: _round2(total) or 0.0 for business_date, total in totals.items()}


def _query_mes_process_packaging_output_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    return mes_factory_packaging_fact.query_factory_packaging_output_by_date(db, start, end)


def _query_mes_process_packaging_row_counts_by_date(db: Session, start: date, end: date) -> dict[date, int]:
    return mes_factory_packaging_fact.query_factory_packaging_row_counts_by_date(db, start, end)


def _query_mes_packaging_output_with_source_by_date(db: Session, start: date, end: date) -> tuple[dict[date, float], dict[date, str]]:
    return mes_factory_packaging_fact.query_factory_packaging_output_with_source_by_date(db, start, end)


def _query_mes_packaging_row_counts_with_source_by_date(db: Session, start: date, end: date) -> dict[date, int]:
    return mes_factory_packaging_fact.query_factory_packaging_row_counts_by_date(db, start, end)


def _query_mes_packaging_output_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    totals, _sources = _query_mes_packaging_output_with_source_by_date(db, start, end)
    return totals


def _query_plant_output_totals_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    return _query_mes_packaging_output_by_date(db, start, end)


def _build_plant_output(db: Session, target_date: date, energy: dict) -> dict:
    month_start = target_date.replace(day=1)
    factory_production_fact = mes_factory_production_fact.build_factory_production_fact(db, target_date=target_date)
    mes_totals_by_date, mes_sources_by_date = _query_mes_packaging_output_with_source_by_date(db, month_start, target_date)
    mes_row_counts_by_date = _query_mes_packaging_row_counts_with_source_by_date(db, month_start, target_date)
    mes_home_fact = factory_production_fact.get('packaging_fact') or mes_home_packaging_fact.build_mes_home_packaging_fact(db, target_date=target_date)
    finished_inbound_fact = factory_production_fact.get('finished_inbound_fact') or {}
    feeding_fact = factory_production_fact.get('feeding_fact') or {}
    daily_output = mes_totals_by_date.get(target_date, 0.0)
    yesterday_output = mes_totals_by_date.get(target_date - timedelta(days=1), 0.0)
    mes_monthly_output = sum(mes_totals_by_date.values())
    if mes_home_fact.get('daily_row_count'):
        daily_output = _to_float(mes_home_fact.get('mes_home_daily_output'))
        mes_totals_by_date[target_date] = daily_output
        mes_sources_by_date[target_date] = 'mes_workshop_process_records'
        mes_row_counts_by_date[target_date] = int(mes_home_fact.get('daily_row_count') or 0)
    if mes_home_fact.get('month_row_count'):
        mes_monthly_output = _to_float(mes_home_fact.get('mes_home_month_to_date_output'))
    finished_inbound_output = _to_float(factory_production_fact.get('factory_finished_inbound_daily_output'))
    finished_inbound_monthly_output = _to_float(factory_production_fact.get('factory_finished_inbound_month_to_date_output'))
    monthly_output = mes_monthly_output
    monthly_output_source = 'mes_packaging_output'
    daily_output_source = mes_sources_by_date.get(target_date, 'mes_packaging_output')
    business_window_start, business_window_end = production_business_window(target_date)
    month_window_start, _month_window_end = production_business_window(month_start)
    packaging_business_day = mes_home_fact.get('business_day') or {}
    source_table_by_key = {
        'mes_stock_header_records': 'WMS_InStock',
        'mes_stock_records': 'WMS_InStockDetail',
        'mes_workshop_process_records': 'MES_ProductProcessRecord',
        'mes_packaging_output': 'mes_projection',
    }
    date_column_by_key = {
        'mes_stock_header_records': 'InStockDate',
        'mes_stock_records': 'CreateDate',
        'mes_workshop_process_records': 'business_date',
        'mes_packaging_output': 'business_date',
    }
    days_elapsed = max(1, target_date.day)
    total_electricity = _to_float(energy.get('total_electricity'))
    energy_per_ton = round(total_electricity / daily_output, 2) if daily_output > 0 and total_electricity > 0 else None
    return {
        'basis': 'mes_packaging_output',
        'basis_label': '包装产量',
        'business_day_start': production_business_day_start_label(),
        'daily_output_source': daily_output_source,
        'daily_output_source_table': source_table_by_key.get(daily_output_source),
        'daily_output_date_column': date_column_by_key.get(daily_output_source),
        'source_table': source_table_by_key.get(daily_output_source),
        'date_column': date_column_by_key.get(daily_output_source),
        'source_weight_field': 'EndWeight' if daily_output_source == 'mes_workshop_process_records' else None,
        'source_time_field': 'EndDatetime' if daily_output_source == 'mes_workshop_process_records' else None,
        'projection_table': 'mes_workshop_process_records' if daily_output_source == 'mes_workshop_process_records' else None,
        'projection_weight_field': 'output_weight_tons' if daily_output_source == 'mes_workshop_process_records' else None,
        'projection_date_field': 'business_date' if daily_output_source == 'mes_workshop_process_records' else None,
        'row_count': mes_row_counts_by_date.get(target_date, 0),
        'month_row_count': int(packaging_business_day.get('month_row_count') or sum(mes_row_counts_by_date.values())),
        'latest_row_id': packaging_business_day.get('latest_row_id'),
        'month_latest_row_id': packaging_business_day.get('month_latest_row_id'),
        'source_trace_id': packaging_business_day.get('trace_id'),
        'source_month_trace_id': packaging_business_day.get('month_trace_id'),
        'business_window_start': business_window_start.isoformat(),
        'business_window_end': business_window_end.isoformat(),
        'month_window_start': month_window_start.isoformat(),
        'monthly_output_source': monthly_output_source,
        'daily_output': _round2(daily_output),
        'yesterday_output': _round2(yesterday_output),
        'monthly_output': _round2(monthly_output),
        'monthly_average_output': _round2(monthly_output / days_elapsed),
        'packaging_output': _round2(daily_output),
        'packaging_monthly_output': _round2(monthly_output),
        'packaging_monthly_source': monthly_output_source,
        'packaging_monthly_average': _round2(monthly_output / days_elapsed),
        'packaging_basis_label': '包装产量',
        'mes_packaging_output': _round2(mes_totals_by_date.get(target_date, 0.0)),
        'mes_packaging_monthly_output': _round2(mes_monthly_output),
        'factory_production_fact': factory_production_fact,
        'factory_packaging_fact': mes_home_fact,
        'mes_home_packaging_fact': mes_home_fact,
        'factory_feeding_fact': feeding_fact,
        'factory_feeding_daily_input': _round2(factory_production_fact.get('factory_feeding_daily_input')),
        'factory_feeding_month_to_date_input': _round2(factory_production_fact.get('factory_feeding_month_to_date_input')),
        'finished_inbound_output': _round2(finished_inbound_output),
        'finished_inbound_row_count': int(finished_inbound_fact.get('daily_row_count') or 0),
        'finished_inbound_month_row_count': int(finished_inbound_fact.get('month_row_count') or 0),
        'finished_inbound_latest_row_id': finished_inbound_fact.get('daily_latest_row_id'),
        'finished_inbound_month_latest_row_id': finished_inbound_fact.get('month_latest_row_id'),
        'finished_inbound_trace_id': finished_inbound_fact.get('daily_trace_id'),
        'finished_inbound_month_trace_id': finished_inbound_fact.get('month_trace_id'),
        'finished_inbound_monthly_output': _round2(finished_inbound_monthly_output),
        'finished_inbound_monthly_average': _round2(finished_inbound_monthly_output / days_elapsed),
        'finished_inbound_basis_label': '全厂入库产量',
        'finished_inbound_source': (
            'mes_stock_header_records'
            if any(item.get('source_path') == MES_STOCK_HEADER_SOURCE_PATH for item in finished_inbound_fact.get('by_source', []))
            else 'mes_stock_records'
            if (finished_inbound_fact.get('daily_row_count') or 0) > 0
            else 'mes_stock_records_missing'
        ),
        'yield_rate': factory_production_fact.get('daily_yield_rate'),
        'monthly_yield_rate': factory_production_fact.get('month_yield_rate'),
        'yield_rate_source': factory_production_fact.get('yield_rate_source'),
        'energy_per_ton': energy_per_ton,
    }


def _build_shift_breakdown(db: Session, target_date: date) -> dict:
    latest_rows = _query_latest_mobile_coil_rows(db, target_date, target_date)
    shift_meta = {
        item.id: item
        for item in db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).all()
    }
    production_workshop_ids = {
        int(item.id)
        for item in db.query(Workshop).filter(Workshop.is_active.is_(True)).all()
        if _is_production_shift_workshop(item)
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

    def shift_meta_rank(meta: ShiftConfig | None, code: str) -> tuple[int, int]:
        meta_code = str(getattr(meta, 'code', '') or '').strip().upper()
        return (0 if meta_code == code else 1, int(getattr(meta, 'sort_order', 0) or 0))

    canonical_meta: dict[str, ShiftConfig] = {}
    for meta in shift_meta.values():
        bucket = canonical_shift_code(meta)
        if bucket is None:
            continue
        current = canonical_meta.get(bucket)
        if current is None or shift_meta_rank(meta, bucket) < shift_meta_rank(current, bucket):
            canonical_meta[bucket] = meta

    expected_workshops_by_shift: dict[str, set[int]] = {code: set() for code in SHIFT_ORDER}
    schedule_rows = (
        db.query(AttendanceSchedule.workshop_id, AttendanceSchedule.shift_config_id)
        .join(Workshop, Workshop.id == AttendanceSchedule.workshop_id)
        .filter(
            AttendanceSchedule.business_date == target_date,
            AttendanceSchedule.workshop_id.is_not(None),
            AttendanceSchedule.shift_config_id.is_not(None),
            Workshop.is_active.is_(True),
            Workshop.code.notin_(tuple(PRODUCTION_SHIFT_EXCLUDED_WORKSHOP_CODES)),
        )
        .distinct()
        .all()
    )
    for row in schedule_rows:
        bucket = canonical_shift_code(shift_meta.get(int(row.shift_config_id)))
        if bucket is None or row.workshop_id is None or int(row.workshop_id) not in production_workshop_ids:
            continue
        expected_workshops_by_shift[bucket].add(int(row.workshop_id))

    grouped: dict[str, dict[str, Any]] = {}
    for row in latest_rows:
        if row.shift_id is None:
            continue
        workshop_id = getattr(row, 'workshop_id', None)
        if workshop_id is not None and int(workshop_id) not in production_workshop_ids:
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
                'workshop_ids': set(),
            },
        )
        payload['total_output'] += round((_to_float(getattr(row, 'output_weight', None)) / 1000), 2)
        payload['total_energy'] += round(_to_float(getattr(row, 'energy_kwh', None)), 1)
        payload['entry_count'] += 1
        if workshop_id is not None:
            payload['workshop_ids'].add(int(workshop_id))

    shifts: list[dict[str, Any]] = []
    grand_output = 0.0
    grand_energy = 0.0
    for code in SHIFT_ORDER:
        bucket = grouped.get(code) or {}
        meta = bucket.get('meta') or canonical_meta.get(code)
        total_output = round(float(bucket.get('total_output') or 0.0), 2)
        total_energy = round(float(bucket.get('total_energy') or 0.0), 1)
        entry_count = int(bucket.get('entry_count') or 0)
        workshop_ids = bucket.get('workshop_ids') or set()
        workshop_count = len(workshop_ids)
        expected_workshops = len(expected_workshops_by_shift.get(code) or set()) or workshop_count
        grand_output += total_output
        grand_energy += total_energy
        shift_window = ''
        if meta is not None:
            shift_window = f"{meta.start_time.strftime('%H:%M')}-{meta.end_time.strftime('%H:%M')}"
        shifts.append({
            'shift_code': code,
            'shift_name': SHIFT_LABELS.get(code, meta.name if meta is not None else code),
            'shift_window': shift_window or SHIFT_WINDOWS.get(code, ''),
            'shift_count': entry_count,
            'total_output': total_output,
            'reported_workshops': workshop_count,
            'expected_workshops': expected_workshops,
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


def build_daily_production_overview(
    db: Session,
    *,
    target_date: date,
    wip_date: date | None = None,
) -> dict[str, Any]:
    effective_wip_date = wip_date or (target_date + timedelta(days=1))
    ws_map = _workshop_map(db)

    workshop_output = _build_workshop_output(db, target_date, ws_map)
    wip = _build_wip_distribution(db, effective_wip_date)
    yield_rates = _build_yield_rates(db, target_date)
    energy = _build_energy(db, target_date)
    contracts = _build_contracts(db, target_date)
    plant_output = _build_plant_output(db, target_date, energy)
    if plant_output.get('yield_rate') is not None:
        yield_rates['daily'] = plant_output.get('yield_rate')
        yield_rates['source'] = plant_output.get('yield_rate_source')
    if plant_output.get('monthly_yield_rate') is not None:
        yield_rates['monthly'] = plant_output.get('monthly_yield_rate')
        yield_rates['monthly_source'] = plant_output.get('yield_rate_source')
    shift_breakdown = _build_shift_breakdown(db, target_date)

    total_today = sum(r['daily_output'] or 0 for r in workshop_output)
    total_yesterday = sum(r['yesterday_output'] or 0 for r in workshop_output)
    total_monthly = sum(r['monthly_output'] or 0 for r in workshop_output)
    wip_total = sum(r['total_weight'] or 0 for r in wip)

    process_cost = _build_cost(total_today, energy)
    plant_cost = _build_cost(plant_output['daily_output'] or 0, energy)

    header_kpis = [
        {'key': 'plant_daily_output', 'label': '包装产量', 'value': plant_output['daily_output'], 'unit': '吨',
         'delta': _delta(plant_output['daily_output'], plant_output['yesterday_output']),
         'delta_label': _fmt_delta_label(_delta(plant_output['daily_output'], plant_output['yesterday_output']))},
        {'key': 'plant_inbound_output', 'label': '全厂入库产量', 'value': plant_output.get('finished_inbound_output'), 'unit': '吨'},
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
    fact_surface = build_persisted_daily_fact_surface(db, target_date=target_date)

    return {
        'target_date': target_date.isoformat(),
        'wip_business_date': effective_wip_date.isoformat(),
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
        **fact_surface,
    }
