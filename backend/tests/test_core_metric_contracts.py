from app.core.business_time import OWNER_DAILY_BUSINESS_DAY_START, PRODUCTION_BUSINESS_DAY_START
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

    assert contract['primary_source'] == 'mes_stock_records.net_weight_tons'
    assert 'mes_workshop_process_records.output_weight_tons' in contract['fallback_source']
    assert daily_overview_builder.PACKAGING_INBOUND_OUTPUT_FIELD not in contract['fallback_source']
    assert contract['business_date_basis'] == 'production_business_date'
    assert contract['aggregation_rule'] == 'sum_mes_stock_in_to_finished_goods_first'
    assert set(contract['final_workshop_codes']) == daily_overview_builder.FINAL_PACKAGING_WORKSHOP_CODES
    assert set(contract['final_mes_workshop_names']) == daily_overview_builder.FINAL_PACKAGING_MES_WORKSHOP_NAMES


def test_yield_contract_matches_formal_yield_map() -> None:
    contract = CORE_METRIC_CONTRACTS['formal_yield_rate']
    deprecation_map = build_yield_rate_deprecation_map()

    assert contract['primary_source'] == deprecation_map['formal_truth']
    assert contract['aggregation_rule'] == 'formal_matrix_first_runtime_detail_compat'


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
