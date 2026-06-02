from datetime import datetime, time

from app.models.shift import ShiftConfig
from app.services.shift_engine import build_shift_window, infer_shift


def build_shift(
    shift_id: int,
    code: str,
    name: str,
    start_time: time,
    end_time: time,
    is_cross_day: bool,
    offset: int,
    sort_order: int,
) -> ShiftConfig:
    return ShiftConfig(
        id=shift_id,
        code=code,
        name=name,
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


def canonical_shifts() -> list[ShiftConfig]:
    return [
        build_shift(1, 'A', '长白班', time(7, 30), time(15, 30), False, 0, 1),
        build_shift(2, 'B', '小夜班', time(15, 30), time(23, 30), False, 0, 2),
        build_shift(3, 'C', '大夜班', time(23, 30), time(7, 30), True, 0, 3),
    ]


def test_infer_day_shift() -> None:
    shifts = canonical_shifts()

    matched = infer_shift(datetime(2026, 3, 25, 7, 30), shifts)

    assert matched.shift_config_id == 1
    assert matched.business_date.isoformat() == '2026-03-25'


def test_infer_shift_switches_by_canonical_order() -> None:
    shifts = canonical_shifts()

    assert infer_shift(datetime(2026, 3, 25, 15, 29), shifts).shift_config_id == 1
    assert infer_shift(datetime(2026, 3, 25, 15, 30), shifts).shift_config_id == 2
    assert infer_shift(datetime(2026, 3, 25, 23, 30), shifts).shift_config_id == 3


def test_infer_cross_day_business_date() -> None:
    shifts = canonical_shifts()

    matched = infer_shift(datetime(2026, 3, 26, 1, 15), shifts)

    assert matched.shift_config_id == 3
    assert matched.business_date.isoformat() == '2026-03-25'


def test_build_shift_window_cross_day() -> None:
    night = canonical_shifts()[2]
    start, end = build_shift_window(night, datetime(2026, 3, 25, 0, 0).date(), 0, 0)

    assert start.isoformat() == '2026-03-25T23:30:00'
    assert end.isoformat() == '2026-03-26T07:30:00'
