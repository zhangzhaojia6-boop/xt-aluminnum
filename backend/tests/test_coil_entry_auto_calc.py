from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.mobile_report.summary import _aggregate_coil_to_shift, create_coil_entry


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
        assert entry.entry_status == 'submitted'
        assert float(entry.scrap_weight) == 40.0
        assert float(entry.yield_rate) == round(950 / 1000, 4)
    finally:
        db.close()


def test_coil_entry_records_creator_for_assignment_trace(tmp_path):
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

        result = create_coil_entry(
            db,
            payload={
                'tracking_card_no': 'CREATOR-TRACE-001',
                'business_date': date(2026, 5, 2),
                'shift_id': shift.id,
                'input_weight': 1000,
                'output_weight': 950,
            },
            current_user=mobile_user,
        )

        entry = db.get(WorkOrderEntry, result['id'])
        assert entry.created_by == mobile_user.id
        assert entry.created_by_user_id == mobile_user.id
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
        assert entry.entry_status == 'submitted'
        assert entry.machine_id == equipment.id
        # mobile_coil_agg dual-write retired — no aggregate row expected
        assert db.query(ShiftProductionData).count() == 0
    finally:
        db.close()


def test_coil_entry_uses_reporting_machine_for_virtual_role_binding(tmp_path):
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
        role_qr = Equipment(
            id=101,
            code='LZ2050-1-OP',
            name='2050# 主操',
            workshop_id=workshop.id,
            equipment_type='virtual_role_qr',
            operational_status='running',
            is_active=True,
            bound_user_id=mobile_user.id,
        )
        real_machine = Equipment(
            id=102,
            code='LZ2050-1',
            name='2050轧机',
            workshop_id=workshop.id,
            equipment_type='cold_mill',
            operational_status='running',
            is_active=True,
        )
        db.add_all([workshop, shift, mobile_user, role_qr, real_machine])
        db.commit()

        result = create_coil_entry(
            db,
            payload={
                'tracking_card_no': 'BOUND-MACHINE-OP-001',
                'business_date': date(2026, 5, 2),
                'shift_id': shift.id,
                'input_weight': 1000,
                'output_weight': 960,
                'scrap_weight': 40,
            },
            current_user=mobile_user,
        )

        entry = db.get(WorkOrderEntry, result['id'])
        assert entry.machine_id == real_machine.id
        # mobile_coil_agg dual-write retired
        assert db.query(ShiftProductionData).count() == 0
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

        # mobile_coil_agg dual-write retired — no aggregate rows expected
        assert db.query(ShiftProductionData).count() == 0
    finally:
        db.close()


def test_coil_shift_aggregation_ignores_draft_rows(tmp_path):
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
        work_order = WorkOrder(
            id=1,
            tracking_card_no='DRAFT-COIL-001',
            process_route_code='mobile',
            overall_status='created',
        )
        draft_entry = WorkOrderEntry(
            work_order_id=work_order.id,
            workshop_id=workshop.id,
            shift_id=shift.id,
            business_date=date(2026, 5, 2),
            input_weight=100000,
            output_weight=96000,
            scrap_weight=4000,
            entry_type='mobile_coil',
            entry_status='draft',
        )
        db.add_all([workshop, shift, work_order, draft_entry])
        db.commit()

        _aggregate_coil_to_shift(
            db,
            business_date=date(2026, 5, 2),
            shift_id=shift.id,
            workshop_id=workshop.id,
            machine_id=None,
        )

        assert db.query(ShiftProductionData).filter(ShiftProductionData.data_source == 'mobile_coil_agg').count() == 0
    finally:
        db.close()


def test_coil_shift_aggregation_is_noop_after_retirement(tmp_path):
    """mobile_coil_agg dual-write retired — _aggregate_coil_to_shift is now a no-op."""
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
        db.add_all([workshop, shift])
        db.commit()

        _aggregate_coil_to_shift(
            db,
            business_date=date(2026, 5, 2),
            shift_id=shift.id,
            workshop_id=workshop.id,
            machine_id=None,
        )

        assert db.query(ShiftProductionData).count() == 0
    finally:
        db.close()
