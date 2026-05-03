from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Workshop
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.mobile_report.summary import create_coil_entry


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'coil-entry-auto-calc.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            ShiftConfig.__table__,
            User.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            ShiftProductionData.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)()


def test_coil_entry_auto_calculates_scrap_weight(tmp_path):
    db = build_session(tmp_path)
    try:
        workshop = Workshop(id=1, code='LZ2050', name='2050冷轧车间', workshop_type='cold_roll')
        shift = ShiftConfig(
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
        mobile_user = User(
            id=7,
            username='mobile-operator',
            password_hash='x',
            name='主操',
            role='machine_operator',
            workshop_id=workshop.id,
            data_scope_type='self_workshop',
            is_mobile_user=True,
            is_active=True,
        )
        db.add_all([workshop, shift, mobile_user])
        db.commit()

        payload = {
            'tracking_card_no': 'TEST-AUTO-001',
            'business_date': date(2026, 5, 2),
            'shift_id': shift.id,
            'input_weight': 1000,
            'output_weight': 950,
            'spool_weight': 10,
        }

        result = create_coil_entry(db, payload=payload, current_user=mobile_user)

        entry = db.get(WorkOrderEntry, result['id'])
        assert float(entry.scrap_weight) == 40.0
        assert float(entry.yield_rate) == round(950 / 1000, 4)
    finally:
        db.close()


def test_coil_entry_keeps_process_flow_trace(tmp_path):
    db = build_session(tmp_path)
    try:
        workshop = Workshop(id=1, code='LZ2050', name='2050冷轧车间', workshop_type='cold_roll')
        shift = ShiftConfig(
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
        mobile_user = User(
            id=7,
            username='mobile-operator',
            password_hash='x',
            name='主操',
            role='machine_operator',
            workshop_id=workshop.id,
            data_scope_type='self_workshop',
            is_mobile_user=True,
            is_active=True,
        )
        db.add_all([workshop, shift, mobile_user])
        db.commit()

        payload = {
            'tracking_card_no': 'FLOW-001',
            'business_date': date(2026, 5, 2),
            'shift_id': shift.id,
            'input_weight': 1000,
            'output_weight': 960,
            'previous_process': '热轧',
            'next_process': '退火',
        }

        result = create_coil_entry(db, payload=payload, current_user=mobile_user)

        entry = db.get(WorkOrderEntry, result['id'])
        assert entry.extra_payload == {
            'previous_process': '热轧',
            'next_process': '退火',
        }
        assert result['previous_process'] == '热轧'
        assert result['next_process'] == '退火'
    finally:
        db.close()
