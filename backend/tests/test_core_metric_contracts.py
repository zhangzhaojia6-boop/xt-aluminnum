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
        'workshop_output_daily': ('吨', 0.0),
        'finished_inbound_daily': ('吨', 20.0),
        'daily_input_weight': ('吨', 0.0),
        'wip_total': ('吨', 20.0),
        'total_electricity_kwh': ('kWh', 20.0),
        'total_gas_m3': ('m³', 0.0),
        'electricity_per_ton': ('kWh/吨', 0.2),
        'daily_yield_rate': ('%', 0.2),
        'cost_per_ton': ('元/吨', 0.0),
        'remaining_contract_weight': ('吨', 0.0),
        'monthly_total_output': ('吨', 0.0),
        'annual_total_output': ('吨', 0.0),
        'anomaly_explanation_daily': (None, 0.0),
        'dingtalk_specialist_evidence': (None, 0.0),
        'source_status': (None, 0.0),
        'daily_report_readiness': (None, 0.0),
    }
    expected_sources = {
        'total_output_daily': {
            'dingtalk_supplement',
            'root_owner_correction',
            'mes_packaging_output',
        },
        'workshop_output_daily': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'finished_inbound_daily': {
            'dingtalk_supplement',
            'root_owner_correction',
            'mes_stock_header_records',
            'mes_stock_records',
        },
        'daily_input_weight': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'wip_total': {
            'dingtalk_supplement',
            'root_owner_correction',
            'mes_coil_snapshot_business_date',
            'mes_daily_wip_snapshot',
            'mes_wip_total_snapshot',
        },
        'total_electricity_kwh': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'total_gas_m3': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'electricity_per_ton': {
            'dingtalk_supplement',
        },
        'daily_yield_rate': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'cost_per_ton': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'remaining_contract_weight': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'monthly_total_output': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'annual_total_output': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'anomaly_explanation_daily': {
            'dingtalk_supplement',
            'root_owner_correction',
        },
        'dingtalk_specialist_evidence': {
            'dingtalk_supplement',
        },
        'source_status': set(),
        'daily_report_readiness': set(),
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
    assert {
        'computed',
        'computed_same_basis',
        'owner_daily',
        'quality_yield_daily',
        'yield_projection',
        'mes_feeding_to_finished_inbound',
    }.isdisjoint(
        yield_contract.allowed_source_types
    )


_UNANCHORED_REVIEWER_SOURCE_PAIRS = (
    ('total_output_daily', 'mes_verified'),
    ('finished_inbound_daily', 'finished_inbound_output'),
    ('finished_inbound_daily', 'wms_direct'),
    ('wip_total', 'mes_wip_distribution'),
    ('total_electricity_kwh', 'data_hub_manual'),
    ('total_electricity_kwh', 'iot_energy'),
    ('total_electricity_kwh', 'owner_daily'),
    ('total_electricity_kwh', 'owner_or_energy_summary'),
    ('daily_yield_rate', 'computed_same_basis'),
    ('daily_yield_rate', 'owner_daily'),
    ('daily_yield_rate', 'quality_yield_daily'),
)


def test_every_confirmable_allowed_source_type_resolves_to_a_canonical_contract() -> None:
    unresolved = sorted(
        (field_name, source_type)
        for field_name, contract in metric_contracts.DAILY_REPORT_METRIC_CONTRACTS.items()
        if contract.confirmation_allowed
        for source_type in contract.allowed_source_types
        if metric_contracts.fact_source_contract_for(field_name, source_type) is None
    )

    assert unresolved == []


@pytest.mark.parametrize(('field_name', 'source_type'), _UNANCHORED_REVIEWER_SOURCE_PAIRS)
def test_unanchored_upstream_source_type_is_not_nominally_confirmable(
    field_name: str,
    source_type: str,
) -> None:
    contract = metric_contracts.daily_report_contract_for(field_name)

    assert source_type not in contract.allowed_source_types
    assert metric_contracts.fact_source_contract_for(field_name, source_type) is None


def test_allowed_source_types_are_derived_from_canonical_source_contracts() -> None:
    assert isinstance(metric_contracts.DailyReportMetricContract.allowed_source_types, property)


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


def test_all_20_question_metric_keys_have_canonical_fact_or_diagnostic_policy() -> None:
    from app.services.hermes_20_question_acceptance import build_20_question_catalog

    expected_value_kinds = {
        'total_output_daily': 'finite_number',
        'workshop_output_daily': 'numeric_mapping',
        'finished_inbound_daily': 'finite_number',
        'daily_input_weight': 'finite_number',
        'total_electricity_kwh': 'finite_number',
        'total_gas_m3': 'finite_number',
        'electricity_per_ton': 'finite_number',
        'daily_yield_rate': 'finite_number',
        'cost_per_ton': 'finite_number',
        'wip_total': 'finite_number',
        'remaining_contract_weight': 'finite_number',
        'monthly_total_output': 'finite_number',
        'annual_total_output': 'finite_number',
        'anomaly_explanation_daily': 'nonempty_text',
        'dingtalk_specialist_evidence': 'evidence_collection',
        'source_status': 'diagnostic_status',
        'daily_report_readiness': 'diagnostic_status',
    }
    catalog = build_20_question_catalog()
    catalog_fields = {field for question in catalog for field in question.metric_keys}

    assert len(catalog) == 20
    assert catalog_fields == set(expected_value_kinds)
    for field, value_kind in expected_value_kinds.items():
        contract = metric_contracts.daily_report_contract_for(field)
        assert contract.value_kind == value_kind
        assert contract.confirmation_allowed or contract.confirmed_failure_reason

    for question in catalog:
        for field in question.metric_keys:
            contract = metric_contracts.daily_report_contract_for(field)
            if contract.confirmation_allowed:
                assert contract.source_contracts or metric_contracts.fact_source_contract_for(
                    field,
                    next(iter(contract.allowed_source_types)),
                ) is not None
            else:
                assert question.status_hint in contract.allowed_non_confirmed_statuses


def test_diagnostic_metric_policies_are_explicit_and_non_confirmable() -> None:
    for field in ('source_status', 'daily_report_readiness'):
        contract = metric_contracts.daily_report_contract_for(field)
        assert contract.confirmation_allowed is False
        assert contract.unit is None
        assert contract.allowed_source_types == frozenset()
        assert contract.allowed_non_confirmed_statuses == frozenset(
            {'candidate', 'missing', 'conflict'}
        )
        assert contract.requires_non_confirmed_reason_action is True
        assert field in contract.confirmed_failure_reason


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
