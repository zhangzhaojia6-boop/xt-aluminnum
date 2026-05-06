from __future__ import annotations

from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, Team, Workshop
from app.models.production import MobileShiftReport, ShiftProductionData
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.mobile_report.lifecycle import _sync_to_shift_production


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mobile-shift-report-machine-binding.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            ShiftConfig.__table__,
            User.__table__,
            Equipment.__table__,
            MobileShiftReport.__table__,
            ShiftProductionData.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)()


def _shift() -> ShiftConfig:
    return ShiftConfig(
        id=1,
        code='A',
        name='白班',
        shift_type='day',
        start_time=time(8, 0),
        end_time=time(16, 0),
        is_cross_day=False,
        sort_order=1,
        is_active=True,
    )


def test_mobile_shift_report_sync_uses_bound_machine_for_management_data(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop = Workshop(id=1, code='LZ2050', name='2050冷轧车间', workshop_type='cold_roll')
        team = Team(id=10, workshop_id=workshop.id, code='A', name='甲班', is_active=True)
        shift = _shift()
        mobile_user = User(
            id=7,
            username='machine-operator',
            password_hash='x',
            name='1#主操',
            role='machine_operator',
            workshop_id=workshop.id,
            team_id=team.id,
            data_scope_type='self_team',
            is_mobile_user=True,
            is_active=True,
        )
        equipment = Equipment(
            id=101,
            code='LZ2050-01',
            name='2050 1#轧机',
            workshop_id=workshop.id,
            operational_status='running',
            is_active=True,
            bound_user_id=mobile_user.id,
        )
        report = MobileShiftReport(
            business_date=date(2026, 5, 6),
            shift_config_id=shift.id,
            workshop_id=workshop.id,
            team_id=team.id,
            owner_user_id=mobile_user.id,
            leader_user_id=mobile_user.id,
            leader_name=mobile_user.name,
            attendance_count=4,
            input_weight=1000,
            output_weight=960,
            scrap_weight=20,
            report_status='submitted',
        )
        db.add_all([workshop, team, shift, mobile_user, equipment, report])
        db.commit()

        production = _sync_to_shift_production(db, report=report, shift=shift, workshop=workshop, team=team)

        assert production.equipment_id == equipment.id
        assert report.linked_production_data_id == production.id
    finally:
        db.close()


def test_mobile_shift_report_sync_ignores_bound_machine_from_other_workshop(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        target_workshop = Workshop(id=1, code='LZ2050', name='2050冷轧车间', workshop_type='cold_roll')
        other_workshop = Workshop(id=2, code='TH', name='退火车间', workshop_type='anneal')
        team = Team(id=10, workshop_id=target_workshop.id, code='A', name='甲班', is_active=True)
        shift = _shift()
        mobile_user = User(
            id=7,
            username='machine-operator',
            password_hash='x',
            name='1#主操',
            role='machine_operator',
            workshop_id=target_workshop.id,
            team_id=team.id,
            data_scope_type='self_team',
            is_mobile_user=True,
            is_active=True,
        )
        equipment = Equipment(
            id=101,
            code='TH-01',
            name='退火 1#炉',
            workshop_id=other_workshop.id,
            operational_status='running',
            is_active=True,
            bound_user_id=mobile_user.id,
        )
        report = MobileShiftReport(
            business_date=date(2026, 5, 6),
            shift_config_id=shift.id,
            workshop_id=target_workshop.id,
            team_id=team.id,
            owner_user_id=mobile_user.id,
            leader_user_id=mobile_user.id,
            leader_name=mobile_user.name,
            attendance_count=4,
            input_weight=1000,
            output_weight=960,
            scrap_weight=20,
            report_status='submitted',
        )
        db.add_all([target_workshop, other_workshop, team, shift, mobile_user, equipment, report])
        db.commit()

        production = _sync_to_shift_production(db, report=report, shift=shift, workshop=target_workshop, team=team)

        assert production.equipment_id is None
    finally:
        db.close()


def test_mobile_shift_report_sync_does_not_conflict_with_existing_machine_aggregate(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop = Workshop(id=1, code='LZ2050', name='2050冷轧车间', workshop_type='cold_roll')
        team = Team(id=10, workshop_id=workshop.id, code='A', name='甲班', is_active=True)
        shift = _shift()
        mobile_user = User(
            id=7,
            username='machine-operator',
            password_hash='x',
            name='1#主操',
            role='machine_operator',
            workshop_id=workshop.id,
            team_id=team.id,
            data_scope_type='self_team',
            is_mobile_user=True,
            is_active=True,
        )
        equipment = Equipment(
            id=101,
            code='LZ2050-01',
            name='2050 1#轧机',
            workshop_id=workshop.id,
            operational_status='running',
            is_active=True,
            bound_user_id=mobile_user.id,
        )
        existing_aggregate = ShiftProductionData(
            business_date=date(2026, 5, 6),
            shift_config_id=shift.id,
            workshop_id=workshop.id,
            equipment_id=equipment.id,
            output_weight=960,
            data_source='mobile_coil_agg',
            data_status='pending',
        )
        report = MobileShiftReport(
            business_date=date(2026, 5, 6),
            shift_config_id=shift.id,
            workshop_id=workshop.id,
            team_id=team.id,
            owner_user_id=mobile_user.id,
            leader_user_id=mobile_user.id,
            leader_name=mobile_user.name,
            attendance_count=4,
            input_weight=1000,
            output_weight=960,
            scrap_weight=20,
            report_status='submitted',
        )
        db.add_all([workshop, team, shift, mobile_user, equipment, existing_aggregate, report])
        db.commit()

        production = _sync_to_shift_production(db, report=report, shift=shift, workshop=workshop, team=team)

        assert production.equipment_id is None
        assert existing_aggregate.equipment_id == equipment.id
    finally:
        db.close()
