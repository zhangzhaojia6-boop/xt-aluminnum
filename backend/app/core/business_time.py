from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings


PRODUCTION_BUSINESS_DAY_START = time(7, 50)
BILLET_PRODUCTION_BUSINESS_DAY_START = time(10, 0)
OWNER_DAILY_BUSINESS_DAY_START = time(9, 30)
OWNER_DAILY_CUTOFF = OWNER_DAILY_BUSINESS_DAY_START
OWNER_DAILY_LATE_CUTOFF = time(10, 0)
OWNER_DAILY_BACKFILL_LOOKBACK_DAYS = 7
BILLET_BUSINESS_TIME_WORKSHOPS = {'铸二', '铸三', '热轧'}


def _business_time_scope(value: str | None) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    return text.replace('车间', '').replace(' ', '')


def is_billet_business_time_scope(workshop_name: str | None) -> bool:
    text = _business_time_scope(workshop_name)
    return any(token and token in text for token in BILLET_BUSINESS_TIME_WORKSHOPS)


def production_business_day_start(workshop_name: str | None = None) -> time:
    if is_billet_business_time_scope(workshop_name):
        return BILLET_PRODUCTION_BUSINESS_DAY_START
    return PRODUCTION_BUSINESS_DAY_START


def production_business_day_start_label(workshop_name: str | None = None) -> str:
    start = production_business_day_start(workshop_name)
    return f'{start.hour:02d}:{start.minute:02d}'


def local_now(now: datetime | None = None) -> datetime:
    timezone = ZoneInfo(settings.DEFAULT_TIMEZONE)
    if now is None:
        return datetime.now(timezone)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone)
    return now.astimezone(timezone)


def resolve_production_business_date(now: datetime | None = None, workshop_name: str | None = None) -> date:
    current_local = local_now(now)
    if current_local.time() < production_business_day_start(workshop_name):
        return current_local.date() - timedelta(days=1)
    return current_local.date()


def resolve_yearless_business_date(*, month: int, day: int, reference_date: date) -> date:
    candidates: list[date] = []
    for year in (reference_date.year, reference_date.year - 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        return date(reference_date.year, month, day)
    return min(candidates, key=lambda candidate: abs((candidate - reference_date).days))


def production_business_window(business_date: date, workshop_name: str | None = None) -> tuple[datetime, datetime]:
    timezone = ZoneInfo(settings.DEFAULT_TIMEZONE)
    start_at = datetime.combine(business_date, production_business_day_start(workshop_name), tzinfo=timezone)
    end_at = start_at + timedelta(days=1)
    return start_at, end_at


def last_completed_production_business_date(now: datetime | None = None) -> date:
    return resolve_production_business_date(now) - timedelta(days=1)


def resolve_owner_daily_business_date(now: datetime | None = None) -> date:
    current_local = local_now(now)
    if current_local.time() < OWNER_DAILY_BUSINESS_DAY_START:
        return current_local.date() - timedelta(days=1)
    return current_local.date()
