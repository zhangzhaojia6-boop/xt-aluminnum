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
            'basis': 'latest_mobile_coil_output',
            'basis_label': '全厂成品产量',
            'energy_per_ton': 172.97,
        },
    )
    monkeypatch.setattr(
        daily_overview_builder,
        '_build_shift_breakdown',
        lambda *_args, **_kwargs: {
            'business_date': '2026-05-29',
            'total_output': 18.5,
            'output_basis': 'latest_mobile_coil_output',
            'output_basis_label': '全厂成品产量',
            'energy_per_ton': 172.97,
            'shifts': [],
        },
    )

    payload = daily_overview_builder.build_daily_production_overview(None, target_date=date(2026, 5, 29))

    assert payload['plant_output']['daily_output'] == 18.5
    assert payload['plant_output']['basis_label'] == '全厂成品产量'
    assert payload['plant_cost']['basis_weight'] == 18.5
    assert payload['plant_cost']['cost_per_ton'] == round(2.08 * 10000 / 18.5, 0)
    assert payload['shift_breakdown']['output_basis_label'] == '全厂成品产量'


def test_build_plant_output_uses_latest_mobile_coil_entry_per_work_order(monkeypatch) -> None:
    class _FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return self._rows

    class _FakeDB:
        def __init__(self, rows):
            self._rows = rows

        def query(self, *_args, **_kwargs):
            return _FakeQuery(self._rows)

    rows = [
        type('Row', (), {
            'id': 1,
            'work_order_id': 11,
            'business_date': date(2026, 5, 29),
            'output_weight': 1200.0,
            'entry_status': 'submitted',
            'entry_type': 'mobile_coil',
            'approved_at': None,
            'verified_at': None,
            'submitted_at': None,
            'updated_at': None,
            'created_at': None,
        })(),
        type('Row', (), {
            'id': 2,
            'work_order_id': 11,
            'business_date': date(2026, 5, 29),
            'output_weight': 1500.0,
            'entry_status': 'submitted',
            'entry_type': 'mobile_coil',
            'approved_at': None,
            'verified_at': None,
            'submitted_at': None,
            'updated_at': None,
            'created_at': None,
        })(),
        type('Row', (), {
            'id': 3,
            'work_order_id': 12,
            'business_date': date(2026, 5, 29),
            'output_weight': 500.0,
            'entry_status': 'approved',
            'entry_type': 'mobile_coil',
            'approved_at': None,
            'verified_at': None,
            'submitted_at': None,
            'updated_at': None,
            'created_at': None,
        })(),
        type('Row', (), {
            'id': 4,
            'work_order_id': 12,
            'business_date': date(2026, 5, 28),
            'output_weight': 800.0,
            'entry_status': 'approved',
            'entry_type': 'mobile_coil',
            'approved_at': None,
            'verified_at': None,
            'submitted_at': None,
            'updated_at': None,
            'created_at': None,
        })(),
    ]
    energy = {
        'total_electricity': 400.0,
        'total_gas': 0.0,
        'electricity_cost': 0.26,
        'gas_cost': 0.0,
        'total_cost': 0.26,
        'by_workshop': [],
    }

    payload = daily_overview_builder._build_plant_output(_FakeDB(rows), date(2026, 5, 29), energy)

    assert payload['daily_output'] == 2.0
    assert payload['yesterday_output'] == 0.8
    assert payload['monthly_output'] == 2.8
    assert payload['basis'] == 'latest_mobile_coil_output'
    assert payload['basis_label'] == '全厂成品产量'


def test_build_timeseries_uses_mobile_coil_plant_output(monkeypatch) -> None:
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
