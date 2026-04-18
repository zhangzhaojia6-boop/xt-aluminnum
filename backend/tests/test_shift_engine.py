from datetime import datetime, time

from app.models.shift import ShiftConfig
from app.services.shift_engine import build_shift_window, infer_shift


def build_shift(shift_id: int, code: str, start_time: time, end_time: time, is_cross_day: bool, offset: int, sort_order: int) -> ShiftConfig:
    return ShiftConfig(
        id=shift_id,
        code=code,
        name=code,
        shift_type='test',
        start_time=start_time,
        end_time=end_time,
        is_cross_day=is_cross_day,
        business_day_offset=offset,
        late_tolerance_minutes=30,
        early_tolerance_minutes=30,
        sort_order=sort_order,
        is_active=True,
    )


def test_infer_day_shift() -> None:
    day = build_shift(1, 'A', time(8, 0), time(16, 0), False, 0, 1)
    night = build_shift(2, 'B', time(16, 0), time(0, 0), True, 0, 2)

    matched = infer_shift(datetime(2026, 3, 25, 8, 32), [day, night])

    assert matched.shift_config_id == 1
    assert matched.business_date.isoformat() == '2026-03-25'


def test_infer_cross_day_business_date() -> None:
    day = build_shift(1, 'A', time(8, 0), time(16, 0), False, 0, 1)
    middle = build_shift(2, 'B', time(16, 0), time(0, 0), True, 0, 2)
    night = build_shift(3, 'C', time(0, 0), time(8, 0), False, -1, 3)

    matched = infer_shift(datetime(2026, 3, 26, 1, 15), [day, middle, night])

    assert matched.shift_config_id == 3
    assert matched.business_date.isoformat() == '2026-03-25'


def test_build_shift_window_cross_day() -> None:
    middle = build_shift(2, 'B', time(16, 0), time(0, 0), True, 0, 2)
    start, end = build_shift_window(middle, datetime(2026, 3, 25, 0, 0).date(), 0, 0)

    assert start.isoformat() == '2026-03-25T16:00:00'
    assert end.isoformat() == '2026-03-26T00:00:00'
