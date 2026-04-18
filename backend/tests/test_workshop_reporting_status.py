from __future__ import annotations

from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.attendance import AttendanceSchedule
from app.models.master import Employee, Team, Workshop
from app.models.production import MobileShiftReport
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.report_service import _build_workshop_reporting_status


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workshop-reporting-status.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            Employee.__table__,
            ShiftConfig.__table__,
            AttendanceSchedule.__table__,
            User.__table__,
            MobileShiftReport.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)()


def test_build_workshop_reporting_status_marks_workshop_unreported_when_expected_shift_missing(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop = Workshop(id=1, code='ZR2', name='铸二车间', workshop_type='casting', sort_order=1, is_active=True)
        team_a = Team(id=11, workshop_id=1, code='A', name='白班组', sort_order=1, is_active=True)
        team_b = Team(id=12, workshop_id=1, code='B', name='小夜班组', sort_order=2, is_active=True)
        shift = ShiftConfig(id=1, code='A', name='白班', shift_type='day', start_time=time(8, 0), end_time=time(16, 0), is_cross_day=False, sort_order=1, is_active=True)
        employee_a = Employee(id=101, employee_no='E101', name='甲', workshop_id=1, team_id=11, is_active=True)
        employee_b = Employee(id=102, employee_no='E102', name='乙', workshop_id=1, team_id=12, is_active=True)
        user = User(id=7, username='leader', password_hash='x', name='班长', role='team_leader', is_active=True)
        report = MobileShiftReport(
            id=1,
            business_date=date(2026, 4, 17),
            shift_config_id=1,
            workshop_id=1,
            team_id=11,
            owner_user_id=user.id,
            leader_user_id=user.id,
            leader_name=user.name,
            report_status='auto_confirmed',
            output_weight=120.0,
        )
        db.add_all([workshop, team_a, team_b, shift, employee_a, employee_b, user, report])
        db.flush()
        db.add_all(
            [
                AttendanceSchedule(employee_id=101, business_date=date(2026, 4, 17), shift_config_id=1, team_id=11, workshop_id=1, source='import', is_rest_day=False),
                AttendanceSchedule(employee_id=102, business_date=date(2026, 4, 17), shift_config_id=1, team_id=12, workshop_id=1, source='import', is_rest_day=False),
            ]
        )
        db.commit()

        items = _build_workshop_reporting_status(db, date(2026, 4, 17))

        assert items[0]['workshop_code'] == 'ZR2'
        assert items[0]['report_status'] == 'unreported'
    finally:
        db.close()
