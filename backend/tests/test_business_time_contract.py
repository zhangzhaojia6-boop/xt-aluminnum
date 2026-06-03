from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.business_time import (
    production_business_window,
    resolve_owner_daily_business_date,
    resolve_production_business_date,
)


SHANGHAI = ZoneInfo('Asia/Shanghai')


def test_production_roles_business_date_switches_at_0730() -> None:
    assert resolve_production_business_date(datetime(2026, 6, 3, 7, 29, tzinfo=SHANGHAI)) == date(2026, 6, 2)
    assert resolve_production_business_date(datetime(2026, 6, 3, 7, 30, tzinfo=SHANGHAI)) == date(2026, 6, 3)


def test_owner_daily_roles_business_date_switches_at_1000() -> None:
    assert resolve_owner_daily_business_date(datetime(2026, 6, 3, 9, 59, tzinfo=SHANGHAI)) == date(2026, 6, 2)
    assert resolve_owner_daily_business_date(datetime(2026, 6, 3, 10, 0, tzinfo=SHANGHAI)) == date(2026, 6, 3)


def test_production_business_window_is_24_hours_from_start_anchor() -> None:
    start_at, end_at = production_business_window(date(2026, 6, 3))

    assert start_at == datetime(2026, 6, 3, 7, 30, tzinfo=SHANGHAI)
    assert end_at == datetime(2026, 6, 4, 7, 30, tzinfo=SHANGHAI)
