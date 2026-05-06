from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot
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
            Equipment.__table__,
            MesCoilSnapshot.__table__,
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


def test_coil_entry_uses_bound_machine_for_management_aggregation(tmp_path):
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
        equipment = Equipment(
            id=101,
            code='LZ2050-01',
            name='2050 1#轧机',
            workshop_id=workshop.id,
            operational_status='running',
            is_active=True,
            bound_user_id=mobile_user.id,
        )
        db.add_all([workshop, shift, mobile_user, equipment])
        db.commit()

        payload = {
            'tracking_card_no': 'BOUND-MACHINE-001',
            'business_date': date(2026, 5, 2),
            'shift_id': shift.id,
            'input_weight': 1000,
            'output_weight': 960,
            'scrap_weight': 40,
        }

        result = create_coil_entry(db, payload=payload, current_user=mobile_user)

        entry = db.get(WorkOrderEntry, result['id'])
        aggregate = db.query(ShiftProductionData).filter(ShiftProductionData.data_source == 'mobile_coil_agg').one()
        assert entry.machine_id == equipment.id
        assert aggregate.equipment_id == equipment.id
        assert float(aggregate.input_weight) == 1000.0
        assert float(aggregate.output_weight) == 960.0
        assert float(aggregate.scrap_weight) == 40.0
    finally:
        db.close()


def test_coil_entry_aggregates_by_bound_machine_not_only_workshop_shift(tmp_path):
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
        first_user = User(
            id=7,
            username='operator-1',
            password_hash='x',
            name='1#主操',
            role='machine_operator',
            workshop_id=workshop.id,
            data_scope_type='self_workshop',
            is_mobile_user=True,
            is_active=True,
        )
        second_user = User(
            id=8,
            username='operator-2',
            password_hash='x',
            name='2#主操',
            role='machine_operator',
            workshop_id=workshop.id,
            data_scope_type='self_workshop',
            is_mobile_user=True,
            is_active=True,
        )
        first_machine = Equipment(
            id=101,
            code='LZ2050-01',
            name='2050 1#轧机',
            workshop_id=workshop.id,
            operational_status='running',
            is_active=True,
            bound_user_id=first_user.id,
        )
        second_machine = Equipment(
            id=102,
            code='LZ2050-02',
            name='2050 2#轧机',
            workshop_id=workshop.id,
            operational_status='running',
            is_active=True,
            bound_user_id=second_user.id,
        )
        db.add_all([workshop, shift, first_user, second_user, first_machine, second_machine])
        db.commit()

        create_coil_entry(
            db,
            payload={
                'tracking_card_no': 'BOUND-MACHINE-101',
                'business_date': date(2026, 5, 2),
                'shift_id': shift.id,
                'input_weight': 1000,
                'output_weight': 960,
                'scrap_weight': 40,
            },
            current_user=first_user,
        )
        create_coil_entry(
            db,
            payload={
                'tracking_card_no': 'BOUND-MACHINE-102',
                'business_date': date(2026, 5, 2),
                'shift_id': shift.id,
                'input_weight': 2000,
                'output_weight': 1900,
                'scrap_weight': 100,
            },
            current_user=second_user,
        )

        aggregates = db.query(ShiftProductionData).order_by(ShiftProductionData.equipment_id.asc()).all()
        assert len(aggregates) == 2
        assert [row.equipment_id for row in aggregates] == [first_machine.id, second_machine.id]
        assert [float(row.output_weight) for row in aggregates] == [960.0, 1900.0]
    finally:
        db.close()
