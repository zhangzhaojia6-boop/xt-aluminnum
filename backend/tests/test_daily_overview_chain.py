from __future__ import annotations

from datetime import date

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
