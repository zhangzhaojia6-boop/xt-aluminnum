from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.consumable import DailyConsumableLog
from app.models.master import Equipment, Workshop
from app.models.mes import MesStockRecord, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.report import daily_overview_builder


BUSINESS_DATE = date(2026, 6, 9)
PACKAGING_INBOUND_OUTPUT_FIELD = 'packaging_inbound_output_tons'


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-mes-packaging.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Workshop.__table__,
            Equipment.__table__,
            ShiftConfig.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            DailyConsumableLog.__table__,
            MesStockRecord.__table__,
            MesWorkshopProcessRecord.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def test_mes_packaging_output_is_grouped_by_business_date(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                MesWorkshopProcessRecord(
                    source_id='pkg-jz-1',
                    source_path='sqlserver',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=14.111,
                    business_date=BUSINESS_DATE,
                ),
                MesWorkshopProcessRecord(
                    source_id='pkg-lj-1',
                    source_path='sqlserver',
                    workshop_name='拉矫车间',
                    process_name='包装',
                    output_weight_tons=12.719,
                    business_date=BUSINESS_DATE,
                ),
                MesWorkshopProcessRecord(
                    source_id='cold-roll-1',
                    source_path='sqlserver',
                    workshop_name='2050冷轧车间',
                    process_name='冷轧',
                    output_weight_tons=99,
                    business_date=BUSINESS_DATE,
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        totals = daily_overview_builder._query_mes_packaging_output_by_date(db, BUSINESS_DATE, BUSINESS_DATE)

    assert totals == {BUSINESS_DATE: 26.83}


def test_mes_packaging_output_prefers_mes_stock_in_records_over_process_packaging(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                Workshop(id=1, code='JZ', name='精整车间', is_active=True),
                MesStockRecord(
                    source_id='stock-in-today',
                    source_path='sqlserver',
                    net_weight_tons=341.707,
                    status_name='1',
                    business_date=BUSINESS_DATE,
                    source_payload={
                        'FromDepartment': '精整',
                        'ToDepartment': '成品库',
                        'Status': 1,
                    },
                ),
                MesWorkshopProcessRecord(
                    source_id='pkg-today',
                    source_path='sqlserver',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=44.23,
                    business_date=BUSINESS_DATE,
                ),
                MesWorkshopProcessRecord(
                    source_id='pkg-yesterday',
                    source_path='sqlserver',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=22.25,
                    business_date=date(2026, 6, 8),
                ),
                DailyConsumableLog(
                    workshop_id=1,
                    workshop_type='finishing',
                    business_date=BUSINESS_DATE,
                    payload={PACKAGING_INBOUND_OUTPUT_FIELD: 18.75},
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        totals = daily_overview_builder._query_mes_packaging_output_by_date(db, BUSINESS_DATE, BUSINESS_DATE)

    assert totals == {BUSINESS_DATE: 341.71}


def test_mes_packaging_output_counts_legacy_stock_rows_without_department_payload(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesStockRecord(
                source_id='stock-legacy-row',
                source_path='sqlserver:stock_records',
                net_weight_tons=25.357,
                status_name='1',
                business_date=BUSINESS_DATE,
                source_payload={},
            )
        )
        db.commit()

    with session_factory() as db:
        totals = daily_overview_builder._query_mes_packaging_output_by_date(db, BUSINESS_DATE, BUSINESS_DATE)

    assert totals == {BUSINESS_DATE: 25.36}


def test_mes_packaging_output_rejects_non_finished_stock_destination(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesStockRecord(
                source_id='stock-middle-warehouse',
                source_path='sqlserver:stock_records',
                net_weight_tons=25.357,
                status_name='1',
                business_date=BUSINESS_DATE,
                source_payload={
                    'FromDepartment': '精整',
                    'ToDepartment': '半成品库',
                    'Status': 1,
                },
            )
        )
        db.commit()

    with session_factory() as db:
        totals = daily_overview_builder._query_mes_packaging_output_by_date(db, BUSINESS_DATE, BUSINESS_DATE)

    assert totals == {}


def test_plant_output_uses_mes_stock_packaging_for_daily_and_monthly(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                Workshop(id=1, code='JZ', name='精整车间', is_active=True),
                Workshop(id=2, code='CPK', name='成品库', is_active=True),
                User(
                    id=7,
                    username='CPK-FS',
                    password_hash='x',
                    name='成品库内勤',
                    role='storage_owner',
                    workshop_id=2,
                    is_mobile_user=True,
                    is_active=True,
                ),
                MesStockRecord(
                    source_id='stock-in-today',
                    source_path='sqlserver',
                    net_weight_tons=36.5,
                    status_name='1',
                    business_date=BUSINESS_DATE,
                    source_payload={
                        'FromDepartment': '精整',
                        'ToDepartment': '成品库',
                        'Status': 1,
                    },
                ),
                MesWorkshopProcessRecord(
                    source_id='pkg-yesterday',
                    source_path='sqlserver',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=22.25,
                    business_date=date(2026, 6, 8),
                ),
                DailyConsumableLog(
                    workshop_id=1,
                    workshop_type='finishing',
                    business_date=BUSINESS_DATE,
                    payload={PACKAGING_INBOUND_OUTPUT_FIELD: 18.75},
                ),
                WorkOrder(
                    id=100,
                    tracking_card_no='OWNER-storage_owner-7-2026-06-09',
                    process_route_code='owner_daily',
                    overall_status='created',
                    created_by=7,
                ),
                WorkOrderEntry(
                    work_order_id=100,
                    workshop_id=2,
                    machine_id=None,
                    shift_id=None,
                    business_date=BUSINESS_DATE,
                    entry_type='owner_daily',
                    entry_status='submitted',
                    created_by=7,
                    created_by_user_id=7,
                    extra_payload={
                        'park_inbound_daily': 12.5,
                        'new_plant_inbound_daily': 14.75,
                    },
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        plant = daily_overview_builder._build_plant_output(db, BUSINESS_DATE, {'total_electricity': 3650})

    assert plant['basis'] == 'mes_packaging_output'
    assert plant['basis_label'] == '包装产量'
    assert plant['business_day_start'] == '07:30'
    assert plant['daily_output_source'] == 'mes_stock_records'
    assert plant['daily_output'] == 36.5
    assert plant['packaging_output'] == 36.5
    assert plant['yesterday_output'] == 22.25
    assert plant['monthly_output'] == 58.75
    assert plant['monthly_output_source'] == 'mes_packaging_output'
    assert plant['packaging_monthly_output'] == 58.75
    assert plant['packaging_monthly_source'] == 'mes_packaging_output'
    assert plant['monthly_average_output'] == round(58.75 / 9, 2)
    assert plant['finished_inbound_source'] == 'storage_owner_daily_entry'
    assert plant['finished_inbound_output'] == 27.25
    assert plant['finished_inbound_basis_label'] == '全厂入库产量'
    assert plant['finished_inbound_monthly_output'] == 27.25
    assert plant['finished_inbound_monthly_average'] == round(27.25 / 9, 2)
    assert plant['energy_per_ton'] == 100.0


def test_plant_output_does_not_use_consumable_packaging_as_storage_owner_inbound(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                Workshop(id=1, code='JZ', name='精整车间', is_active=True),
                DailyConsumableLog(
                    workshop_id=1,
                    workshop_type='finishing',
                    business_date=BUSINESS_DATE,
                    payload={PACKAGING_INBOUND_OUTPUT_FIELD: 18.75},
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        plant = daily_overview_builder._build_plant_output(db, BUSINESS_DATE, {'total_electricity': 3650})

    assert plant['basis'] == 'mes_packaging_output'
    assert plant['daily_output'] == 0.0
    assert plant['packaging_output'] == 0.0
    assert plant['finished_inbound_output'] == 0.0
    assert plant['energy_per_ton'] is None
