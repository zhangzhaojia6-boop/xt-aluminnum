from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.business_time import production_business_window
from app.models.mes import MesWorkshopProcessRecord
from app.services.report._utils import _to_float


FACT_SOURCE_KEY = 'mes_workshop_process_records'
FACT_SOURCE_PATH = 'sqlserver:workshop_process_records'
FACT_SOURCE_TABLE = 'MES_ProductProcessRecord'
FACT_WEIGHT_FIELD = 'EndWeight'
FACT_TIME_FIELD = 'EndDatetime'
FACT_PROCESS_FIELD = 'Process'
FACT_WORKSHOP_FIELD = 'WorkShop'
FACT_PROJECTION_TABLE = 'mes_workshop_process_records'
FACT_PROJECTION_WEIGHT_FIELD = 'output_weight_tons'
FACT_PROJECTION_TIME_FIELD = 'end_time'
FACT_PROJECTION_DATE_FIELD = 'business_date'
PACKAGING_PROCESS_KEYWORD = '包装'
BUSINESS_DAY_START_LABEL = '07:30'
WORKSHOP_ALIAS_MAP = {
    '园区精整': '园区剪切',
    '园区精整车间': '园区剪切',
    '园区剪切车间': '园区剪切',
}


def _round2(value: float | None) -> float:
    return round(float(value or 0.0), 2)


def _plain_text(value: Any) -> str:
    return str(value or '').strip()


def normalize_packaging_workshop_name(workshop_name: Any) -> str:
    text = _plain_text(workshop_name)
    if not text:
        return '未标注车间'
    for source, target in WORKSHOP_ALIAS_MAP.items():
        if source in text:
            return target
    if '园区剪切' in text:
        return '园区剪切'
    if '拉矫' in text:
        return '拉矫'
    if '精整' in text:
        return '精整'
    return text


def is_factory_packaging_process(row: MesWorkshopProcessRecord) -> bool:
    process_name = _plain_text(getattr(row, 'process_name', None))
    return PACKAGING_PROCESS_KEYWORD in process_name


def _output_tons(row: MesWorkshopProcessRecord) -> float:
    direct = _to_float(getattr(row, 'output_weight_tons', None))
    if direct > 0:
        return direct
    return _to_float(getattr(row, 'output_weight_kg', None)) / 1000


def _empty_sum() -> dict[str, Any]:
    return {
        'output': 0.0,
        'row_count': 0,
        'last_seen_from_mes_at': None,
        'by_workshop': [],
    }


def _sum_rows(rows: list[MesWorkshopProcessRecord]) -> dict[str, Any]:
    total = 0.0
    row_count = 0
    latest_seen = None
    by_workshop: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not is_factory_packaging_process(row):
            continue
        output = _output_tons(row)
        if output <= 0:
            continue
        row_count += 1
        total += output
        if row.last_seen_from_mes_at is not None and (
            latest_seen is None or row.last_seen_from_mes_at > latest_seen
        ):
            latest_seen = row.last_seen_from_mes_at
        workshop_name = normalize_packaging_workshop_name(row.workshop_name)
        bucket = by_workshop.setdefault(
            workshop_name,
            {'workshop_name': workshop_name, 'output': 0.0, 'row_count': 0},
        )
        bucket['output'] += output
        bucket['row_count'] += 1
    if row_count == 0:
        return _empty_sum()
    return {
        'output': _round2(total),
        'row_count': row_count,
        'last_seen_from_mes_at': latest_seen.isoformat() if latest_seen is not None else None,
        'by_workshop': [
            {
                'workshop_name': item['workshop_name'],
                'output': _round2(item['output']),
                'row_count': item['row_count'],
            }
            for item in sorted(by_workshop.values(), key=lambda item: item['workshop_name'])
        ],
    }


def _rows_by_business_date(db: Session, start: date, end: date) -> list[MesWorkshopProcessRecord]:
    return (
        db.query(MesWorkshopProcessRecord)
        .filter(
            MesWorkshopProcessRecord.business_date >= start,
            MesWorkshopProcessRecord.business_date <= end,
        )
        .all()
    )


def _rows_by_natural_time(db: Session, start_at: datetime, end_at: datetime) -> list[MesWorkshopProcessRecord]:
    return (
        db.query(MesWorkshopProcessRecord)
        .filter(
            MesWorkshopProcessRecord.end_time >= start_at,
            MesWorkshopProcessRecord.end_time < end_at,
        )
        .all()
    )


def _natural_window(target_date: date) -> tuple[datetime, datetime]:
    start_at = datetime.combine(target_date, time.min)
    return start_at, start_at + timedelta(days=1)


def query_factory_packaging_output_by_date(db: Session, start: date, end: date) -> dict[date, float]:
    if db is None or not hasattr(db, 'query'):
        return {}
    rows = _rows_by_business_date(db, start, end)
    totals: dict[date, float] = {}
    for row in rows:
        if row.business_date is None or not is_factory_packaging_process(row):
            continue
        output = _output_tons(row)
        if output <= 0:
            continue
        totals[row.business_date] = totals.get(row.business_date, 0.0) + output
    return {business_date: _round2(total) for business_date, total in totals.items()}


def query_factory_packaging_row_counts_by_date(db: Session, start: date, end: date) -> dict[date, int]:
    if db is None or not hasattr(db, 'query'):
        return {}
    rows = _rows_by_business_date(db, start, end)
    counts: dict[date, int] = {}
    for row in rows:
        if row.business_date is None or not is_factory_packaging_process(row):
            continue
        if _output_tons(row) <= 0:
            continue
        counts[row.business_date] = counts.get(row.business_date, 0) + 1
    return counts


def query_factory_packaging_output_with_source_by_date(
    db: Session,
    start: date,
    end: date,
) -> tuple[dict[date, float], dict[date, str]]:
    totals = query_factory_packaging_output_by_date(db, start, end)
    return totals, {business_date: FACT_SOURCE_KEY for business_date in totals}


def _build_empty_fact(target_date: date) -> dict[str, Any]:
    month_start = target_date.replace(day=1)
    return {
        'target_date': target_date.isoformat(),
        'month_start': month_start.isoformat(),
        'selected_window': 'business_day_0730',
        'business_day_start': BUSINESS_DAY_START_LABEL,
        'source_kind': 'factory_packaging_process',
        'source_table': FACT_SOURCE_TABLE,
        'source_weight_field': FACT_WEIGHT_FIELD,
        'source_time_field': FACT_TIME_FIELD,
        'source_process_field': FACT_PROCESS_FIELD,
        'source_workshop_field': FACT_WORKSHOP_FIELD,
        'projection_table': FACT_PROJECTION_TABLE,
        'projection_weight_field': FACT_PROJECTION_WEIGHT_FIELD,
        'projection_time_field': FACT_PROJECTION_TIME_FIELD,
        'projection_date_field': FACT_PROJECTION_DATE_FIELD,
        'source_path': FACT_SOURCE_PATH,
        'process_filter': PACKAGING_PROCESS_KEYWORD,
        'workshop_aliases': WORKSHOP_ALIAS_MAP,
        'factory_packaging_daily_output': 0.0,
        'factory_packaging_month_to_date_output': 0.0,
        'mes_home_daily_output': 0.0,
        'mes_home_month_to_date_output': 0.0,
        'daily_row_count': 0,
        'month_row_count': 0,
        'business_day': {},
        'natural_day': {},
    }


def build_factory_packaging_fact(db: Session, *, target_date: date) -> dict[str, Any]:
    month_start = target_date.replace(day=1)
    try:
        business_start_at, business_end_at = production_business_window(target_date)
        natural_start_at, natural_end_at = _natural_window(target_date)
        business_daily = _sum_rows(_rows_by_business_date(db, target_date, target_date))
        business_month = _sum_rows(_rows_by_business_date(db, month_start, target_date))
        natural_daily = _sum_rows(_rows_by_natural_time(db, natural_start_at, natural_end_at))
        natural_month = _sum_rows(
            _rows_by_natural_time(
                db,
                datetime.combine(month_start, time.min),
                natural_end_at,
            )
        )
    except (AttributeError, SQLAlchemyError):
        return _build_empty_fact(target_date)

    return {
        'target_date': target_date.isoformat(),
        'month_start': month_start.isoformat(),
        'selected_window': 'business_day_0730',
        'business_day_start': BUSINESS_DAY_START_LABEL,
        'source_kind': 'factory_packaging_process',
        'source_table': FACT_SOURCE_TABLE,
        'source_weight_field': FACT_WEIGHT_FIELD,
        'source_time_field': FACT_TIME_FIELD,
        'source_process_field': FACT_PROCESS_FIELD,
        'source_workshop_field': FACT_WORKSHOP_FIELD,
        'projection_table': FACT_PROJECTION_TABLE,
        'projection_weight_field': FACT_PROJECTION_WEIGHT_FIELD,
        'projection_time_field': FACT_PROJECTION_TIME_FIELD,
        'projection_date_field': FACT_PROJECTION_DATE_FIELD,
        'source_path': FACT_SOURCE_PATH,
        'process_filter': PACKAGING_PROCESS_KEYWORD,
        'workshop_aliases': WORKSHOP_ALIAS_MAP,
        'factory_packaging_daily_output': business_daily['output'],
        'factory_packaging_month_to_date_output': business_month['output'],
        'mes_home_daily_output': business_daily['output'],
        'mes_home_month_to_date_output': business_month['output'],
        'daily_row_count': business_daily['row_count'],
        'month_row_count': business_month['row_count'],
        'last_seen_from_mes_at': business_month['last_seen_from_mes_at'] or business_daily['last_seen_from_mes_at'],
        'business_day': {
            'window_start': business_start_at.isoformat(),
            'window_end': business_end_at.isoformat(),
            'daily_output': business_daily['output'],
            'month_to_date_output': business_month['output'],
            'daily_row_count': business_daily['row_count'],
            'month_row_count': business_month['row_count'],
            'by_workshop': business_daily['by_workshop'],
            'month_by_workshop': business_month['by_workshop'],
        },
        'natural_day': {
            'window_start': natural_start_at.isoformat(),
            'window_end': natural_end_at.isoformat(),
            'daily_output': natural_daily['output'],
            'month_to_date_output': natural_month['output'],
            'daily_row_count': natural_daily['row_count'],
            'month_row_count': natural_month['row_count'],
            'by_workshop': natural_daily['by_workshop'],
            'month_by_workshop': natural_month['by_workshop'],
        },
    }


def build_factory_packaging_reconciliation(db: Session, *, target_date: date) -> dict[str, Any]:
    fact = build_factory_packaging_fact(db, target_date=target_date)
    daily_output = fact['factory_packaging_daily_output']
    month_output = fact['factory_packaging_month_to_date_output']
    return {
        **fact,
        'current_dashboard_daily_output': daily_output,
        'current_dashboard_month_to_date_output': month_output,
        'daily_delta': 0.0,
        'month_delta': 0.0,
    }
