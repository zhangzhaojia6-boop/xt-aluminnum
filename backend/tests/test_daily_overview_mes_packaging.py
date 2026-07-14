from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.consumable import DailyConsumableLog
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot, MesStockRecord, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.report import daily_overview_builder, mes_home_packaging_fact


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
            MesCoilSnapshot.__table__,
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


def test_mes_packaging_output_uses_process_packaging_not_stock_records(tmp_path) -> None:
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

    assert totals == {BUSINESS_DATE: 44.23}


def test_plant_output_uses_packaging_process_and_keeps_inbound_as_comparison(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                MesStockRecord(
                    source_id='header-inbound-2026-06-17',
                    source_path='sqlserver:stock_header_records',
                    net_weight_tons=303.031,
                    business_date=BUSINESS_DATE,
                    source_payload={},
                ),
                MesStockRecord(
                    source_id='detail-inbound-2026-06-17',
                    source_path='sqlserver:stock_records',
                    net_weight_tons=271.996,
                    status_name='1',
                    business_date=BUSINESS_DATE,
                    source_payload={
                        'FromDepartment': '园区精整',
                        'ToDepartment': '成品库',
                        'Status': 1,
                    },
                ),
                MesWorkshopProcessRecord(
                    source_id='pkg-process-2026-06-09',
                    source_path='sqlserver:workshop_process_records',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=66.136,
                    business_date=BUSINESS_DATE,
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        plant = daily_overview_builder._build_plant_output(db, BUSINESS_DATE, {'total_electricity': 0})

    assert plant['daily_output'] == 66.14
    assert plant['packaging_output'] == 66.14
    assert plant['finished_inbound_output'] == 303.03
    assert plant['finished_inbound_source'] == 'mes_stock_header_records'
    assert plant['daily_output_source'] == 'mes_workshop_process_records'
    assert plant['source_table'] == 'MES_ProductProcessRecord'
    assert plant['source_weight_field'] == 'EndWeight'
    assert plant['source_time_field'] == 'EndDatetime'
    assert plant['date_column'] == 'business_date'
    assert plant['mes_home_packaging_fact']['mes_home_daily_output'] == 66.14
    assert plant['mes_home_packaging_fact']['mes_home_month_to_date_output'] == 66.14
    assert plant['factory_packaging_fact']['factory_packaging_daily_output'] == 66.14
    assert plant['factory_packaging_fact']['source_pages'] == [
        {'page': '包装管理 / 包装录入', 'path': '/Pack/Index'},
        {'page': '包装管理 / 成品调拨单', 'path': '/Allocation/Index'},
    ]
    assert plant['factory_packaging_fact']['finished_transfer_day']['daily_output'] == 272.0
    assert plant['factory_packaging_fact']['finished_transfer_day']['by_workshop'] == [
        {'workshop_name': '园区剪切', 'output': 272.0, 'row_count': 1}
    ]
    assert plant['row_count'] == 1
    assert plant['latest_row_id'] == 1
    assert plant['source_trace_id'] == 'projection-read:mes_workshop_process_records:1:1'
    assert plant['finished_inbound_row_count'] == 1
    assert plant['finished_inbound_latest_row_id'] == 1
    assert plant['finished_inbound_trace_id'] == 'projection-read:mes_stock_records:1:1'
    assert plant['business_window_start'] == f'{BUSINESS_DATE.isoformat()}T07:50:00+08:00'
    assert plant['business_window_end'] == f'{(BUSINESS_DATE + timedelta(days=1)).isoformat()}T07:50:00+08:00'


def test_factory_packaging_fact_maps_park_finishing_to_park_shearing(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                MesWorkshopProcessRecord(
                    source_id='pkg-jz',
                    source_path='sqlserver:workshop_process_records',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=10.0,
                    business_date=BUSINESS_DATE,
                ),
                MesWorkshopProcessRecord(
                    source_id='pkg-park',
                    source_path='sqlserver:workshop_process_records',
                    workshop_name='园区精整',
                    process_name='包装',
                    output_weight_tons=20.0,
                    business_date=BUSINESS_DATE,
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        fact = mes_home_packaging_fact.build_mes_home_packaging_fact(db, target_date=BUSINESS_DATE)

    assert fact['source_table'] == 'MES_ProductProcessRecord'
    assert fact['projection_table'] == 'mes_workshop_process_records'
    assert fact['factory_packaging_daily_output'] == 30.0
    assert fact['business_day']['by_workshop'] == [
        {'workshop_name': '园区剪切', 'output': 20.0, 'row_count': 1},
        {'workshop_name': '精整', 'output': 10.0, 'row_count': 1},
    ]


def test_mes_delivery_output_requires_delivery_code(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                MesStockRecord(
                    source_id='delivery-with-code',
                    source_path='sqlserver:delivery_records',
                    net_weight_tons=222.306,
                    business_date=BUSINESS_DATE,
                    source_payload={'DeliveryCode': 'FH-1'},
                ),
                MesStockRecord(
                    source_id='delivery-without-code',
                    source_path='sqlserver:delivery_records',
                    net_weight_tons=2.617,
                    business_date=BUSINESS_DATE,
                    source_payload={'DeliveryCode': ''},
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        totals = daily_overview_builder._query_mes_delivery_output_by_date(db, BUSINESS_DATE, BUSINESS_DATE)

    assert totals == {BUSINESS_DATE: 222.31}


def test_mes_packaging_output_ignores_legacy_stock_rows_without_process_record(tmp_path) -> None:
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

    assert totals == {}


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


def test_plant_output_uses_process_packaging_for_daily_and_monthly(tmp_path) -> None:
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
                    source_id='header-in-today',
                    source_path='sqlserver:stock_header_records',
                    net_weight_tons=27.25,
                    status_name='1',
                    business_date=BUSINESS_DATE,
                    source_payload={
                        'TotalNetWeight': '27250',
                        'InStockDate': '2026-06-09 10:00:00',
                    },
                ),
                MesWorkshopProcessRecord(
                    source_id='pkg-today',
                    source_path='sqlserver:workshop_process_records',
                    workshop_name='精整',
                    process_name='包装',
                    output_weight_tons=36.5,
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
    assert plant['business_day_start'] == '07:50'
    assert plant['daily_output_source'] == 'mes_workshop_process_records'
    assert plant['daily_output'] == 36.5
    assert plant['packaging_output'] == 36.5
    assert plant['yesterday_output'] == 22.25
    assert plant['monthly_output'] == 58.75
    assert plant['monthly_output_source'] == 'mes_packaging_output'
    assert plant['packaging_monthly_output'] == 58.75
    assert plant['packaging_monthly_source'] == 'mes_packaging_output'
    assert plant['monthly_average_output'] == round(58.75 / 9, 2)
    assert plant['finished_inbound_source'] == 'mes_stock_header_records'
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
