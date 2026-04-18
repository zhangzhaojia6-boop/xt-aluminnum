from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.models.shift import ShiftConfig
from app.utils.date_utils import combine_date_time


@dataclass(slots=True)
class ShiftMatch:
    shift_config_id: int | None
    business_date: date
    auto_shift_config_id: int | None
    confidence: float


def _normalize_dt(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def build_shift_window(
    shift: ShiftConfig,
    business_date: date,
    buffer_before_minutes: int = 120,
    buffer_after_minutes: int = 240,
) -> tuple[datetime, datetime]:
    shift_anchor_date = business_date - timedelta(days=shift.business_day_offset)
    start_dt = combine_date_time(shift_anchor_date, shift.start_time)
    end_dt = combine_date_time(shift_anchor_date, shift.end_time)

    if shift.is_cross_day or end_dt <= start_dt:
        end_dt += timedelta(days=1)

    return (
        start_dt - timedelta(minutes=buffer_before_minutes),
        end_dt + timedelta(minutes=buffer_after_minutes),
    )


def _distance_to_shift_start(clock_dt: datetime, shift: ShiftConfig, business_date: date) -> float:
    clock_dt = _normalize_dt(clock_dt)
    shift_anchor_date = business_date - timedelta(days=shift.business_day_offset)
    start_dt = combine_date_time(shift_anchor_date, shift.start_time)
    return abs((clock_dt - start_dt).total_seconds())


def infer_shift(clock_dt: datetime, shifts: list[ShiftConfig]) -> ShiftMatch:
    clock_dt = _normalize_dt(clock_dt)
    if not shifts:
        return ShiftMatch(shift_config_id=None, business_date=clock_dt.date(), auto_shift_config_id=None, confidence=0.0)

    candidate_dates = [clock_dt.date() - timedelta(days=1), clock_dt.date(), clock_dt.date() + timedelta(days=1)]

    best: tuple[ShiftConfig, date, float] | None = None
    for shift in shifts:
        for candidate_date in candidate_dates:
            window_start, window_end = build_shift_window(shift, candidate_date)
            if window_start <= clock_dt <= window_end:
                distance = _distance_to_shift_start(clock_dt, shift, candidate_date)
                if best is None or distance < best[2]:
                    best = (shift, candidate_date, distance)

    if best is None:
        fallback_shift = sorted(shifts, key=lambda item: item.sort_order)[0]
        return ShiftMatch(
            shift_config_id=fallback_shift.id,
            business_date=clock_dt.date(),
            auto_shift_config_id=fallback_shift.id,
            confidence=0.1,
        )

    shift, business_date, distance = best
    # 8-hour decay function for rough confidence score.
    confidence = max(0.2, min(1.0, 1 - (distance / (8 * 3600))))
    return ShiftMatch(
        shift_config_id=shift.id,
        business_date=business_date,
        auto_shift_config_id=shift.id,
        confidence=confidence,
    )


def assign_shift(
    clock_dt: datetime,
    shifts: list[ShiftConfig],
    scheduled_shift: ShiftConfig | None = None,
    scheduled_business_date: date | None = None,
) -> ShiftMatch:
    clock_dt = _normalize_dt(clock_dt)
    if scheduled_shift is not None and scheduled_business_date is not None:
        return ShiftMatch(
            shift_config_id=scheduled_shift.id,
            business_date=scheduled_business_date,
            auto_shift_config_id=scheduled_shift.id,
            confidence=1.0,
        )
    return infer_shift(clock_dt, shifts)


def calculate_late_minutes(check_in_time: datetime | None, shift: ShiftConfig, business_date: date) -> int:
    if check_in_time is None:
        return 0
    check_in_time = _normalize_dt(check_in_time)
    shift_anchor_date = business_date - timedelta(days=shift.business_day_offset)
    shift_start = combine_date_time(shift_anchor_date, shift.start_time)
    delta_minutes = int((check_in_time - shift_start).total_seconds() // 60)
    return max(0, delta_minutes)


def calculate_early_leave_minutes(check_out_time: datetime | None, shift: ShiftConfig, business_date: date) -> int:
    if check_out_time is None:
        return 0
    check_out_time = _normalize_dt(check_out_time)
    shift_anchor_date = business_date - timedelta(days=shift.business_day_offset)
    shift_end = combine_date_time(shift_anchor_date, shift.end_time)
    if shift.is_cross_day or shift_end <= combine_date_time(shift_anchor_date, shift.start_time):
        shift_end += timedelta(days=1)
    delta_minutes = int((shift_end - check_out_time).total_seconds() // 60)
    return max(0, delta_minutes)
