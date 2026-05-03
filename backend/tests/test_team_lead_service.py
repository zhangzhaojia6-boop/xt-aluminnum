from __future__ import annotations

from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.attendance import AttendanceResult, AttendanceSchedule
from app.models.master import Employee, Team, Workshop
from app.models.production import MobileReminderRecord, MobileShiftReport
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import team_lead_service


TABLES = [
    Workshop.__table__,
    Team.__table__,
    User.__table__,
    Employee.__table__,
    ShiftConfig.__table__,
    AttendanceSchedule.__table__,
    AttendanceResult.__table__,
    MobileShiftReport.__table__,
    MobileReminderRecord.__table__,
]


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'team-lead.db'}", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    SessionLocal = sessionmaker(bind=engine, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_team_lead_data(db):
    target_date = date(2026, 5, 3)
    db.add_all(
        [
            Workshop(id=1, code='LZ01', name='冷轧一车间'),
            Team(id=10, workshop_id=1, code='A', name='甲班'),
            Team(id=11, workshop_id=1, code='B', name='乙班'),
            ShiftConfig(id=1, code='day', name='白班', shift_type='day', start_time=time(8), end_time=time(20)),
            User(id=7, username='leader', password_hash='x', name='班长', role='team_leader', workshop_id=1, team_id=10, is_active=True),
            Employee(id=101, employee_no='E101', name='张三', workshop_id=1, team_id=10),
            Employee(id=102, employee_no='E102', name='李四', workshop_id=1, team_id=10),
            Employee(id=103, employee_no='E103', name='王五', workshop_id=1, team_id=11),
        ]
    )
    db.add_all(
        [
            AttendanceSchedule(employee_id=101, business_date=target_date, shift_config_id=1, workshop_id=1, team_id=10, is_rest_day=False),
            AttendanceSchedule(employee_id=102, business_date=target_date, shift_config_id=1, workshop_id=1, team_id=10, is_rest_day=False),
            AttendanceSchedule(employee_id=103, business_date=target_date, shift_config_id=1, workshop_id=1, team_id=11, is_rest_day=False),
            AttendanceResult(employee_id=101, employee_no='E101', employee_name='张三', business_date=target_date, workshop_id=1, team_id=10, shift_config_id=1, attendance_status='normal'),
            MobileShiftReport(id=201, business_date=target_date, shift_config_id=1, workshop_id=1, team_id=10, leader_user_id=7, leader_name='班长', attendance_count=1, report_status='returned', returned_reason='产出需核对'),
            MobileReminderRecord(id=301, business_date=target_date, shift_config_id=1, workshop_id=1, team_id=10, leader_user_id=7, reminder_type='unreported', reminder_status='sent', reminder_count=2),
        ]
    )
    db.commit()
    return target_date, db.get(User, 7)


def test_build_overview_counts_five_quadrants_and_lists(tmp_path) -> None:
    db = next(build_session(tmp_path))
    target_date, leader = seed_team_lead_data(db)

    payload = team_lead_service.build_overview(db, leader_user=leader, target_date=target_date)

    assert payload['scheduled_count'] == 2
    assert payload['attended_count'] == 1
    assert payload['reported_count'] == 1
    assert payload['returned_count'] == 1
    assert payload['reminder_count'] == 2
    assert payload['escalation_count'] == 0
    assert payload['shift_health'] == 'red'
    assert payload['returned_list'][0]['returned_reason'] == '产出需核对'
    assert payload['pending_list'][0]['business_date'] == '2026-05-03'
    assert payload['pending_list'][0]['shift_id'] == 1
    assert payload['pending_list'][0]['members'] == [
        {
            'employee_id': 102,
            'name': '李四',
            'route': '/team-lead/worker/102/2026-05-03?shift_id=1',
        }
    ]
    assert payload['reminder_list'][0]['count'] == 2


def test_build_overview_flags_unreported_shift_even_when_attendance_complete(tmp_path) -> None:
    db = next(build_session(tmp_path))
    target_date, leader = seed_team_lead_data(db)
    db.query(MobileShiftReport).delete()
    db.add(
        AttendanceResult(
            employee_id=102,
            employee_no='E102',
            employee_name='李四',
            business_date=target_date,
            workshop_id=1,
            team_id=10,
            shift_config_id=1,
            attendance_status='normal',
        )
    )
    db.commit()

    payload = team_lead_service.build_overview(db, leader_user=leader, target_date=target_date)

    assert payload['attended_count'] == 2
    assert payload['reported_count'] == 0
    assert payload['shift_health'] == 'yellow'
    assert payload['pending_list'][0]['shift_id'] == 1
    assert payload['pending_list'][0]['team'] == '甲班'
    assert payload['pending_list'][0]['members'] == [
        {
            'employee_id': 101,
            'name': '张三',
            'route': '/team-lead/worker/101/2026-05-03?shift_id=1',
        },
        {
            'employee_id': 102,
            'name': '李四',
            'route': '/team-lead/worker/102/2026-05-03?shift_id=1',
        },
    ]
