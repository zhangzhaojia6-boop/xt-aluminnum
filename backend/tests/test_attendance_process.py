from datetime import date, datetime, time, timezone

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.attendance import AttendanceSchedule, ClockRecord
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.attendance_service import ProcessSummary, _match_schedule_for_clock


class DummyDB:
    pass


def test_attendance_process_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_process_attendance(db, *, start_date, end_date, operator):
        assert start_date == date(2026, 3, 25)
        assert end_date == date(2026, 3, 25)
        assert operator.id == 1
        return ProcessSummary(
            processed_dates=[date(2026, 3, 25)],
            processed_results=3,
            generated_exceptions=2,
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.attendance.attendance_service.process_attendance', fake_process_attendance)

    client = TestClient(app)
    response = client.post('/api/v1/attendance/process', json={'start_date': '2026-03-25', 'end_date': '2026-03-25'})

    assert response.status_code == 200
    assert response.json()['processed_results'] == 3
    assert response.json()['generated_exceptions'] == 2

    app.dependency_overrides.clear()


def test_match_schedule_for_aware_clock_datetime() -> None:
    shift = ShiftConfig(
        id=1,
        code='A',
        name='Day',
        shift_type='day',
        start_time=time(8, 0),
        end_time=time(16, 0),
        is_cross_day=False,
        business_day_offset=0,
        late_tolerance_minutes=30,
        early_tolerance_minutes=30,
        sort_order=1,
        is_active=True,
    )
    schedule = AttendanceSchedule(
        employee_id=1,
        business_date=date(2026, 3, 25),
        shift_config_id=1,
        source='import',
        is_rest_day=False,
    )
    clock = ClockRecord(
        employee_id=1,
        employee_no='E1',
        dingtalk_user_id='dt_e1',
        clock_datetime=datetime(2026, 3, 25, 8, 10, tzinfo=timezone.utc),
        clock_type='in',
        dingtalk_record_id='r1',
        device_id='D1',
        location_name='Gate',
        source='import',
    )

    matched = _match_schedule_for_clock(
        clock=clock,
        employee_id=1,
        schedule_map={(1, date(2026, 3, 25)): schedule},
        shift_map={1: shift},
    )

    assert matched is not None
