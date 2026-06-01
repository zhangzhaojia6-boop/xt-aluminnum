from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings


PRODUCTION_BUSINESS_DAY_START = time(23, 30)
OWNER_DAILY_CUTOFF = time(9, 0)


def local_now(now: datetime | None = None) -> datetime:
    timezone = ZoneInfo(settings.DEFAULT_TIMEZONE)
    if now is None:
        return datetime.now(timezone)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone)
    return now.astimezone(timezone)


def resolve_production_business_date(now: datetime | None = None) -> date:
    current_local = local_now(now)
    if current_local.time() >= PRODUCTION_BUSINESS_DAY_START:
        return current_local.date() + timedelta(days=1)
    return current_local.date()


def production_business_window(business_date: date) -> tuple[datetime, datetime]:
    timezone = ZoneInfo(settings.DEFAULT_TIMEZONE)
    end_at = datetime.combine(business_date, PRODUCTION_BUSINESS_DAY_START, tzinfo=timezone)
    start_at = end_at - timedelta(days=1)
    return start_at, end_at


def last_completed_production_business_date(now: datetime | None = None) -> date:
    return resolve_production_business_date(now) - timedelta(days=1)


def resolve_owner_daily_business_date(now: datetime | None = None) -> date:
    current_local = local_now(now)
    if current_local.time() < OWNER_DAILY_CUTOFF:
        return current_local.date() - timedelta(days=1)
    return resolve_production_business_date(current_local)
