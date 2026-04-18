from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd


def parse_date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    dt = pd.to_datetime(value, errors='coerce')
    if pd.isna(dt):
        raise ValueError(f'Invalid date value: {value}')
    return dt.date()


def parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    dt = pd.to_datetime(value, errors='coerce')
    if pd.isna(dt):
        raise ValueError(f'Invalid datetime value: {value}')
    return dt.to_pydatetime()


def combine_date_time(base_date: date, base_time: time) -> datetime:
    return datetime.combine(base_date, base_time)


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def daterange(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        return []
    days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(days + 1)]


def normalize_clock_type(clock_type: str) -> str:
    value = (clock_type or '').strip().lower()
    mapping = {
        '上班': 'in',
        '上班打卡': 'in',
        'in': 'in',
        'checkin': 'in',
        'check_in': 'in',
        'on': 'in',
        '下班': 'out',
        '下班打卡': 'out',
        'out': 'out',
        'checkout': 'out',
        'check_out': 'out',
        'off': 'out',
    }
    return mapping.get(value, value or 'in')
