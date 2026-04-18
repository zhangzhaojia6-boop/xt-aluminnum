from datetime import date, datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services.mobile_reminder_service import build_reminder_candidates


LOCAL_TZ = ZoneInfo('Asia/Shanghai')


def _schedule(**overrides):
    payload = {
        'business_date': date(2026, 3, 27),
        'shift_config_id': 1,
        'workshop_id': 1,
        'team_id': 10,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _shift(**overrides):
    payload = {
        'id': 1,
        'code': 'A',
        'name': '白班',
        'start_time': time(7, 0),
        'end_time': time(15, 0),
        'is_cross_day': False,
        'business_day_offset': 0,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_missing_shift_generates_unreported_reminder() -> None:
    candidates = build_reminder_candidates(
        expected_rows=[_schedule()],
        report_rows=[],
        shift_map={1: _shift()},
        leader_map={(1, 10): 88},
        now=datetime(2026, 3, 27, 12, 0, tzinfo=LOCAL_TZ),
        grace_minutes=30,
    )

    assert len(candidates) == 1
    assert candidates[0]['reminder_type'] == 'unreported'
    assert candidates[0]['leader_user_id'] == 88


def test_overdue_missing_shift_generates_late_report_reminder() -> None:
    candidates = build_reminder_candidates(
        expected_rows=[_schedule()],
        report_rows=[],
        shift_map={1: _shift()},
        leader_map={(1, 10): 88},
        now=datetime(2026, 3, 27, 17, 0, tzinfo=LOCAL_TZ),
        grace_minutes=30,
    )

    assert len(candidates) == 1
    assert candidates[0]['reminder_type'] == 'late_report'
    assert candidates[0]['leader_user_id'] == 88


def test_auto_confirmed_shift_does_not_generate_reminder() -> None:
    candidates = build_reminder_candidates(
        expected_rows=[_schedule()],
        report_rows=[_schedule(report_status='auto_confirmed')],
        shift_map={1: _shift()},
        leader_map={(1, 10): 88},
        now=datetime(2026, 3, 27, 17, 0, tzinfo=LOCAL_TZ),
        grace_minutes=30,
    )

    assert candidates == []
