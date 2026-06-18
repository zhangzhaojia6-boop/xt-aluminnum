from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.mes import MesStockRecord
from app.services.report._utils import _to_float


MES_HOME_SOURCE_PATH = 'sqlserver:stock_header_records'
MES_HOME_SOURCE_TABLE = 'WMS_InStock'
MES_HOME_WEIGHT_FIELD = 'TotalNetWeight'
MES_HOME_TIME_FIELD = 'InStockDate'
MES_HOME_PROJECTION_TABLE = 'mes_stock_records'
BUSINESS_DAY_START = time(7, 30)


def _round2(value: float | None) -> float:
    return round(float(value or 0.0), 2)


def _weight_tons(row: MesStockRecord) -> float:
    direct = _to_float(row.net_weight_tons)
    if direct > 0:
        return direct
    return _to_float(row.net_weight_kg) / 1000


def _sum_rows(rows: list[MesStockRecord]) -> dict[str, Any]:
    total = 0.0
    latest_seen = None
    for row in rows:
        weight = _weight_tons(row)
        if weight <= 0:
            continue
        total += weight
        if row.last_seen_from_mes_at is not None and (
            latest_seen is None or row.last_seen_from_mes_at > latest_seen
        ):
            latest_seen = row.last_seen_from_mes_at
    counted = [row for row in rows if _weight_tons(row) > 0]
    return {
        'output': _round2(total),
        'row_count': len(counted),
        'last_seen_from_mes_at': latest_seen.isoformat() if latest_seen is not None else None,
    }


def _header_rows_by_business_date(db: Session, start: date, end: date) -> list[MesStockRecord]:
    return (
        db.query(MesStockRecord)
        .filter(
            MesStockRecord.source_path == MES_HOME_SOURCE_PATH,
            MesStockRecord.business_date >= start,
            MesStockRecord.business_date <= end,
        )
        .all()
    )


def _header_rows_by_natural_time(db: Session, start_at: datetime, end_at: datetime) -> list[MesStockRecord]:
    return (
        db.query(MesStockRecord)
        .filter(
            MesStockRecord.source_path == MES_HOME_SOURCE_PATH,
            MesStockRecord.in_stock_date >= start_at,
            MesStockRecord.in_stock_date < end_at,
        )
        .all()
    )


def _business_window(target_date: date) -> tuple[datetime, datetime]:
    start_at = datetime.combine(target_date, BUSINESS_DAY_START)
    return start_at, start_at + timedelta(days=1)


def _natural_window(target_date: date) -> tuple[datetime, datetime]:
    start_at = datetime.combine(target_date, time.min)
    return start_at, start_at + timedelta(days=1)


def _build_empty_fact(target_date: date) -> dict[str, Any]:
    month_start = target_date.replace(day=1)
    return {
        'target_date': target_date.isoformat(),
        'month_start': month_start.isoformat(),
        'selected_window': 'business_day_0730',
        'source_table': MES_HOME_SOURCE_TABLE,
        'source_weight_field': MES_HOME_WEIGHT_FIELD,
        'source_time_field': MES_HOME_TIME_FIELD,
        'projection_table': MES_HOME_PROJECTION_TABLE,
        'source_path': MES_HOME_SOURCE_PATH,
        'mes_home_daily_output': 0.0,
        'mes_home_month_to_date_output': 0.0,
        'daily_row_count': 0,
        'month_row_count': 0,
        'business_day': {},
        'natural_day': {},
    }


def build_mes_home_packaging_fact(db: Session, *, target_date: date) -> dict[str, Any]:
    month_start = target_date.replace(day=1)
    try:
        business_start_at, business_end_at = _business_window(target_date)
        natural_start_at, natural_end_at = _natural_window(target_date)
        business_daily = _sum_rows(_header_rows_by_business_date(db, target_date, target_date))
        business_month = _sum_rows(_header_rows_by_business_date(db, month_start, target_date))
        natural_daily = _sum_rows(_header_rows_by_natural_time(db, natural_start_at, natural_end_at))
        natural_month = _sum_rows(
            _header_rows_by_natural_time(
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
        'source_table': MES_HOME_SOURCE_TABLE,
        'source_weight_field': MES_HOME_WEIGHT_FIELD,
        'source_time_field': MES_HOME_TIME_FIELD,
        'projection_table': MES_HOME_PROJECTION_TABLE,
        'source_path': MES_HOME_SOURCE_PATH,
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
        },
        'natural_day': {
            'window_start': natural_start_at.isoformat(),
            'window_end': natural_end_at.isoformat(),
            'daily_output': natural_daily['output'],
            'month_to_date_output': natural_month['output'],
            'daily_row_count': natural_daily['row_count'],
            'month_row_count': natural_month['row_count'],
        },
    }


def build_mes_home_reconciliation(db: Session, *, target_date: date) -> dict[str, Any]:
    fact = build_mes_home_packaging_fact(db, target_date=target_date)
    daily_output = fact['mes_home_daily_output']
    month_output = fact['mes_home_month_to_date_output']
    return {
        **fact,
        'current_dashboard_daily_output': daily_output,
        'current_dashboard_month_to_date_output': month_output,
        'daily_delta': 0.0,
        'month_delta': 0.0,
    }
