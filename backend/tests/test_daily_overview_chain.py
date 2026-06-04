from __future__ import annotations

from datetime import date
from datetime import time
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.attendance import AttendanceSchedule
from app.models.consumable import DailyConsumableLog
from app.models.master import Employee, Workshop
from app.models.mes import MesCoilSnapshot, MesDailyWipSnapshot
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
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
            'basis': 'storage_inbound_output',
            'basis_label': '全厂入库产量',
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
    assert payload['plant_output']['basis_label'] == '全厂入库产量'
    assert payload['plant_cost']['basis_weight'] == 18.5
    assert payload['plant_cost']['cost_per_ton'] == round(2.08 * 10000 / 18.5, 0)
    assert payload['shift_breakdown']['output_basis_label'] == '工序下机量'
    assert payload['header_kpis'][0]['label'] == '全厂入库产量'


def test_owner_storage_inbound_supports_current_inventory_fields() -> None:
    assert daily_overview_builder._owner_storage_inbound_tons({
        'park_inbound_daily': 12.5,
        'new_plant_inbound_daily': 6.0,
    }) == 18.5
    assert daily_overview_builder._owner_storage_inbound_tons({
        'storage_inbound_weight': 7.2,
        'park_inbound_daily': 12.5,
    }) == 7.2


def test_plant_output_prefers_packaging_inbound_from_final_packaging_workshops(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'daily-overview-packaging-output.db'}", future=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False, future=True)()
    db.add_all([
        Workshop(id=1, code='JZ', name='精整车间', workshop_type='finishing', is_active=True),
        Workshop(id=2, code='LJ', name='拉矫车间', workshop_type='straightening', is_active=True),
        Workshop(id=3, code='JQ', name='园区剪切车间', workshop_type='shearing', is_active=True),
        Workshop(id=4, code='ZXTF-N', name='新厂在线退火', workshop_type='annealing', is_active=True),
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
    ])
    db.commit()

    totals = daily_overview_builder._query_plant_output_totals_by_date(
        db,
        date(2026, 6, 4),
        date(2026, 6, 4),
    )

    assert totals == {date(2026, 6, 4): 18.5}


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


def test_build_plant_output_uses_storage_inbound_totals(monkeypatch) -> None:
    monkeypatch.setattr(
        daily_overview_builder,
        '_query_plant_output_totals_by_date',
        lambda *_args, **_kwargs: {
            date(2026, 5, 28): 0.8,
            date(2026, 5, 29): 2.0,
        },
    )
    energy = {
        'total_electricity': 400.0,
        'total_gas': 0.0,
        'electricity_cost': 0.26,
        'gas_cost': 0.0,
        'total_cost': 0.26,
        'by_workshop': [],
    }

    payload = daily_overview_builder._build_plant_output(None, date(2026, 5, 29), energy)

    assert payload['daily_output'] == 2.0
    assert payload['yesterday_output'] == 0.8
    assert payload['monthly_output'] == 2.8
    assert payload['basis'] == 'storage_inbound_output'
    assert payload['basis_label'] == '全厂入库产量'


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


def test_build_timeseries_uses_storage_inbound_plant_output(monkeypatch) -> None:
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


def test_factory_dashboard_runtime_output_prefers_storage_inbound_totals(monkeypatch) -> None:
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
