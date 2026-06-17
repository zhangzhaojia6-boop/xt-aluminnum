from __future__ import annotations

from datetime import UTC, date, datetime
from datetime import time
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.attendance import AttendanceSchedule
from app.models.consumable import DailyConsumableLog
from app.models.imports import ImportBatch, ImportRow
from app.models.master import Employee, Workshop
from app.models.mes import MesCoilSnapshot, MesDailyWipSnapshot, MesWipTotalSnapshot, MesWorkshopProcessRecord, MesYieldRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import report_service
from app.services.report import daily_overview_builder
from app.services.report import dashboard_builder


def test_daily_overview_exposes_plant_output_basis_and_plant_cost(monkeypatch) -> None:
    monkeypatch.setattr(daily_overview_builder, '_workshop_map', lambda *_args, **_kwargs: {1: '热轧车间'})
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_workshop_output',
        lambda *_args, **_kwargs: [
            {
                'workshop_id': 1,
                'workshop': '热轧车间',
                'daily_output': 120.0,
                'monthly_output': 600.0,
                'yesterday_output': 110.0,
                'delta': 10.0,
            }
        ],
    )
    monkeypatch.setattr(daily_overview_builder, '_build_wip_distribution', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_yield_rates',
        lambda *_args, **_kwargs: {'daily': 95.5, 'daily_delta': 0.5, 'monthly': 96.1},
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_energy',
        lambda *_args, **_kwargs: {
            'total_electricity': 3200.0,
            'total_gas': 0.0,
            'electricity_cost': 2.08,
            'gas_cost': 0.0,
            'total_cost': 2.08,
            'by_workshop': [],
        },
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_contracts',
        lambda *_args, **_kwargs: {'daily_new': 2, 'monthly_total': 10, 'remaining': 8, 'remaining_delta': 1},
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_plant_output',
        lambda *_args, **_kwargs: {
            'daily_output': 18.5,
            'yesterday_output': 17.2,
            'monthly_output': 220.0,
            'basis': 'mes_packaging_output',
            'basis_label': '包装产量',
            'energy_per_ton': 172.97,
        },
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_shift_breakdown',
        lambda *_args, **_kwargs: {
            'business_date': '2026-05-29',
            'total_output': 120.0,
            'output_basis': 'mobile_coil_process_output',
            'output_basis_label': '工序下机量',
            'energy_per_ton': 172.97,
            'shifts': [],
        },
    )

    payload = daily_overview_builder.build_daily_production_overview(None, target_date=date(2026, 5, 29))

    assert payload['plant_output']['daily_output'] == 18.5
    assert payload['plant_output']['basis_label'] == '包装产量'
    assert payload['plant_cost']['basis_weight'] == 18.5
    assert payload['plant_cost']['cost_per_ton'] == round(2.08 * 10000 / 18.5, 0)
    assert payload['shift_breakdown']['output_basis_label'] == '工序下机量'
    assert payload['header_kpis'][0]['label'] == '包装产量'


def test_daily_overview_can_use_separate_wip_business_date(monkeypatch) -> None:
    seen: dict[str, date] = {}

    monkeypatch.setattr(daily_overview_builder, '_workshop_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(daily_overview_builder, '_build_workshop_output', lambda *_args, **_kwargs: [])

    def fake_wip(_db, business_date: date):
        seen['wip_date'] = business_date
        return [{'workshop': '冷轧车间', 'coil_count': 1, 'total_weight': 879.0}]

    monkeypatch.setattr(daily_overview_builder, '_build_wip_distribution', fake_wip)
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_yield_rates',
        lambda *_args, **_kwargs: {'daily': None, 'daily_delta': None, 'monthly': None},
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_energy',
        lambda *_args, **_kwargs: {
            'total_electricity': 0.0,
            'total_gas': 0.0,
            'electricity_cost': 0.0,
            'gas_cost': 0.0,
            'total_cost': 0.0,
            'by_workshop': [],
        },
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_contracts',
        lambda *_args, **_kwargs: {'daily_new': 0, 'monthly_total': 0, 'remaining': 0, 'remaining_delta': 0},
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_plant_output',
        lambda *_args, **_kwargs: {'daily_output': 0.0, 'yesterday_output': 0.0, 'monthly_output': 0.0},
    )
    monkeypatch.setattr(daily_overview_builder, '_build_shift_breakdown', lambda *_args, **_kwargs: {})

    payload = daily_overview_builder.build_daily_production_overview(
        None,
        target_date=date(2026, 6, 16),
        wip_date=date(2026, 6, 17),
    )

    assert payload['target_date'] == '2026-06-16'
    assert payload['wip_business_date'] == '2026-06-17'
    assert seen['wip_date'] == date(2026, 6, 17)
    assert payload['header_kpis'][2]['value'] == 879.0


def test_daily_overview_defaults_wip_to_next_business_day(monkeypatch) -> None:
    seen: dict[str, date] = {}

    monkeypatch.setattr(daily_overview_builder, '_workshop_map', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(daily_overview_builder, '_build_workshop_output', lambda *_args, **_kwargs: [])

    def fake_wip(_db, business_date: date):
        seen['wip_date'] = business_date
        return []

    monkeypatch.setattr(daily_overview_builder, '_build_wip_distribution', fake_wip)
    monkeypatch.setattr(daily_overview_builder, '_build_yield_rates', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(daily_overview_builder, '_build_energy', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_contracts',
        lambda *_args, **_kwargs: {'daily_new': 0, 'monthly_total': 0, 'remaining': 0, 'remaining_delta': 0},
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_plant_output',
        lambda *_args, **_kwargs: {'daily_output': 0.0, 'yesterday_output': 0.0, 'monthly_output': 0.0},
    )
    monkeypatch.setattr(daily_overview_builder, '_build_shift_breakdown', lambda *_args, **_kwargs: {})

    payload = daily_overview_builder.build_daily_production_overview(None, target_date=date(2026, 6, 16))

    assert payload['wip_business_date'] == '2026-06-17'
    assert seen['wip_date'] == date(2026, 6, 17)


def test_owner_storage_inbound_supports_current_inventory_fields() -> None:
    assert daily_overview_builder._owner_storage_inbound_tons({
        'park_inbound_daily': 12.5,
        'new_plant_inbound_daily': 6.0,
    }) == 18.5
    assert daily_overview_builder._owner_storage_inbound_tons({
        'storage_inbound_weight': 7.2,
        'park_inbound_daily': 12.5,
    }) == 7.2
    assert daily_overview_builder._owner_storage_monthly_inbound_tons({
        'park_inbound_monthly': 120.5,
        'new_plant_inbound_monthly': 30.0,
    }) == 150.5
    assert daily_overview_builder._owner_storage_monthly_inbound_tons({
        'storage_inbound_monthly': 5013.725,
        'park_inbound_monthly': 120.5,
    }) == 5013.725


def test_finished_inbound_output_uses_storage_owner_daily_entry_only(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-packaging-output.db'}", future=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all([
        Workshop(id=1, code='JZ', name='精整车间', workshop_type='finishing', is_active=True),
        Workshop(id=2, code='LJ', name='拉矫车间', workshop_type='straightening', is_active=True),
        Workshop(id=3, code='JQ', name='园区剪切车间', workshop_type='shearing', is_active=True),
        Workshop(id=4, code='ZXTF-N', name='新厂在线退火', workshop_type='annealing', is_active=True),
        Workshop(id=5, code='CPK', name='成品库', workshop_type='inventory', is_active=True),
        User(id=7, username='CPK-FS', password_hash='x', name='成品库内勤', role='storage_owner', workshop_id=5, is_mobile_user=True),
    ])
    db.add_all([
        DailyConsumableLog(
            workshop_id=1,
            workshop_type='finishing',
            business_date=date(2026, 6, 4),
            payload={'packaging_inbound_output_tons': 10.5},
        ),
        DailyConsumableLog(
            workshop_id=2,
            workshop_type='straightening',
            business_date=date(2026, 6, 4),
            payload={'packaging_inbound_output_tons': 6.0},
        ),
        DailyConsumableLog(
            workshop_id=3,
            workshop_type='shearing',
            business_date=date(2026, 6, 4),
            payload={'packaging_inbound_output_tons': 2.0},
        ),
        DailyConsumableLog(
            workshop_id=4,
            workshop_type='annealing',
            business_date=date(2026, 6, 4),
            payload={'packaging_inbound_output_tons': 99.0},
        ),
        WorkOrder(id=100, tracking_card_no='OWNER-storage_owner-7-2026-06-04', process_route_code='owner_daily', created_by=7),
        WorkOrderEntry(
            work_order_id=100,
            workshop_id=5,
            machine_id=None,
            shift_id=None,
            business_date=date(2026, 6, 4),
            entry_type='owner_daily',
            entry_status='submitted',
            created_by=7,
            created_by_user_id=7,
            extra_payload={'park_inbound_daily': 20.0, 'new_plant_inbound_daily': 11.25},
        ),
    ])
    db.commit()

    totals = daily_overview_builder._query_finished_inbound_totals_by_date(
        db,
        date(2026, 6, 4),
        date(2026, 6, 4),
    )

    assert totals == {date(2026, 6, 4): 31.25}


def test_wip_distribution_uses_target_business_date_and_feeding_weight_reference(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-wip.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, MesDailyWipSnapshot.__table__])
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all([
        MesCoilSnapshot(
            coil_id='MES:OLD-WIP',
            tracking_card_no='OLD-WIP',
            business_date=date(2026, 5, 27),
            current_workshop='冷轧车间',
            current_process='轧制',
            material_weight=2500.0,
            feeding_weight=4.5,
        ),
        MesCoilSnapshot(
            coil_id='MES:TODAY-WIP',
            tracking_card_no='TODAY-WIP',
            business_date=date(2026, 5, 29),
            current_workshop='冷轧车间',
            current_process='轧制',
            material_weight=5000.0,
            feeding_weight=7.5,
        ),
        MesCoilSnapshot(
            coil_id='MES:STOCK',
            tracking_card_no='STOCK',
            business_date=date(2026, 5, 29),
            current_workshop='冷轧车间',
            current_process='入库',
            status_name='已入库',
            material_weight=9000.0,
            feeding_weight=9.0,
        ),
    ])
    db.commit()

    payload = daily_overview_builder._build_wip_distribution(db, date(2026, 5, 29))

    assert payload == [
        {
            'workshop': '冷轧车间',
            'coil_count': 1,
            'total_weight': 5.0,
            'feeding_weight': 7.5,
            'source_basis': 'mes_coil_snapshot_business_date',
            'source_label': '外部 MES 当日快照参考',
        }
    ]


def test_wip_distribution_prefers_daily_wip_snapshot_read_model(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-frozen-wip.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, MesDailyWipSnapshot.__table__])
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all([
        MesDailyWipSnapshot(
            business_date=date(2026, 5, 29),
            workshop_name='冷轧车间',
            process_name='轧制',
            coil_count=4,
            material_weight_tons=12.5,
            feeding_weight_tons=18.2,
            source='mes_coil_snapshot',
        ),
        MesCoilSnapshot(
            coil_id='MES:LIVE-WIP',
            tracking_card_no='LIVE-WIP',
            business_date=date(2026, 5, 29),
            current_workshop='冷轧车间',
            current_process='轧制',
            material_weight=999000.0,
            feeding_weight=999.0,
        ),
    ])
    db.commit()

    payload = daily_overview_builder._build_wip_distribution(db, date(2026, 5, 29))

    assert payload == [
        {
            'workshop': '冷轧车间',
            'coil_count': 4,
            'total_weight': 12.5,
            'feeding_weight': 18.2,
            'source_basis': 'mes_daily_wip_snapshot',
            'source_label': '外部 MES 当日快照参考',
        }
    ]


def test_wip_distribution_uses_wip_total_when_daily_snapshot_weight_is_zero(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-wip-total.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesDailyWipSnapshot.__table__, MesWipTotalSnapshot.__table__])
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all([
        MesDailyWipSnapshot(
            business_date=date(2026, 5, 29),
            workshop_name='新厂在线车间',
            process_name='北线退火',
            coil_count=3,
            material_weight_tons=0.0,
            feeding_weight_tons=28.5,
            source='mes_coil_snapshot',
        ),
        MesWipTotalSnapshot(
            source_id='新厂在线车间:北线退火',
            workshop_name='新厂在线车间',
            process_name='北线退火',
            doing_count=588,
            doing_weight_tons=4466.5,
            snapshot_at=datetime(2026, 5, 29, 8, 0, tzinfo=UTC),
        ),
    ])
    db.commit()

    payload = daily_overview_builder._build_wip_distribution(db, date(2026, 5, 29))

    assert payload == [
        {
            'workshop': '新厂在线车间',
            'coil_count': 588,
            'total_weight': 4.47,
            'feeding_weight': 28.5,
            'source_basis': 'mes_wip_total_snapshot',
            'source_label': '外部 MES 在制总量参考',
        }
    ]


def test_wip_distribution_ignores_zero_snapshots_and_total_fallback_when_positive_daily_exists(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-official-wip.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesDailyWipSnapshot.__table__, MesWipTotalSnapshot.__table__])
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all([
        MesDailyWipSnapshot(
            business_date=date(2026, 6, 17),
            workshop_name='精整分厂',
            process_name='精整',
            coil_count=0,
            material_weight_tons=576.5,
            feeding_weight_tons=0.0,
            source='output_skill_daily_report',
        ),
        MesDailyWipSnapshot(
            business_date=date(2026, 6, 17),
            workshop_name='2050车间',
            process_name='冷轧',
            coil_count=2,
            material_weight_tons=0.0,
            feeding_weight_tons=16.5,
            source='mes_coil_snapshot',
        ),
        MesWipTotalSnapshot(
            source_id='精整:包装',
            workshop_name='精整',
            process_name='包装',
            doing_count=33839,
            doing_weight_tons=264254.65,
            snapshot_at=datetime(2026, 6, 17, 8, 0, tzinfo=UTC),
        ),
    ])
    db.commit()

    payload = daily_overview_builder._build_wip_distribution(db, date(2026, 6, 17))

    assert payload == [
        {
            'workshop': '精整分厂',
            'coil_count': 0,
            'total_weight': 576.5,
            'feeding_weight': 0.0,
            'source_basis': 'mes_daily_wip_snapshot',
            'source_label': '外部 MES 当日快照参考',
        }
    ]


def test_wip_distribution_does_not_use_other_day_wip_total_snapshot(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-wip-total-strict-date.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, MesDailyWipSnapshot.__table__, MesWipTotalSnapshot.__table__])
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add(
        MesWipTotalSnapshot(
            source_id='latest-other-day',
            workshop_name='新厂在线车间',
            process_name='北线退火',
            doing_count=588,
            doing_weight_tons=4466.5,
            snapshot_at=datetime(2026, 5, 31, 8, 0, tzinfo=UTC),
        )
    )
    db.commit()

    payload = daily_overview_builder._build_wip_distribution(db, date(2026, 5, 29))

    assert payload == []


def test_wip_distribution_converts_large_wip_total_snapshot_weight_from_kg(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-wip-total-unit.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, MesDailyWipSnapshot.__table__, MesWipTotalSnapshot.__table__])
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add(
        MesWipTotalSnapshot(
            source_id='新厂在线车间:北线退火',
            workshop_name='新厂在线车间',
            process_name='北线退火',
            doing_count=588,
            doing_weight_tons=302338.2,
            snapshot_at=datetime(2026, 5, 29, 8, 0, tzinfo=UTC),
        )
    )
    db.commit()

    payload = daily_overview_builder._build_wip_distribution(db, date(2026, 5, 29))

    assert payload[0]['total_weight'] == 302.34


def test_contracts_derive_remaining_delta_from_yesterday_when_owner_entry_delta_missing(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-contract-delta.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[Workshop.__table__, WorkOrder.__table__, WorkOrderEntry.__table__, ImportBatch.__table__, ImportRow.__table__],
    )
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all(
        [
            Workshop(id=1, code='CPK', name='成品库', workshop_type='inventory', is_active=True),
            WorkOrder(id=1, tracking_card_no='OWNER-2026-06-15', process_route_code='owner_daily'),
            WorkOrder(id=2, tracking_card_no='OWNER-2026-06-16', process_route_code='owner_daily'),
            WorkOrderEntry(
                work_order_id=1,
                workshop_id=1,
                business_date=date(2026, 6, 15),
                entry_type='owner_daily',
                entry_status='submitted',
                extra_payload={
                    'daily_contract_weight': 303,
                    'remaining_contract_weight': 2699,
                },
            ),
            WorkOrderEntry(
                work_order_id=2,
                workshop_id=1,
                business_date=date(2026, 6, 16),
                entry_type='owner_daily',
                entry_status='submitted',
                extra_payload={
                    'daily_contract_weight': 66,
                    'remaining_contract_weight': 2569,
                },
            ),
        ]
    )
    db.commit()

    payload = daily_overview_builder._build_contracts(db, date(2026, 6, 16))

    assert payload['remaining'] == 2569.0
    assert payload['remaining_delta'] == -130.0


def test_workshop_output_uses_manual_for_named_workshops_and_mes_for_others(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-workshop-output-mixed.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            MesWorkshopProcessRecord.__table__,
        ],
    )
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all(
        [
            Workshop(id=1, code='RZ', name='热轧车间', workshop_type='hot_roll', is_active=True),
            Workshop(id=2, code='LZ1650', name='1650车间', workshop_type='cold_roll', is_active=True),
            Workshop(id=3, code='CH', name='园区淬火', workshop_type='quenching', is_active=True),
            WorkOrder(id=1, tracking_card_no='RZ-1', process_route_code='manual'),
            WorkOrder(id=2, tracking_card_no='LZ1650-1', process_route_code='manual'),
            WorkOrder(id=3, tracking_card_no='CH-1', process_route_code='manual'),
            WorkOrderEntry(
                work_order_id=1,
                workshop_id=1,
                business_date=date(2026, 5, 29),
                output_weight=88000,
                entry_type='mobile_coil',
                entry_status='submitted',
            ),
            WorkOrderEntry(
                work_order_id=2,
                workshop_id=2,
                business_date=date(2026, 5, 29),
                output_weight=7000,
                entry_type='mobile_coil',
                entry_status='submitted',
            ),
            WorkOrderEntry(
                work_order_id=3,
                workshop_id=3,
                business_date=date(2026, 5, 29),
                output_weight=5000,
                entry_type='mobile_coil',
                entry_status='submitted',
            ),
            MesWorkshopProcessRecord(
                source_id='mes-hot-roll',
                source_path='sqlserver',
                workshop_name='热轧车间',
                process_name='热轧',
                output_weight_tons=12,
                business_date=date(2026, 5, 29),
            ),
            MesWorkshopProcessRecord(
                source_id='mes-1650',
                source_path='sqlserver',
                workshop_name='1650车间',
                process_name='冷轧',
                output_weight_tons=33,
                business_date=date(2026, 5, 29),
                source_payload={'pass_count': 11},
            ),
            MesWorkshopProcessRecord(
                source_id='mes-quench',
                source_path='sqlserver',
                workshop_name='园区淬火',
                process_name='淬火',
                output_weight_tons=99,
                business_date=date(2026, 5, 29),
            ),
        ]
    )
    db.commit()

    rows = daily_overview_builder._build_workshop_output(
        db,
        date(2026, 5, 29),
        {1: '热轧车间', 2: '1650车间', 3: '园区淬火'},
    )
    by_name = {row['workshop']: row for row in rows}

    assert by_name['热轧车间']['daily_output'] == 88.0
    assert by_name['热轧车间']['source_basis'] == 'manual_mobile_coil'
    assert by_name['1650车间']['daily_output'] == 33.0
    assert by_name['1650车间']['source_basis'] == 'mes_workshop_process_records'
    assert by_name['1650车间']['pass_count_total'] == 11
    assert by_name['园区淬火']['daily_output'] == 5.0
    assert by_name['园区淬火']['source_basis'] == 'manual_mobile_coil'


def test_yield_rates_prefer_mes_algorithm_over_mobile_entry_yield(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-mes-yield.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            MesYieldRecord.__table__,
        ],
    )
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all(
        [
            Workshop(id=1, code='LZ1650', name='1650车间', workshop_type='cold_roll', is_active=True),
            WorkOrder(id=1, tracking_card_no='LZ1650-1', process_route_code='manual'),
            WorkOrderEntry(
                work_order_id=1,
                workshop_id=1,
                business_date=date(2026, 5, 29),
                output_weight=99000,
                input_weight=100000,
                yield_rate=99.0,
                entry_type='mobile_coil',
                entry_status='submitted',
            ),
            MesYieldRecord(
                source_id='yield-yesterday',
                source_path='sqlserver',
                feeding_weight_tons=50,
                in_stock_net_weight_tons=40,
                business_date=date(2026, 5, 28),
            ),
            MesYieldRecord(
                source_id='yield-today',
                source_path='sqlserver',
                feeding_weight_tons=100,
                in_stock_net_weight_tons=85,
                yield_rate=10,
                business_date=date(2026, 5, 29),
            ),
        ]
    )
    db.commit()

    payload = daily_overview_builder._build_yield_rates(db, date(2026, 5, 29))

    assert payload['daily'] == 85.0
    assert payload['daily_delta'] == 5.0
    assert payload['monthly'] == 83.33
    assert payload['basis'] == 'mes_yield_records'


def test_yield_rates_prefer_official_owner_daily_report_when_present(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-owner-yield.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            MesYieldRecord.__table__,
        ],
    )
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all(
        [
            Workshop(id=1, code='CPK', name='成品库', is_active=True),
            WorkOrder(id=1, tracking_card_no='OWNER-2026-06-15', process_route_code='owner_daily'),
            WorkOrderEntry(
                work_order_id=1,
                workshop_id=1,
                business_date=date(2026, 6, 15),
                entry_type='owner_daily',
                entry_status='submitted',
                extra_payload={'plant_daily_yield_rate': 86.24},
            ),
            WorkOrder(id=2, tracking_card_no='OWNER-2026-06-16', process_route_code='owner_daily'),
            WorkOrderEntry(
                work_order_id=2,
                workshop_id=1,
                business_date=date(2026, 6, 16),
                entry_type='owner_daily',
                entry_status='submitted',
                extra_payload={'plant_daily_yield_rate': 84.86, 'plant_monthly_yield_rate': 86.0},
            ),
            MesYieldRecord(
                source_id='yield-today',
                source_path='sqlserver',
                feeding_weight_tons=100,
                in_stock_net_weight_tons=96.53,
                business_date=date(2026, 6, 16),
            ),
        ]
    )
    db.commit()

    payload = daily_overview_builder._build_yield_rates(db, date(2026, 6, 16))

    assert payload['daily'] == 84.86
    assert payload['daily_delta'] == -1.38
    assert payload['monthly'] == 86.0
    assert payload['basis'] == 'owner_daily_report'


def test_build_plant_output_keeps_inbound_as_comparison_when_mes_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        daily_overview_builder,
        '_query_mes_packaging_output_with_source_by_date',
        lambda *_args, **_kwargs: ({}, {}),
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_query_finished_inbound_totals_by_date',
        lambda *_args, **_kwargs: {
            date(2026, 5, 28): 0.8,
            date(2026, 5, 29): 2.0,
        },
    )
    monkeypatch.setattr(daily_overview_builder, '_query_owner_storage_monthly_inbound_by_date', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(daily_overview_builder, '_query_owner_storage_direct_inbound_by_date', lambda *_args, **_kwargs: {})
    energy = {
        'total_electricity': 400.0,
        'total_gas': 0.0,
        'electricity_cost': 0.26,
        'gas_cost': 0.0,
        'total_cost': 0.26,
        'by_workshop': [],
    }

    payload = daily_overview_builder._build_plant_output(None, date(2026, 5, 29), energy)

    assert payload['daily_output'] == 0.0
    assert payload['yesterday_output'] == 0.0
    assert payload['monthly_output'] == 2.8
    assert payload['monthly_output_source'] == 'storage_owner_daily_entry'
    assert payload['basis'] == 'mes_packaging_output'
    assert payload['basis_label'] == '包装产量'
    assert payload['finished_inbound_output'] == 2.0
    assert payload['finished_inbound_monthly_output'] == 2.8


def test_build_plant_output_uses_official_owner_daily_and_monthly_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        daily_overview_builder,
        '_query_mes_packaging_output_with_source_by_date',
        lambda *_args, **_kwargs: ({date(2026, 6, 16): 308.68}, {date(2026, 6, 16): 'mes_stock_records'}),
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_query_finished_inbound_totals_by_date',
        lambda *_args, **_kwargs: {date(2026, 6, 16): 328.033},
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_query_owner_storage_direct_inbound_by_date',
        lambda *_args, **_kwargs: {date(2026, 6, 15): 305.848, date(2026, 6, 16): 328.033},
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_query_owner_storage_monthly_inbound_by_date',
        lambda *_args, **_kwargs: {date(2026, 6, 16): 5013.725},
    )

    payload = daily_overview_builder._build_plant_output(None, date(2026, 6, 16), {'total_electricity': 0})

    assert payload['daily_output'] == 328.03
    assert payload['yesterday_output'] == 305.85
    assert payload['monthly_output'] == 5013.73
    assert payload['finished_inbound_output'] == 328.03
    assert payload['mes_packaging_output'] == 308.68
    assert payload['daily_output_source'] == 'storage_owner_daily_entry'


def test_daily_overview_contracts_use_weight_projection(monkeypatch) -> None:
    monkeypatch.setattr(
        daily_overview_builder,
        'build_contract_projection',
        lambda *_args, **_kwargs: {
            'daily_contract_weight': 59.5,
            'month_to_date_contract_weight': 2991.25,
            'remaining_contract_weight': 1200.0,
            'remaining_contract_delta_weight': -30.0,
            'owner_entry_count': 1,
            'quality_status': 'owner_only',
        },
    )

    payload = daily_overview_builder._build_contracts(None, date(2026, 5, 29))

    assert payload['daily_new'] == 59.5
    assert payload['monthly_total'] == 2991.25
    assert payload['remaining'] == 1200.0
    assert payload['remaining_delta'] == -30.0
    assert payload['unit'] == '吨'


def test_build_energy_returns_none_when_no_real_energy_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        daily_overview_builder.energy_service,
        'summarize_energy_for_date',
        lambda *_args, **_kwargs: {
            'electricity_value': 0.0,
            'gas_value': 0.0,
            'primary_source': 'none',
            'rows': [],
            'owner_totals': {'electricity_value': 0.0, 'gas_value': 0.0, 'total_energy': 0.0, 'row_count': 0},
            'mobile_totals': {'total_energy': 0.0, 'row_count': 0},
            'system_totals': {'total_energy': 0.0, 'row_count': 0},
            'energy_per_ton': None,
        },
    )

    payload = daily_overview_builder._build_energy(None, date(2026, 5, 29))

    assert payload['data_available'] is False
    assert payload['total_electricity'] is None
    assert payload['total_gas'] is None
    assert payload['owner_electricity'] is None
    assert payload['total_cost'] is None


def test_build_timeseries_uses_mes_packaging_plant_output(monkeypatch) -> None:
    monkeypatch.setattr(
        daily_overview_builder,
        '_query_plant_output_totals_by_date',
        lambda *_args, **_kwargs: {
            date(2026, 5, 28): 1054.039,
            date(2026, 5, 29): 152.124,
        },
    )
    monkeypatch.setattr(
        dashboard_builder.energy_service,
        'summarize_energy_for_date',
        lambda *_args, **kwargs: {'electricity_value': 3200.0 if kwargs['business_date'].day == 29 else 18000.0},
    )

    payload = report_service.build_timeseries(None, start_date=date(2026, 5, 28), end_date=date(2026, 5, 29))

    assert payload == [
        {'date': '2026-05-28', 'output': 1054039.0, 'energy': 18000.0},
        {'date': '2026-05-29', 'output': 152124.0, 'energy': 3200.0},
    ]


def test_factory_dashboard_runtime_output_uses_mes_packaging_totals(monkeypatch) -> None:
    monkeypatch.setattr(
        daily_overview_builder,
        '_query_plant_output_totals_by_date',
        lambda *_args, **_kwargs: {date(2026, 5, 29): 1.5},
    )

    assert dashboard_builder._current_shift_output(None, target_date=date(2026, 5, 29)) == 1.5


def test_shift_breakdown_counts_distinct_workshops_not_coils(monkeypatch) -> None:
    shift_a = SimpleNamespace(id=1, code='A', name='长白班', start_time=time(7, 30), end_time=time(15, 30))
    shift_b = SimpleNamespace(id=2, code='B', name='小夜', start_time=time(15, 30), end_time=time(23, 30))

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def join(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def distinct(self):
            return self

        def all(self):
            return self.rows

    class FakeDB:
        def query(self, *args):
            if args and args[0] is daily_overview_builder.ShiftConfig:
                return FakeQuery([shift_a, shift_b])
            if args and args[0] is daily_overview_builder.Workshop:
                return FakeQuery([
                    SimpleNamespace(id=10, code='LZ', name='冷轧车间', is_active=True),
                    SimpleNamespace(id=11, code='JZ', name='精整车间', is_active=True),
                ])
            return FakeQuery([
                SimpleNamespace(workshop_id=10, shift_config_id=1),
                SimpleNamespace(workshop_id=11, shift_config_id=1),
                SimpleNamespace(workshop_id=10, shift_config_id=2),
            ])

    monkeypatch.setattr(
        daily_overview_builder,
        '_query_latest_mobile_coil_rows',
        lambda *_args, **_kwargs: [
            SimpleNamespace(shift_id=1, workshop_id=10, output_weight=1000, energy_kwh=10),
            SimpleNamespace(shift_id=1, workshop_id=10, output_weight=2000, energy_kwh=20),
            SimpleNamespace(shift_id=1, workshop_id=11, output_weight=3000, energy_kwh=30),
            SimpleNamespace(shift_id=2, workshop_id=10, output_weight=4000, energy_kwh=40),
        ],
    )

    payload = daily_overview_builder._build_shift_breakdown(FakeDB(), date(2026, 5, 29))

    by_code = {item['shift_code']: item for item in payload['shifts']}
    assert [item['shift_code'] for item in payload['shifts']] == ['A', 'B', 'C']
    assert by_code['A']['shift_count'] == 3
    assert by_code['A']['reported_workshops'] == 2
    assert by_code['A']['expected_workshops'] == 2
    assert by_code['B']['reported_workshops'] == 1


def test_shift_breakdown_excludes_factory_special_workshop_from_expected_total(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-shift-breakdown.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Employee.__table__,
            ShiftConfig.__table__,
            AttendanceSchedule.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
        ],
    )
    session_factory = sessionmaker(bind=engine, future=True)

    with session_factory() as db:
        db.add_all(
            [
                Workshop(id=1, code='ZR2', name='铸二车间', workshop_type='casting', sort_order=1, is_active=True),
                Workshop(id=2, code='FACTORY', name='全厂', workshop_type=None, sort_order=99, is_active=True),
                Employee(id=1, employee_no='E001', name='甲', workshop_id=1, is_active=True),
                Employee(id=2, employee_no='E002', name='乙', workshop_id=2, is_active=True),
                ShiftConfig(id=1, code='A', name='长白班', shift_type='day', start_time=time(7, 30), end_time=time(15, 30), is_cross_day=False, sort_order=1, is_active=True),
                WorkOrder(id=1, tracking_card_no='TC-001', process_route_code='CAST'),
            ]
        )
        db.flush()
        db.add_all(
            [
                AttendanceSchedule(employee_id=1, business_date=date(2026, 6, 1), shift_config_id=1, workshop_id=1, source='manual', is_rest_day=False),
                AttendanceSchedule(employee_id=2, business_date=date(2026, 6, 1), shift_config_id=1, workshop_id=2, source='manual', is_rest_day=False),
                WorkOrderEntry(
                    id=1,
                    work_order_id=1,
                    workshop_id=1,
                    shift_id=1,
                    business_date=date(2026, 6, 1),
                    output_weight=1200,
                    energy_kwh=12,
                    entry_status='submitted',
                    entry_type='mobile_coil',
                ),
            ]
        )
        db.commit()

        payload = daily_overview_builder._build_shift_breakdown(db, date(2026, 6, 1))

    by_code = {item['shift_code']: item for item in payload['shifts']}
    assert by_code['A']['shift_name'] == '长白班'
    assert by_code['A']['reported_workshops'] == 1
    assert by_code['A']['expected_workshops'] == 1
