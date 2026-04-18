from __future__ import annotations

from datetime import date, time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.attendance import AttendanceSchedule
from app.models.master import Employee, Team, Workshop
from app.models.shift import ShiftConfig
from app.services.pilot_schedule_seed import seed_default_pilot_schedule


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pilot-schedule.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            Employee.__table__,
            ShiftConfig.__table__,
            AttendanceSchedule.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)()


def test_seed_default_pilot_schedule_creates_phase1_owner_grid_for_each_shift_team(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshops = [
            Workshop(code='ZR2', name='铸二车间', sort_order=1, is_active=True),
            Workshop(code='CPK', name='成品库', sort_order=2, is_active=True),
        ]
        db.add_all(workshops)
        db.flush()

        teams = [
            Team(code='ZR2-A', name='白班组', workshop_id=workshops[0].id, sort_order=1, is_active=True),
            Team(code='ZR2-B', name='小夜班组', workshop_id=workshops[0].id, sort_order=2, is_active=True),
            Team(code='ZR2-C', name='大夜班组', workshop_id=workshops[0].id, sort_order=3, is_active=True),
            Team(code='CPK-A', name='白班组', workshop_id=workshops[1].id, sort_order=1, is_active=True),
            Team(code='CPK-B', name='小夜班组', workshop_id=workshops[1].id, sort_order=2, is_active=True),
            Team(code='CPK-C', name='大夜班组', workshop_id=workshops[1].id, sort_order=3, is_active=True),
        ]
        db.add_all(teams)

        shifts = [
            ShiftConfig(
                code='A',
                name='白班',
                shift_type='day',
                start_time=time(8, 0),
                end_time=time(16, 0),
                is_cross_day=False,
                sort_order=1,
                is_active=True,
            ),
            ShiftConfig(
                code='B',
                name='小夜',
                shift_type='swing',
                start_time=time(16, 0),
                end_time=time(0, 0),
                is_cross_day=True,
                business_day_offset=0,
                sort_order=2,
                is_active=True,
            ),
            ShiftConfig(
                code='C',
                name='大夜',
                shift_type='night',
                start_time=time(0, 0),
                end_time=time(8, 0),
                is_cross_day=False,
                business_day_offset=0,
                sort_order=3,
                is_active=True,
            ),
        ]
        db.add_all(shifts)
        db.commit()

        created = seed_default_pilot_schedule(db, target_date=date(2026, 4, 17))

        employees = db.execute(select(Employee).order_by(Employee.employee_no.asc())).scalars().all()
        employee_nos = [item.employee_no for item in employees]
        assert created == len(employees) * 2
        assert 'PILOT-ZR2-A' not in employee_nos
        assert 'PILOT-ZR2-A-OP' in employee_nos
        assert 'PILOT-ZR2-B-EN' in employee_nos
        assert 'PILOT-ZR2-C-QC' in employee_nos
        assert 'PILOT-CPK-A-INV' in employee_nos
        assert 'PILOT-CPK-B-PLAN' in employee_nos
        assert 'PILOT-CPK-C-UTILITY' in employee_nos

        schedules = db.execute(
            select(AttendanceSchedule).where(AttendanceSchedule.business_date == date(2026, 4, 17))
        ).scalars().all()
        shift_by_employee = {
            db.get(Employee, row.employee_id).employee_no: db.get(ShiftConfig, row.shift_config_id).code
            for row in schedules
        }
        assert shift_by_employee['PILOT-ZR2-A-OP'] == 'A'
        assert shift_by_employee['PILOT-ZR2-B-EN'] == 'B'
        assert shift_by_employee['PILOT-ZR2-C-QC'] == 'C'
        assert shift_by_employee['PILOT-CPK-A-INV'] == 'A'
        assert shift_by_employee['PILOT-CPK-B-PLAN'] == 'B'
        assert shift_by_employee['PILOT-CPK-C-UTILITY'] == 'C'
    finally:
        db.close()
