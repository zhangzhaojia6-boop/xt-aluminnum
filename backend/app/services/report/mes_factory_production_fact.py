from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.business_time import (
    production_business_day_start_label,
    production_business_window,
    resolve_production_business_date,
)
from app.models.mes import MesCoilSnapshot, MesStockRecord
from app.services.report._utils import _to_float
from app.services.report import mes_factory_packaging_fact


FEEDING_SOURCE_TABLE = 'MES_Product'
FEEDING_SOURCE_WEIGHT_FIELD = 'FeedingWeight'
FEEDING_SOURCE_TIME_FIELD = 'CreateDate'
FEEDING_SOURCE_WORKSHOP_FIELD = 'CurrentWorkShop'
FEEDING_SOURCE_PAGES = (
    {'page': '计划管理 / 投料管理', 'path': '/Feeding/Index'},
    {'page': '计划管理 / 随行卡管理', 'path': '/FollowCard/Index'},
)
FEEDING_PROJECTION_TABLE = 'mes_coil_snapshots'
FEEDING_PROJECTION_WEIGHT_FIELD = 'feeding_weight'
FINISHED_INBOUND_SOURCE_TABLES = ('WMS_InStock', 'WMS_InStockDetail')
FINISHED_INBOUND_WEIGHT_FIELD = 'TotalNetWeight/NetWeight'
FINISHED_INBOUND_TIME_FIELD = 'InStockDate/CreateDate'
FINISHED_INBOUND_HEADER_SOURCE_PATH = 'sqlserver:stock_header_records'
FINISHED_INBOUND_DETAIL_SOURCE_PATH = 'sqlserver:stock_records'
BUSINESS_DAY_START_LABEL = production_business_day_start_label()
BUSINESS_DAY_WINDOW_KEY = 'business_day_0750'
BUSINESS_DAY_POLICY = {
    'default': '07:50-07:50',
    '铸二': '10:00-10:00',
    '铸三': '10:00-10:00',
    '热轧': '10:00-10:00',
}
MES_HOME_REFERENCE_SOURCE_UNAVAILABLE = 'unavailable'
MES_READ_MODE = 'projection_cache_with_read_only_sqlserver_reconciliation'


def _round2(value: float | None) -> float:
    return round(float(value or 0.0), 2)


def _plain_text(value: Any) -> str:
    return str(value or '').strip()


def _source_payload(row: Any) -> dict[str, Any]:
    payload = getattr(row, 'source_payload', None)
    if not isinstance(payload, dict):
        return {}
    metadata = payload.get('metadata')
    if isinstance(metadata, dict):
        merged = dict(metadata)
        merged.update({key: value for key, value in payload.items() if key != 'metadata'})
        return merged
    return dict(payload)


def _payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ''):
            return payload[key]
    projection = payload.get('projection')
    if isinstance(projection, dict):
        for key in keys:
            if key in projection and projection[key] not in (None, ''):
                return projection[key]
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if value in (None, ''):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        pass
    for fmt in (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y-%m-%d',
        '%Y/%m/%d',
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _row_create_time(row: MesCoilSnapshot) -> datetime | None:
    payload = _source_payload(row)
    return (
        _parse_datetime(_payload_value(payload, 'CreateDate', 'StrCreateDate', 'CreateTime'))
        or getattr(row, 'event_time', None)
        or getattr(row, 'updated_from_mes_at', None)
    )


def _row_business_date_from_create_time(row: MesCoilSnapshot) -> date | None:
    created_at = _row_create_time(row)
    if created_at is not None:
        return resolve_production_business_date(created_at, workshop_name=_feeding_workshop(row))
    return getattr(row, 'business_date', None)


def _feeding_workshop(row: MesCoilSnapshot) -> str:
    payload = _source_payload(row)
    return _plain_text(
        getattr(row, 'current_workshop', None)
        or _payload_value(payload, 'CurrentWorkShop', 'WorkShopName', 'WorkshopName')
        or getattr(row, 'workshop_code', None)
    )


def _feeding_weight(row: MesCoilSnapshot) -> float:
    direct = _to_float(getattr(row, 'feeding_weight', None))
    if direct > 0:
        return direct
    payload = _source_payload(row)
    return _to_float(_payload_value(payload, 'FeedingWeight'))


def _feeding_rows(db: Session, start: date, end: date) -> list[MesCoilSnapshot]:
    window_start, _ = production_business_window(start)
    _, window_end = production_business_window(end)
    return (
        db.query(MesCoilSnapshot)
        .filter(
            or_(
                MesCoilSnapshot.business_date.between(start, end),
                and_(MesCoilSnapshot.event_time >= window_start, MesCoilSnapshot.event_time < window_end),
                and_(MesCoilSnapshot.business_date.is_(None), MesCoilSnapshot.event_time.is_(None)),
            )
        )
        .all()
    )


def _sum_feeding_rows(rows: list[MesCoilSnapshot], start: date, end: date) -> dict[str, Any]:
    total = 0.0
    row_count = 0
    latest_seen = None
    by_workshop: dict[str, dict[str, Any]] = {}
    for row in rows:
        business_date = _row_business_date_from_create_time(row)
        if business_date is None or business_date < start or business_date > end:
            continue
        workshop = _feeding_workshop(row)
        if not workshop:
            continue
        feeding = _feeding_weight(row)
        if feeding <= 0:
            continue
        total += feeding
        row_count += 1
        if row.last_seen_from_mes_at is not None and (
            latest_seen is None or row.last_seen_from_mes_at > latest_seen
        ):
            latest_seen = row.last_seen_from_mes_at
        bucket = by_workshop.setdefault(
            workshop,
            {
                'workshop_name': workshop,
                'business_day_start': production_business_day_start_label(workshop),
                'input': 0.0,
                'row_count': 0,
            },
        )
        bucket['input'] += feeding
        bucket['row_count'] += 1
    return {
        'input': _round2(total),
        'row_count': row_count,
        'last_seen_from_mes_at': latest_seen.isoformat() if latest_seen is not None else None,
        'by_workshop': [
            {
                'workshop_name': item['workshop_name'],
                'business_day_start': item['business_day_start'],
                'input': _round2(item['input']),
                'row_count': item['row_count'],
            }
            for item in sorted(by_workshop.values(), key=lambda item: item['workshop_name'])
        ],
    }


def _stock_weight_tons(row: MesStockRecord) -> float:
    direct = _to_float(getattr(row, 'net_weight_tons', None))
    if direct > 0:
        return direct
    return _to_float(getattr(row, 'net_weight_kg', None)) / 1000


def _finished_inbound_rows(db: Session, start: date, end: date) -> list[MesStockRecord]:
    return (
        db.query(MesStockRecord)
        .filter(
            MesStockRecord.business_date >= start,
            MesStockRecord.business_date <= end,
            MesStockRecord.source_path.in_((FINISHED_INBOUND_HEADER_SOURCE_PATH, FINISHED_INBOUND_DETAIL_SOURCE_PATH)),
        )
        .all()
    )


def _sum_finished_inbound_rows(rows: list[MesStockRecord]) -> dict[str, Any]:
    total = 0.0
    row_count = 0
    latest_seen = None
    latest_row_id = None
    by_source: dict[str, dict[str, Any]] = {}
    rows_by_date: dict[date | None, list[MesStockRecord]] = {}
    for row in rows:
        rows_by_date.setdefault(getattr(row, 'business_date', None), []).append(row)
    selected_rows: list[MesStockRecord] = []
    for date_rows in rows_by_date.values():
        header_rows = [row for row in date_rows if row.source_path == FINISHED_INBOUND_HEADER_SOURCE_PATH]
        selected_rows.extend(header_rows or date_rows)
    for row in selected_rows:
        weight = _stock_weight_tons(row)
        if weight <= 0:
            continue
        total += weight
        row_count += 1
        latest_row_id = max(latest_row_id or 0, int(row.id or 0))
        if row.last_seen_from_mes_at is not None and (
            latest_seen is None or row.last_seen_from_mes_at > latest_seen
        ):
            latest_seen = row.last_seen_from_mes_at
        source_path = str(row.source_path or '')
        bucket = by_source.setdefault(source_path, {'source_path': source_path, 'output': 0.0, 'row_count': 0})
        bucket['output'] += weight
        bucket['row_count'] += 1
    return {
        'output': _round2(total),
        'row_count': row_count,
        'last_seen_from_mes_at': latest_seen.isoformat() if latest_seen is not None else None,
        'latest_row_id': latest_row_id,
        'trace_id': (
            f'projection-read:mes_stock_records:{latest_row_id}:{row_count}'
            if row_count > 0
            else None
        ),
        'by_source': [
            {
                'source_path': item['source_path'],
                'output': _round2(item['output']),
                'row_count': item['row_count'],
            }
            for item in sorted(by_source.values(), key=lambda item: item['source_path'])
        ],
    }


def query_factory_feeding_input_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    if db is None or not hasattr(db, 'query'):
        return {}
    try:
        rows = _feeding_rows(db, start, end)
    except (AttributeError, SQLAlchemyError):
        return {}
    totals: dict[date, float] = {}
    for row in rows:
        business_date = _row_business_date_from_create_time(row)
        if business_date is None or business_date < start or business_date > end:
            continue
        if not _feeding_workshop(row):
            continue
        feeding = _feeding_weight(row)
        if feeding <= 0:
            continue
        totals[business_date] = totals.get(business_date, 0.0) + feeding
    return {business_date: _round2(total) for business_date, total in totals.items()}


def query_finished_inbound_output_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    if db is None or not hasattr(db, 'query'):
        return {}
    try:
        rows = _finished_inbound_rows(db, start, end)
    except (AttributeError, SQLAlchemyError):
        return {}
    rows_by_date: dict[date, list[MesStockRecord]] = {}
    for row in rows:
        if row.business_date is not None:
            rows_by_date.setdefault(row.business_date, []).append(row)
    totals: dict[date, float] = {}
    for business_date, date_rows in rows_by_date.items():
        header_rows = [row for row in date_rows if row.source_path == FINISHED_INBOUND_HEADER_SOURCE_PATH]
        selected_rows = header_rows or date_rows
        total = 0.0
        for row in selected_rows:
            weight = _stock_weight_tons(row)
            if weight <= 0:
                continue
            total += weight
        if total <= 0:
            continue
        totals[business_date] = total
    return {business_date: _round2(total) for business_date, total in totals.items()}


def build_factory_feeding_fact(db: Session, *, target_date: date) -> dict[str, Any]:
    month_start = target_date.replace(day=1)
    try:
        business_start_at, business_end_at = production_business_window(target_date)
        month_start_at, _unused = production_business_window(month_start)
        rows = _feeding_rows(db, month_start, target_date)
        daily = _sum_feeding_rows(rows, target_date, target_date)
        monthly = _sum_feeding_rows(rows, month_start, target_date)
    except (AttributeError, SQLAlchemyError):
        business_start_at, business_end_at = production_business_window(target_date)
        month_start_at, _unused = production_business_window(month_start)
        daily = {'input': 0.0, 'row_count': 0, 'last_seen_from_mes_at': None, 'by_workshop': []}
        monthly = {'input': 0.0, 'row_count': 0, 'last_seen_from_mes_at': None, 'by_workshop': []}
    return {
        'target_date': target_date.isoformat(),
        'month_start': month_start.isoformat(),
        'selected_window': BUSINESS_DAY_WINDOW_KEY,
        'business_day_start': BUSINESS_DAY_START_LABEL,
        'business_day_policy': BUSINESS_DAY_POLICY,
        'read_mode': MES_READ_MODE,
        'business_window_start': business_start_at.isoformat(),
        'business_window_end': business_end_at.isoformat(),
        'month_window_start': month_start_at.isoformat(),
        'source_table': FEEDING_SOURCE_TABLE,
        'source_weight_field': FEEDING_SOURCE_WEIGHT_FIELD,
        'source_time_field': FEEDING_SOURCE_TIME_FIELD,
        'source_workshop_field': FEEDING_SOURCE_WORKSHOP_FIELD,
        'source_pages': list(FEEDING_SOURCE_PAGES),
        'projection_table': FEEDING_PROJECTION_TABLE,
        'projection_weight_field': FEEDING_PROJECTION_WEIGHT_FIELD,
        'factory_feeding_daily_input': daily['input'],
        'factory_feeding_month_to_date_input': monthly['input'],
        'daily_row_count': daily['row_count'],
        'month_row_count': monthly['row_count'],
        'last_seen_from_mes_at': monthly['last_seen_from_mes_at'] or daily['last_seen_from_mes_at'],
        'by_workshop': daily['by_workshop'],
        'month_by_workshop': monthly['by_workshop'],
    }


def build_finished_inbound_fact(db: Session, *, target_date: date) -> dict[str, Any]:
    month_start = target_date.replace(day=1)
    try:
        daily = _sum_finished_inbound_rows(_finished_inbound_rows(db, target_date, target_date))
        monthly = _sum_finished_inbound_rows(_finished_inbound_rows(db, month_start, target_date))
    except (AttributeError, SQLAlchemyError):
        daily = {
            'output': 0.0,
            'row_count': 0,
            'last_seen_from_mes_at': None,
            'latest_row_id': None,
            'trace_id': None,
            'by_source': [],
        }
        monthly = {
            'output': 0.0,
            'row_count': 0,
            'last_seen_from_mes_at': None,
            'latest_row_id': None,
            'trace_id': None,
            'by_source': [],
        }
    return {
        'target_date': target_date.isoformat(),
        'month_start': month_start.isoformat(),
        'selected_window': BUSINESS_DAY_WINDOW_KEY,
        'business_day_start': BUSINESS_DAY_START_LABEL,
        'business_day_policy': BUSINESS_DAY_POLICY,
        'read_mode': MES_READ_MODE,
        'source_tables': list(FINISHED_INBOUND_SOURCE_TABLES),
        'source_weight_field': FINISHED_INBOUND_WEIGHT_FIELD,
        'source_time_field': FINISHED_INBOUND_TIME_FIELD,
        'projection_table': 'mes_stock_records',
        'factory_finished_inbound_daily_output': daily['output'],
        'factory_finished_inbound_month_to_date_output': monthly['output'],
        'daily_row_count': daily['row_count'],
        'month_row_count': monthly['row_count'],
        'daily_latest_row_id': daily['latest_row_id'],
        'month_latest_row_id': monthly['latest_row_id'],
        'daily_trace_id': daily['trace_id'],
        'month_trace_id': monthly['trace_id'],
        'last_seen_from_mes_at': monthly['last_seen_from_mes_at'] or daily['last_seen_from_mes_at'],
        'by_source': daily['by_source'],
        'month_by_source': monthly['by_source'],
    }


def build_factory_production_fact(db: Session, *, target_date: date) -> dict[str, Any]:
    feeding = build_factory_feeding_fact(db, target_date=target_date)
    packaging = mes_factory_packaging_fact.build_factory_packaging_fact(db, target_date=target_date)
    inbound = build_finished_inbound_fact(db, target_date=target_date)
    daily_feeding = _to_float(feeding.get('factory_feeding_daily_input'))
    month_feeding = _to_float(feeding.get('factory_feeding_month_to_date_input'))
    daily_inbound = _to_float(inbound.get('factory_finished_inbound_daily_output'))
    month_inbound = _to_float(inbound.get('factory_finished_inbound_month_to_date_output'))
    return {
        'target_date': target_date.isoformat(),
        'month_start': target_date.replace(day=1).isoformat(),
        'business_day_start': BUSINESS_DAY_START_LABEL,
        'business_day_policy': BUSINESS_DAY_POLICY,
        'read_mode': MES_READ_MODE,
        'feeding_fact': feeding,
        'packaging_fact': packaging,
        'finished_inbound_fact': inbound,
        'factory_feeding_daily_input': daily_feeding,
        'factory_feeding_month_to_date_input': month_feeding,
        'factory_packaging_daily_output': _to_float(packaging.get('factory_packaging_daily_output')),
        'factory_packaging_month_to_date_output': _to_float(packaging.get('factory_packaging_month_to_date_output')),
        'factory_finished_inbound_daily_output': daily_inbound,
        'factory_finished_inbound_month_to_date_output': month_inbound,
        'daily_yield_rate': None,
        'month_yield_rate': None,
        'yield_rate_source': 'unavailable_requires_same_basis',
        'feeding_daily_delta': None,
        'feeding_month_to_date_delta': None,
        'source_table': FEEDING_SOURCE_TABLE,
        'source_weight_field': FEEDING_SOURCE_WEIGHT_FIELD,
        'source_time_field': FEEDING_SOURCE_TIME_FIELD,
        'feeding_source_pages': list(FEEDING_SOURCE_PAGES),
    }


def _delta(actual: float | None, expected: float | None) -> float | None:
    if expected is None:
        return None
    return round(_to_float(actual) - _to_float(expected), 2)


def build_factory_production_reconciliation(db: Session, *, target_date: date) -> dict[str, Any]:
    fact = build_factory_production_fact(db, target_date=target_date)
    reference: dict[str, float] = {}
    feeding_reference_daily = None
    feeding_reference_month = None
    packaging_reference_finishing = None
    packaging_by_workshop = (
        fact.get('packaging_fact', {})
        .get('business_day', {})
        .get('by_workshop', [])
    )
    finishing_packaging = next(
        (_to_float(item.get('output')) for item in packaging_by_workshop if item.get('workshop_name') == '精整'),
        None,
    )
    return {
        **fact,
        'source_mapping': {
            'mes_home_feeding': {
                'page': 'MES 投料/随行卡投料',
                'source_pages': list(FEEDING_SOURCE_PAGES),
                'source_table': FEEDING_SOURCE_TABLE,
                'source_weight_field': FEEDING_SOURCE_WEIGHT_FIELD,
                'source_time_field': FEEDING_SOURCE_TIME_FIELD,
                'filter': f'{FEEDING_SOURCE_WORKSHOP_FIELD} 非空',
                'projection_table': FEEDING_PROJECTION_TABLE,
            },
            'mes_feeding_management': {
                'page': 'MES 投料管理',
                'endpoint': '/Feeding/Index',
                'source_table': FEEDING_SOURCE_TABLE,
                'source_weight_field': FEEDING_SOURCE_WEIGHT_FIELD,
                'source_time_field': FEEDING_SOURCE_TIME_FIELD,
                'projection_table': FEEDING_PROJECTION_TABLE,
            },
            'mes_follow_card_management': {
                'page': 'MES 随行卡管理',
                'endpoint': '/FollowCard/Index',
                'source_table': FEEDING_SOURCE_TABLE,
                'source_weight_field': FEEDING_SOURCE_WEIGHT_FIELD,
                'source_time_field': FEEDING_SOURCE_TIME_FIELD,
                'projection_table': FEEDING_PROJECTION_TABLE,
            },
            'mes_packaging': {
                'page': 'MES 包装统计',
                'source_pages': list(mes_factory_packaging_fact.PACKAGING_SOURCE_PAGES),
                'source_table': mes_factory_packaging_fact.FACT_SOURCE_TABLE,
                'source_weight_field': mes_factory_packaging_fact.FACT_WEIGHT_FIELD,
                'source_time_field': mes_factory_packaging_fact.FACT_TIME_FIELD,
                'filter': f'{mes_factory_packaging_fact.FACT_PROCESS_FIELD}=包装',
                'projection_table': mes_factory_packaging_fact.FACT_PROJECTION_TABLE,
            },
            'mes_finished_transfer': {
                'page': 'MES 成品调拨单',
                'endpoint': '/Allocation/Index',
                'source_tables': ['WMS_InStockDetail', 'WMS_OutStockDetail'],
                'source_weight_field': 'NetWeight',
                'source_time_field': 'CreateDate/AllocationDate',
                'projection_table': 'mes_stock_records',
            },
            'finished_inbound': {
                'page': 'MES 成品库/入库',
                'source_tables': list(FINISHED_INBOUND_SOURCE_TABLES),
                'source_weight_field': FINISHED_INBOUND_WEIGHT_FIELD,
                'source_time_field': FINISHED_INBOUND_TIME_FIELD,
                'projection_table': 'mes_stock_records',
            },
        },
        'mes_home_reference': reference,
        'mes_home_reference_source': MES_HOME_REFERENCE_SOURCE_UNAVAILABLE,
        'feeding_daily_delta': _delta(fact.get('factory_feeding_daily_input'), feeding_reference_daily),
        'feeding_month_to_date_delta': _delta(fact.get('factory_feeding_month_to_date_input'), feeding_reference_month),
        'finishing_packaging_daily_output': finishing_packaging,
        'finishing_packaging_daily_delta': _delta(finishing_packaging, packaging_reference_finishing),
    }
