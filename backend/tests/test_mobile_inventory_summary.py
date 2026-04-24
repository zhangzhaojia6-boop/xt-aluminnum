from __future__ import annotations

from datetime import date, time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Team, Workshop
from app.models.production import MobileShiftReport, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.mobile_report_service import summarize_mobile_inventory


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mobile-inventory-summary.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            ShiftConfig.__table__,
            User.__table__,
            MobileShiftReport.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)()


def test_summarize_mobile_inventory_includes_owner_only_work_order_entries(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop = Workshop(id=11, code='CPK', name='成品库', workshop_type='inventory', sort_order=1, is_active=True)
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
        user = User(id=7, username='owner', password_hash='x', name='成品库负责人', role='inventory_keeper', is_active=True)
        work_order = WorkOrder(
            id=21,
            tracking_card_no='OWNER-CPK-20260417-A-INVENTORY_KEEPER',
            process_route_code='OWNER',
            overall_status='submitted',
            created_by=user.id,
        )
        entry = WorkOrderEntry(
            id=31,
            work_order_id=work_order.id,
            workshop_id=workshop.id,
            shift_id=shift.id,
            business_date=date(2026, 4, 17),
            entry_type='completed',
            entry_status='submitted',
            created_by=user.id,
            created_by_user_id=user.id,
            extra_payload={
                'storage_inbound_weight': 320.0,
                'storage_inbound_area': 1800.0,
                'shipment_weight': 184.0,
                'shipment_area': 920.0,
                'consignment_weight': 42.0,
                'finished_inventory_weight': 3562.0,
                'actual_inventory_weight': 3520.0,
            },
        )
        db.add_all([workshop, shift, user, work_order, entry])
        db.commit()

        items = summarize_mobile_inventory(db, target_date=date(2026, 4, 17))

        assert items == [
            {
                'workshop_id': 11,
                'workshop_name': '成品库',
                'team_id': None,
                'team_name': None,
                'source': 'owner_only',
                'source_label': '专项补录',
                'source_variant': 'owner',
                'storage_prepared': 0.0,
                'storage_finished': 320.0,
                'shipment_weight': 184.0,
                'contract_received': 0.0,
                'storage_inbound_area': 1800.0,
                'shipment_area': 920.0,
                'consignment_weight': 42.0,
                'finished_inventory_weight': 3562.0,
                'actual_inventory_weight': 3520.0,
            }
        ]
    finally:
        db.close()


def test_summarize_mobile_inventory_prefers_owner_only_inventory_source_over_mobile_report(tmp_path) -> None:
    db = build_session(tmp_path)
    try:
        workshop = Workshop(id=11, code='CPK', name='成品库', workshop_type='inventory', sort_order=1, is_active=True)
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
        user = User(id=7, username='owner', password_hash='x', name='成品库负责人', role='inventory_keeper', is_active=True)
        mobile_report = MobileShiftReport(
            id=9,
            business_date=date(2026, 4, 17),
            shift_config_id=shift.id,
            workshop_id=workshop.id,
            team_id=None,
            owner_user_id=user.id,
            leader_user_id=user.id,
            leader_name=user.name,
            report_status='submitted',
            storage_finished=111.0,
            shipment_weight=99.0,
        )
        work_order = WorkOrder(
            id=21,
            tracking_card_no='OWNER-CPK-20260417-A-INVENTORY_KEEPER',
            process_route_code='OWNER',
            overall_status='submitted',
            created_by=user.id,
        )
        entry = WorkOrderEntry(
            id=31,
            work_order_id=work_order.id,
            workshop_id=workshop.id,
            shift_id=shift.id,
            business_date=date(2026, 4, 17),
            entry_type='completed',
            entry_status='submitted',
            created_by=user.id,
            created_by_user_id=user.id,
            extra_payload={
                'storage_inbound_weight': 320.0,
                'shipment_weight': 184.0,
            },
        )
        db.add_all([workshop, shift, user, mobile_report, work_order, entry])
        db.commit()

        items = summarize_mobile_inventory(db, target_date=date(2026, 4, 17))

        assert items[0]['storage_finished'] == 320.0
        assert items[0]['shipment_weight'] == 184.0
        assert items[0]['source'] == 'owner_only'
        assert items[0]['source_label'] == '专项补录'
        assert items[0]['source_variant'] == 'owner'
    finally:
        db.close()
