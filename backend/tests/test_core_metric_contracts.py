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
        'electricity_per_ton': ('kWh/吨', 0.2),
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
        'electricity_per_ton': {
            'dingtalk_supplement',
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


def test_fact_source_contracts_reuse_projection_truth_and_control_identity_pairs() -> None:
    contract_lookup = getattr(metric_contracts, 'fact_source_contract_for', None)
    failure_reason = getattr(metric_contracts, 'fact_source_failure_reason', None)

    assert callable(contract_lookup)
    assert callable(failure_reason)

    from app.services.report.daily_fact_evidence_contracts import (
        PROJECTION_FACT_CONTRACTS,
        PROJECTION_METRIC_CONTRACT_VERSION,
        SOURCE_TABLE_BY_TYPE,
    )

    projection = PROJECTION_FACT_CONTRACTS['total_output_daily']
    assert metric_contracts.DAILY_REPORT_METRIC_CONTRACT_VERSION == PROJECTION_METRIC_CONTRACT_VERSION
    source_contract = contract_lookup('total_output_daily', 'mes_packaging_output')
    assert source_contract is not None
    assert source_contract.source_ref_identity == projection.source_ref
    assert source_contract.source_keys == frozenset({'mes_readonly', 'data_hub_projection'})

    valid_ref = {
        'source_ref': projection.source_ref,
        'source_table': SOURCE_TABLE_BY_TYPE['mes_packaging_output'],
        'business_window': '2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00',
        'unit': projection.expected_unit,
        'metric_contract_version': projection.metric_contract_version,
        'row_count': 2,
        'latest_row_id': 41,
        'trace_id': f'projection-read:{projection.source_ref}:41:2',
    }
    assert failure_reason(
        'total_output_daily',
        source_key='mes_readonly',
        source_type='mes_packaging_output',
        source_ref=valid_ref,
        trace_id=valid_ref['trace_id'],
    ) is None
    assert 'source_key' in failure_reason(
        'total_output_daily',
        source_key='invented_anything',
        source_type='mes_packaging_output',
        source_ref=valid_ref,
        trace_id=valid_ref['trace_id'],
    )
    assert 'source_ref' in failure_reason(
        'total_output_daily',
        source_key='mes_readonly',
        source_type='mes_packaging_output',
        source_ref={**valid_ref, 'source_ref': 'totally_fake_ref'},
        trace_id=valid_ref['trace_id'],
    )
    assert 'source_ref' in failure_reason(
        'total_output_daily',
        source_key='mes_readonly',
        source_type='mes_packaging_output',
        source_ref={**valid_ref, 'source_table': 'totally_fake_table'},
        trace_id=valid_ref['trace_id'],
    )
    assert 'trace_id' in failure_reason(
        'total_output_daily',
        source_key='mes_readonly',
        source_type='mes_packaging_output',
        source_ref={**valid_ref, 'latest_row_id': 42},
        trace_id=valid_ref['trace_id'],
    )


def test_dingtalk_fact_source_contract_requires_persisted_evidence_anchor() -> None:
    failure_reason = getattr(metric_contracts, 'fact_source_failure_reason', None)
    assert callable(failure_reason)

    valid_ref = {
        'source_key': 'dingtalk_group_content',
        'evidence_id': 17,
        'trace_id': 'dingtalk-evidence-trace-17',
        'business_date': '2026-06-27',
    }
    assert failure_reason(
        'total_electricity_kwh',
        source_key='dingtalk_group_content',
        source_type='dingtalk_supplement',
        source_ref=valid_ref,
        trace_id='dingtalk-evidence-trace-17',
    ) is None
    assert 'source_ref' in failure_reason(
        'total_electricity_kwh',
        source_key='dingtalk_group_content',
        source_type='dingtalk_supplement',
        source_ref={'source_key': 'dingtalk_group_content', 'trace_id': 'trace-only'},
        trace_id='trace-only',
    )
    assert 'source_key' in failure_reason(
        'total_electricity_kwh',
        source_key='dingtalk_group_file',
        source_type='dingtalk_supplement',
        source_ref=valid_ref,
        trace_id='dingtalk-evidence-trace-17',
    )


def test_electricity_per_ton_contract_requires_persisted_numerator_and_denominator() -> None:
    contract = metric_contracts.daily_report_contract_for('electricity_per_ton')
    assert contract.unit == 'kWh/吨'
    assert contract.requires_same_business_window is True

    valid_ref = {
        'source_key': 'dingtalk_group_content',
        'evidence_id': 31,
        'trace_id': 'dingtalk-evidence-trace-31',
        'business_date': '2026-06-27',
        'numerator_field': 'total_electricity_kwh',
        'numerator_evidence_id': 31,
        'denominator_field': 'total_output_daily',
        'denominator_evidence_id': 32,
    }
    assert metric_contracts.fact_source_failure_reason(
        'electricity_per_ton',
        source_key='dingtalk_group_content',
        source_type='dingtalk_supplement',
        source_ref=valid_ref,
        trace_id=valid_ref['trace_id'],
    ) is None

    for key in ('numerator_evidence_id', 'denominator_evidence_id'):
        invalid_ref = {**valid_ref, key: None}
        assert key in metric_contracts.fact_source_failure_reason(
            'electricity_per_ton',
            source_key='dingtalk_group_content',
            source_type='dingtalk_supplement',
            source_ref=invalid_ref,
            trace_id=valid_ref['trace_id'],
        )

    invalid_basis = {**valid_ref, 'denominator_field': 'finished_inbound_daily'}
    assert 'denominator_field' in metric_contracts.fact_source_failure_reason(
        'electricity_per_ton',
        source_key='dingtalk_group_content',
        source_type='dingtalk_supplement',
        source_ref=invalid_basis,
        trace_id=valid_ref['trace_id'],
    )


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
