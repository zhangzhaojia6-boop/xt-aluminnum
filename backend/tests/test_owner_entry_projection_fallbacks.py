from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Workshop
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.models.energy import EnergyImportRecord
from app.services.contract_canonical_service import build_contract_projection
from app.services.energy_service import get_energy_summary, summarize_energy_for_date, workshop_energy_summary


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'owner-entry-fallbacks.db'}", future=True)
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


class _EmptyEnergyQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return []


class _EnergyFallbackDB:
    def __init__(self, session):
        self._session = session

    def query(self, *args, **kwargs):
        if args and args[0] is EnergyImportRecord:
            return _EmptyEnergyQuery()
        return self._session.query(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._session, item)


def _seed_inventory_owner_rows(db) -> None:
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
    user = User(id=7, username='owner', password_hash='x', name='专项负责人', role='contracts', is_active=True)
    contract_work_order = WorkOrder(
        id=21,
        tracking_card_no='OWNER-CPK-20260417-A-CONTRACTS',
        process_route_code='OWNER',
        overall_status='submitted',
        created_by=user.id,
    )
    utility_work_order = WorkOrder(
        id=22,
        tracking_card_no='OWNER-CPK-20260417-A-UTILITY_MANAGER',
        process_route_code='OWNER',
        overall_status='submitted',
        created_by=user.id,
    )
    contract_entry = WorkOrderEntry(
        id=31,
        work_order_id=contract_work_order.id,
        workshop_id=workshop.id,
        shift_id=shift.id,
        business_date=date(2026, 4, 17),
        entry_type='completed',
        entry_status='submitted',
        created_by=user.id,
        created_by_user_id=user.id,
        extra_payload={
            'daily_contract_weight': 59.0,
            'month_to_date_contract_weight': 2991.0,
            'daily_input_weight': 237.0,
            'month_to_date_input_weight': 3319.0,
        },
    )
    utility_entry = WorkOrderEntry(
        id=32,
        work_order_id=utility_work_order.id,
        workshop_id=workshop.id,
        shift_id=shift.id,
        business_date=date(2026, 4, 17),
        entry_type='completed',
        entry_status='submitted',
        created_by=user.id,
        created_by_user_id=user.id,
        extra_payload={
            'total_electricity_kwh': 1000.0,
            'new_plant_electricity_kwh': 800.0,
            'park_electricity_kwh': 200.0,
            'total_gas_m3': 200.0,
            'groundwater_ton': 30.0,
            'tap_water_ton': 20.0,
        },
    )
    production = ShiftProductionData(
        id=41,
        business_date=date(2026, 4, 17),
        shift_config_id=shift.id,
        workshop_id=workshop.id,
        output_weight=250.0,
        data_source='manual',
        data_status='confirmed',
    )
    db.add_all([workshop, shift, user, contract_work_order, utility_work_order, contract_entry, utility_entry, production])
    db.commit()


def test_build_contract_projection_falls_back_to_owner_entry_payloads(tmp_path, monkeypatch) -> None:
    db = build_session(tmp_path)
    try:
        _seed_inventory_owner_rows(db)
        monkeypatch.setattr('app.services.contract_canonical_service.load_contract_snapshots', lambda *_args, **_kwargs: [])

        payload = build_contract_projection(db, target_date=date(2026, 4, 17))

        assert payload['daily_contract_weight'] == 59.0
        assert payload['month_to_date_contract_weight'] == 2991.0
        assert payload['daily_input_weight'] == 237.0
        assert payload['month_to_date_input_weight'] == 3319.0
        assert payload['quality_status'] == 'owner_only'
        assert payload['owner_entry_count'] == 1
    finally:
        db.close()


def test_build_contract_projection_prefers_owner_entry_over_same_day_snapshot(tmp_path, monkeypatch) -> None:
    db = build_session(tmp_path)
    try:
        _seed_inventory_owner_rows(db)
        monkeypatch.setattr(
            'app.services.contract_canonical_service.load_contract_snapshots',
            lambda *_args, **_kwargs: [
                SimpleNamespace(
                    business_date=date(2026, 4, 17),
                    sheet_name='导入快照',
                    delivery_scope='factory',
                    daily_contract_weight=1.0,
                    month_to_date_contract_weight=2.0,
                    daily_input_weight=3.0,
                    month_to_date_input_weight=4.0,
                    quality_status='ready',
                    source_batch_id=1,
                    lineage_hash='x',
                    to_dict=lambda: {'sheet_name': '导入快照'},
                )
            ],
        )

        payload = build_contract_projection(db, target_date=date(2026, 4, 17))

        assert payload['quality_status'] == 'owner_only'
        assert payload['daily_contract_weight'] == 59.0
        assert payload['month_to_date_contract_weight'] == 2991.0
    finally:
        db.close()


def test_summarize_energy_for_date_falls_back_to_owner_entry_payloads(tmp_path) -> None:
    session = build_session(tmp_path)
    db = _EnergyFallbackDB(session)
    try:
        _seed_inventory_owner_rows(db)

        payload = summarize_energy_for_date(db, business_date=date(2026, 4, 17))

        assert payload['electricity_value'] == 1000.0
        assert payload['gas_value'] == 200.0
        assert payload['water_value'] == 50.0
        assert payload['total_energy'] == 1250.0
        assert payload['total_output_weight'] == 250.0
        assert payload['energy_per_ton'] == 5.0
        assert payload['rows'][0]['source'] == 'owner_only'
    finally:
        session.close()


def test_get_energy_summary_falls_back_to_owner_entry_payloads(tmp_path) -> None:
    session = build_session(tmp_path)
    db = _EnergyFallbackDB(session)
    try:
        _seed_inventory_owner_rows(db)

        rows = get_energy_summary(db, business_date=date(2026, 4, 17), workshop_id=11)

        assert rows[0]['source'] == 'owner_only'
        assert rows[0]['electricity_value'] == 1000.0
        assert rows[0]['gas_value'] == 200.0
        assert rows[0]['water_value'] == 50.0
    finally:
        session.close()


def test_workshop_energy_summary_falls_back_to_owner_entry_payloads(tmp_path) -> None:
    session = build_session(tmp_path)
    db = _EnergyFallbackDB(session)
    try:
        _seed_inventory_owner_rows(db)

        payload = workshop_energy_summary(db, business_date=date(2026, 4, 17), workshop_id=11)

        assert payload['electricity_value'] == 1000.0
        assert payload['gas_value'] == 200.0
        assert payload['water_value'] == 50.0
        assert payload['total_energy'] == 1250.0
        assert payload['output_weight'] == 250.0
        assert payload['energy_per_ton'] == 5.0
    finally:
        session.close()


def test_summarize_energy_for_date_owner_only_rows_do_not_double_count_output(tmp_path) -> None:
    session = build_session(tmp_path)
    db = _EnergyFallbackDB(session)
    try:
        _seed_inventory_owner_rows(db)
        second_work_order = WorkOrder(
            id=23,
            tracking_card_no='OWNER-CPK-20260417-B-UTILITY_MANAGER',
            process_route_code='OWNER',
            overall_status='submitted',
            created_by=7,
        )
        second_entry = WorkOrderEntry(
            id=33,
            work_order_id=23,
            workshop_id=11,
            shift_id=1,
            business_date=date(2026, 4, 17),
            entry_type='completed',
            entry_status='submitted',
            created_by=7,
            created_by_user_id=7,
            extra_payload={
                'total_electricity_kwh': 1000.0,
                'total_gas_m3': 200.0,
                'groundwater_ton': 30.0,
                'tap_water_ton': 20.0,
            },
        )
        db.add_all([second_work_order, second_entry])
        db.commit()

        payload = summarize_energy_for_date(db, business_date=date(2026, 4, 17))

        assert payload['total_energy'] == 2500.0
        assert payload['total_output_weight'] == 250.0
        assert payload['energy_per_ton'] == 10.0
    finally:
        session.close()
