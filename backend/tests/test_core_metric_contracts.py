from dataclasses import FrozenInstanceError

import pytest

from app.core.business_time import OWNER_DAILY_BUSINESS_DAY_START, PRODUCTION_BUSINESS_DAY_START
from app.domain import metric_contracts
from app.domain.metric_contracts import CORE_METRIC_CONTRACTS
from app.services.report import daily_overview_builder
from app.services.yield_rate_deprecation_map_service import build_yield_rate_deprecation_map


def test_core_metric_contracts_cover_business_blockers() -> None:
    required = {
        'factory_total_output_tons',
        'machine_energy_kwh',
        'formal_yield_rate',
        'production_business_date',
        'owner_daily_business_date',
        'mes_wip_coils',
    }

    assert required.issubset(CORE_METRIC_CONTRACTS)
    assert len(CORE_METRIC_CONTRACTS) == len({item['id'] for item in CORE_METRIC_CONTRACTS.values()})

    for metric_id, contract in CORE_METRIC_CONTRACTS.items():
        assert contract['id'] == metric_id
        assert contract['unit']
        assert contract['primary_source']
        assert contract['business_date_basis']
        assert contract['aggregation_rule']
        assert contract['test_anchor']


def test_business_time_contract_matches_runtime_constants() -> None:
    assert CORE_METRIC_CONTRACTS['production_business_date']['start_time'] == PRODUCTION_BUSINESS_DAY_START.strftime('%H:%M')
    assert CORE_METRIC_CONTRACTS['owner_daily_business_date']['start_time'] == OWNER_DAILY_BUSINESS_DAY_START.strftime('%H:%M')


def test_energy_contract_keeps_machine_detail_as_authoritative_source() -> None:
    contract = CORE_METRIC_CONTRACTS['machine_energy_kwh']

    assert contract['primary_source'] == 'machine_energy_records.energy_kwh'
    assert 'shift_report.energy_kwh' in contract['fallback_source']
    assert contract['aggregation_rule'] == 'sum_machine_detail_first'


def test_factory_output_contract_matches_mes_packaging_basis() -> None:
    contract = CORE_METRIC_CONTRACTS['factory_total_output_tons']

    assert contract['primary_source'] == 'mes_workshop_process_records.output_weight_tons'
    assert 'stock' not in contract['primary_source']
    assert 'stock' not in contract['fallback_source']
    assert contract['business_date_basis'] == 'production_business_date'
    assert contract['aggregation_rule'] == 'sum_mes_packaging_process_output'
    assert set(contract['final_workshop_codes']) == daily_overview_builder.FINAL_PACKAGING_WORKSHOP_CODES
    assert set(contract['final_mes_workshop_names']) == daily_overview_builder.FINAL_PACKAGING_MES_WORKSHOP_NAMES


def test_yield_contract_matches_formal_yield_map() -> None:
    contract = CORE_METRIC_CONTRACTS['formal_yield_rate']
    deprecation_map = build_yield_rate_deprecation_map()

    assert contract['primary_source'] == deprecation_map['formal_truth']
    assert contract['fallback_source'] == ''
    assert 'runtime' not in contract['aggregation_rule']


def test_daily_report_metric_contracts_lock_units_tolerances_and_sources() -> None:
    daily_report_contract_for = metric_contracts.daily_report_contract_for
    daily_report_tolerance_for = metric_contracts.daily_report_tolerance_for
    expected = {
        'total_output_daily': ('吨', 20.0),
        'finished_inbound_daily': ('吨', 20.0),
        'wip_total': ('吨', 20.0),
        'total_electricity_kwh': ('kWh', 20.0),
        'daily_yield_rate': ('%', 0.2),
    }
    expected_sources = {
        'total_output_daily': {
            'dingtalk_supplement',
            'root_owner_correction',
            'mes_packaging_output',
            'mes_verified',
        },
        'finished_inbound_daily': {
            'dingtalk_supplement',
            'root_owner_correction',
            'finished_inbound_output',
            'wms_direct',
            'mes_stock_header_records',
            'mes_stock_records',
        },
        'wip_total': {
            'dingtalk_supplement',
            'root_owner_correction',
            'mes_wip_distribution',
            'mes_coil_snapshot_business_date',
            'mes_daily_wip_snapshot',
            'mes_wip_total_snapshot',
        },
        'total_electricity_kwh': {
            'dingtalk_supplement',
            'root_owner_correction',
            'iot_energy',
            'owner_daily',
            'owner_or_energy_summary',
            'data_hub_manual',
        },
        'daily_yield_rate': {
            'dingtalk_supplement',
            'root_owner_correction',
            'owner_daily',
            'quality_yield_daily',
            'computed_same_basis',
        },
    }

    assert set(metric_contracts.DAILY_REPORT_METRIC_CONTRACTS) == set(expected)
    for field, (unit, tolerance) in expected.items():
        contract = daily_report_contract_for(field)
        assert contract.unit == unit
        assert contract.tolerance == tolerance
        assert isinstance(contract.allowed_source_types, frozenset)
        assert contract.allowed_source_types == frozenset(expected_sources[field])
        assert daily_report_tolerance_for(field) == tolerance

    assert all(
        'dingtalk_confirmed' not in contract.allowed_source_types
        for contract in metric_contracts.DAILY_REPORT_METRIC_CONTRACTS.values()
    )


def test_daily_report_metric_contracts_prohibit_cross_metric_and_derived_sources() -> None:
    daily_report_contract_for = metric_contracts.daily_report_contract_for
    assert 'finished_inbound_output' not in daily_report_contract_for('total_output_daily').allowed_source_types
    assert 'mes_stock_header_records' not in daily_report_contract_for('total_output_daily').allowed_source_types
    assert 'mes_stock_header_records' in daily_report_contract_for('finished_inbound_daily').allowed_source_types
    assert 'mes_stock_records' in daily_report_contract_for('finished_inbound_daily').allowed_source_types
    assert {
        'mes_coil_snapshot_business_date',
        'mes_daily_wip_snapshot',
    }.issubset(daily_report_contract_for('wip_total').allowed_source_types)

    yield_contract = daily_report_contract_for('daily_yield_rate')
    assert yield_contract.requires_same_business_window is True
    assert 'computed_same_basis' in yield_contract.allowed_source_types
    assert {'computed', 'yield_projection', 'mes_feeding_to_finished_inbound'}.isdisjoint(
        yield_contract.allowed_source_types
    )


def test_daily_report_metric_contract_is_immutable() -> None:
    contract = metric_contracts.daily_report_contract_for('daily_yield_rate')

    with pytest.raises(FrozenInstanceError):
        contract.tolerance = 20.0


def test_daily_report_metric_contract_unknown_field_behavior() -> None:
    with pytest.raises(KeyError):
        metric_contracts.daily_report_contract_for('unknown_metric')

    assert metric_contracts.daily_report_tolerance_for('unknown_metric') == 0.0


def test_mes_wip_contract_uses_business_date_and_active_coil_filters() -> None:
    contract = CORE_METRIC_CONTRACTS['mes_wip_coils']

    assert contract['primary_source'] == 'mes_coil_snapshots'
    assert contract['business_date_basis'] == 'production_business_date'
    assert contract['required_filters'] == [
        'business_date',
        'delivery_date_is_null',
        'allocation_date_is_null',
        'not_finished_stock',
        'has_current_or_next_process',
    ]
