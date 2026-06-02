from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Workshop
from app.models.production import WorkOrder, WorkOrderEntry
from app.services.report import daily_overview_builder


def test_cold_roll_process_stages_split_output_and_pass_count(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'cold-roll-output-scope.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, WorkOrder.__table__, WorkOrderEntry.__table__])
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    target = date(2026, 6, 1)
    db.add_all([
        Workshop(id=1, code='LZ2050', name='2050冷轧', workshop_type='cold_roll', is_active=True),
        Workshop(id=2, code='RZ', name='热轧', workshop_type='hot_roll', is_active=True),
        WorkOrder(id=1, tracking_card_no='CR-BILLET', process_route_code='CR'),
        WorkOrder(id=2, tracking_card_no='CR-MID', process_route_code='CR'),
        WorkOrder(id=3, tracking_card_no='CR-FIN', process_route_code='CR'),
        WorkOrder(id=4, tracking_card_no='HR-OUT', process_route_code='HR'),
        WorkOrderEntry(
            id=1,
            work_order_id=1,
            workshop_id=1,
            business_date=target,
            entry_type='mobile_coil',
            entry_status='submitted',
            input_weight=10000,
            output_weight=9000,
            extra_payload={'process_stage': 'billet', 'pass_count': 2},
        ),
        WorkOrderEntry(
            id=2,
            work_order_id=2,
            workshop_id=1,
            business_date=target,
            entry_type='mobile_coil',
            entry_status='submitted',
            input_weight=8000,
            output_weight=7800,
            extra_payload={'process_stage': 'intermediate_anneal', 'pass_count': 1},
        ),
        WorkOrderEntry(
            id=3,
            work_order_id=3,
            workshop_id=1,
            business_date=target,
            entry_type='mobile_coil',
            entry_status='submitted',
            input_weight=7000,
            output_weight=6800,
            extra_payload={'process_stage': 'finished', 'pass_count': 1},
        ),
        WorkOrderEntry(
            id=4,
            work_order_id=3,
            workshop_id=1,
            business_date=target,
            entry_type='mobile_coil',
            entry_status='submitted',
            input_weight=6900,
            output_weight=6500,
            extra_payload={'process_stage': 'finished', 'pass_count': 1},
        ),
        WorkOrderEntry(
            id=5,
            work_order_id=4,
            workshop_id=2,
            business_date=target,
            entry_type='mobile_coil',
            entry_status='submitted',
            input_weight=12000,
            output_weight=11500,
            extra_payload={'pass_count': 1},
        ),
    ])
    db.commit()

    rows = daily_overview_builder._build_workshop_output(db, target, {1: '2050冷轧', 2: '热轧'})
    cold_roll = next(item for item in rows if item['workshop'] == '2050冷轧')
    hot_roll = next(item for item in rows if item['workshop'] == '热轧')

    assert cold_roll['daily_output'] == 6.5
    assert cold_roll['process_output'] == 23.3
    assert cold_roll['pass_count_total'] == 4
    assert cold_roll['process_stage_outputs']['billet'] == 9.0
    assert cold_roll['process_stage_outputs']['intermediate_anneal'] == 7.8
    assert hot_roll['daily_output'] == 11.5
