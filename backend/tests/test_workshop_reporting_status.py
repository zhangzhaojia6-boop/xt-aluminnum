from __future__ import annotations

from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.attendance import AttendanceSchedule
from app.models.master import Employee, Equipment, Team, Workshop
from app.models.production import MobileShiftReport, ShiftProductionData, WorkOrder, WorkOrderEntry
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
            Equipment.__table__,
            MobileShiftReport.__table__,
            ShiftProductionData.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
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


def test_build_workshop_reporting_status_surfaces_live_mobile_coil_entries(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop = Workshop(id=1, code='LZ', name='冷轧车间', workshop_type='rolling', sort_order=1, is_active=True)
        shift = ShiftConfig(id=1, code='A', name='白班', shift_type='day', start_time=time(8, 0), end_time=time(16, 0), is_cross_day=False, sort_order=1, is_active=True)
        equipment = Equipment(id=101, code='CRM-01', name='1#轧机', workshop_id=1, is_active=True)
        work_order = WorkOrder(id=201, tracking_card_no='TC-001', process_route_code='ROLLING')
        db.add_all([workshop, shift, equipment, work_order])
        db.flush()
        db.add(
            WorkOrderEntry(
                id=1,
                work_order_id=201,
                workshop_id=1,
                machine_id=101,
                shift_id=1,
                business_date=date(2026, 5, 6),
                output_weight=42_500.0,
                entry_type='mobile_coil',
                entry_status='submitted',
            )
        )
        db.commit()

        items = _build_workshop_reporting_status(db, date(2026, 5, 6))

        assert items == [
            {
                'workshop_id': 1,
                'workshop_name': '冷轧车间',
                'workshop_code': 'LZ',
                'report_status': 'submitted',
                'output_weight': 42.5,
                'source_label': '主操直录',
                'source_variant': 'mobile',
                'status_hint': '现场扫码数据已进入管理端',
            }
        ]
    finally:
        db.close()


def test_build_workshop_reporting_status_does_not_mark_idle_workshops_unreported_when_mobile_coil_active(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop_a = Workshop(id=1, code='LZ', name='冷轧车间', workshop_type='rolling', sort_order=1, is_active=True)
        workshop_b = Workshop(id=2, code='JZ', name='精整车间', workshop_type='finishing', sort_order=2, is_active=True)
        shift = ShiftConfig(id=1, code='A', name='白班', shift_type='day', start_time=time(8, 0), end_time=time(16, 0), is_cross_day=False, sort_order=1, is_active=True)
        work_order = WorkOrder(id=201, tracking_card_no='TC-001', process_route_code='ROLLING')
        db.add_all([workshop_a, workshop_b, shift, work_order])
        db.flush()
        db.add(
            WorkOrderEntry(
                id=1,
                work_order_id=201,
                workshop_id=1,
                shift_id=1,
                business_date=date(2026, 5, 6),
                output_weight=42_500.0,
                entry_type='mobile_coil',
                entry_status='submitted',
            )
        )
        db.commit()

        items = _build_workshop_reporting_status(db, date(2026, 5, 6))

        assert items[0]['report_status'] == 'submitted'
        assert items[1]['report_status'] == 'not_applicable'
        assert items[1]['status_hint'] == '本日暂无扫码成品产出'
    finally:
        db.close()
