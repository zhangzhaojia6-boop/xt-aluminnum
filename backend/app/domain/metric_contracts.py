from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.core.business_time import OWNER_DAILY_BUSINESS_DAY_START, PRODUCTION_BUSINESS_DAY_START


DAILY_REPORT_METRIC_CONTRACT_VERSION = '2026-07-11'


CORE_METRIC_CONTRACTS: dict[str, dict[str, Any]] = {
    'factory_total_output_tons': {
        'id': 'factory_total_output_tons',
        'label': '全厂总产量',
        'unit': 't',
        'primary_source': 'mes_workshop_process_records.output_weight_tons',
        'fallback_source': 'manual owner daily values are comparison only',
        'business_date_basis': 'production_business_date',
        'aggregation_rule': 'sum_mes_packaging_process_output',
        'final_workshop_codes': ['JQ', 'JZ', 'LJ'],
        'final_mes_workshop_names': ['精整', '精整车间', '拉矫', '拉矫车间', '园区精整', '园区剪切', '园区剪切车间', '剪切车间'],
        'test_anchor': 'backend/tests/test_core_metric_contracts.py',
    },
    'machine_energy_kwh': {
        'id': 'machine_energy_kwh',
        'label': '机台用电',
        'unit': 'kWh',
        'primary_source': 'machine_energy_records.energy_kwh',
        'fallback_source': 'shift_report.energy_kwh when machine detail is absent',
        'business_date_basis': 'production_business_date',
        'aggregation_rule': 'sum_machine_detail_first',
        'test_anchor': 'backend/tests/test_core_metric_contracts.py',
    },
    'formal_yield_rate': {
        'id': 'formal_yield_rate',
        'label': '正式成品率',
        'unit': 'ratio',
        'primary_source': 'yield_matrix_lane',
        'fallback_source': '',
        'business_date_basis': 'production_business_date',
        'aggregation_rule': 'formal_independent_source_only',
        'test_anchor': 'backend/tests/test_core_metric_contracts.py',
    },
    'production_business_date': {
        'id': 'production_business_date',
        'label': '主操、电工业务日',
        'unit': 'date',
        'primary_source': 'app.core.business_time.resolve_production_business_date',
        'fallback_source': '',
        'business_date_basis': 'local_time',
        'aggregation_rule': 'start_time_24h_window',
        'start_time': PRODUCTION_BUSINESS_DAY_START.strftime('%H:%M'),
        'test_anchor': 'backend/tests/test_core_metric_contracts.py',
    },
    'owner_daily_business_date': {
        'id': 'owner_daily_business_date',
        'label': '内勤业务日',
        'unit': 'date',
        'primary_source': 'app.core.business_time.resolve_owner_daily_business_date',
        'fallback_source': '',
        'business_date_basis': 'local_time',
        'aggregation_rule': 'start_time_24h_window',
        'start_time': OWNER_DAILY_BUSINESS_DAY_START.strftime('%H:%M'),
        'test_anchor': 'backend/tests/test_core_metric_contracts.py',
    },
    'mes_wip_coils': {
        'id': 'mes_wip_coils',
        'label': '外部在制卷',
        'unit': 'coil',
        'primary_source': 'mes_coil_snapshots',
        'fallback_source': '',
        'business_date_basis': 'production_business_date',
        'aggregation_rule': 'count_active_coils_by_workshop_and_process',
        'required_filters': [
            'business_date',
            'delivery_date_is_null',
            'allocation_date_is_null',
            'not_finished_stock',
            'has_current_or_next_process',
        ],
        'test_anchor': 'backend/tests/test_core_metric_contracts.py',
    },
}


@dataclass(frozen=True)
class FactSourceContract:
    source_type: str
    source_keys: frozenset[str]
    required_ref_fields: frozenset[str]
    source_ref_identity: str | None = None
    source_ref_identity_field: str = 'source_ref'
    source_key_ref_field: str | None = None
    positive_integer_ref_fields: frozenset[str] = frozenset()
    required_ref_values: tuple[tuple[str, str], ...] = ()
    trace_id_prefix: str | None = None


@dataclass(frozen=True)
class DailyReportMetricContract:
    unit: str
    tolerance: float
    allowed_source_types: frozenset[str]
    requires_same_business_window: bool = False
    source_contracts: tuple[FactSourceContract, ...] = ()
    metric_contract_version: str = DAILY_REPORT_METRIC_CONTRACT_VERSION


def _dingtalk_source_contract() -> FactSourceContract:
    return FactSourceContract(
        source_type='dingtalk_supplement',
        source_keys=frozenset({'dingtalk_group_content', 'dingtalk_group_file'}),
        required_ref_fields=frozenset(
            {'source_key', 'evidence_id', 'trace_id', 'business_date'}
        ),
        source_key_ref_field='source_key',
        positive_integer_ref_fields=frozenset({'evidence_id'}),
    )


def _root_owner_correction_source_contract() -> FactSourceContract:
    return FactSourceContract(
        source_type='root_owner_correction',
        source_keys=frozenset({'data_hub_projection'}),
        required_ref_fields=frozenset(
            {'source', 'correction_id', 'trace_id', 'business_date'}
        ),
        source_ref_identity='root_owner_correction',
        source_ref_identity_field='source',
        positive_integer_ref_fields=frozenset({'correction_id'}),
    )


def _electricity_per_ton_source_contract() -> FactSourceContract:
    return FactSourceContract(
        source_type='dingtalk_supplement',
        source_keys=frozenset({'dingtalk_group_content', 'dingtalk_group_file'}),
        required_ref_fields=frozenset({
            'source_key',
            'evidence_id',
            'trace_id',
            'business_date',
            'numerator_field',
            'numerator_evidence_id',
            'denominator_field',
            'denominator_evidence_id',
        }),
        source_key_ref_field='source_key',
        positive_integer_ref_fields=frozenset({
            'evidence_id',
            'numerator_evidence_id',
            'denominator_evidence_id',
        }),
        required_ref_values=(
            ('numerator_field', 'total_electricity_kwh'),
            ('denominator_field', 'total_output_daily'),
        ),
    )


def _projection_source_contracts(field_name: str) -> tuple[FactSourceContract, ...]:
    # Imported lazily because the projection service consumes this domain module.
    from app.services.report.daily_fact_evidence_contracts import (
        PROJECTION_FACT_CONTRACTS,
        SOURCE_TABLE_BY_TYPE,
        WIP_PROJECTION_FACT_CONTRACTS,
    )

    projection_contracts = []
    direct_contract = PROJECTION_FACT_CONTRACTS.get(field_name)
    if direct_contract is not None:
        projection_contracts.append(direct_contract)
    projection_contracts.extend(
        contract
        for (contract_field, _), contract in WIP_PROJECTION_FACT_CONTRACTS.items()
        if contract_field == field_name
    )
    result: list[FactSourceContract] = []
    for projection_contract in projection_contracts:
        for source_type in sorted(projection_contract.source_types):
            source_table = SOURCE_TABLE_BY_TYPE.get(source_type)
            required_ref_fields = {
                'source_ref',
                'business_window',
                'unit',
                'metric_contract_version',
                'row_count',
                'latest_row_id',
                'trace_id',
            }
            required_ref_values = [
                ('unit', projection_contract.expected_unit),
                ('metric_contract_version', projection_contract.metric_contract_version),
            ]
            if source_table is not None:
                required_ref_fields.add('source_table')
                required_ref_values.append(('source_table', source_table))
            result.append(
                FactSourceContract(
                    source_type=source_type,
                    source_keys=frozenset({'mes_readonly', 'data_hub_projection'}),
                    required_ref_fields=frozenset(required_ref_fields),
                    source_ref_identity=projection_contract.source_ref,
                    positive_integer_ref_fields=frozenset({'row_count', 'latest_row_id'}),
                    required_ref_values=tuple(required_ref_values),
                    trace_id_prefix=f'projection-read:{projection_contract.source_ref}:',
                )
            )
    return tuple(result)


def _confirmable_source_contracts() -> tuple[FactSourceContract, ...]:
    return (
        _dingtalk_source_contract(),
        _root_owner_correction_source_contract(),
    )


DAILY_REPORT_METRIC_CONTRACTS: dict[str, DailyReportMetricContract] = {
    'total_output_daily': DailyReportMetricContract(
        unit='吨',
        tolerance=20.0,
        allowed_source_types=frozenset({
            'dingtalk_supplement',
            'root_owner_correction',
            'mes_packaging_output',
            'mes_verified',
        }),
        source_contracts=_confirmable_source_contracts(),
    ),
    'finished_inbound_daily': DailyReportMetricContract(
        unit='吨',
        tolerance=20.0,
        allowed_source_types=frozenset({
            'dingtalk_supplement',
            'root_owner_correction',
            'finished_inbound_output',
            'wms_direct',
            'mes_stock_header_records',
            'mes_stock_records',
        }),
        source_contracts=_confirmable_source_contracts(),
    ),
    'wip_total': DailyReportMetricContract(
        unit='吨',
        tolerance=20.0,
        allowed_source_types=frozenset({
            'dingtalk_supplement',
            'root_owner_correction',
            'mes_wip_distribution',
            'mes_coil_snapshot_business_date',
            'mes_daily_wip_snapshot',
            'mes_wip_total_snapshot',
        }),
        source_contracts=_confirmable_source_contracts(),
    ),
    'total_electricity_kwh': DailyReportMetricContract(
        unit='kWh',
        tolerance=20.0,
        allowed_source_types=frozenset({
            'dingtalk_supplement',
            'root_owner_correction',
            'iot_energy',
            'owner_daily',
            'owner_or_energy_summary',
            'data_hub_manual',
        }),
        source_contracts=_confirmable_source_contracts(),
    ),
    'electricity_per_ton': DailyReportMetricContract(
        unit='kWh/吨',
        tolerance=0.2,
        allowed_source_types=frozenset({'dingtalk_supplement'}),
        requires_same_business_window=True,
        source_contracts=(_electricity_per_ton_source_contract(),),
    ),
    'daily_yield_rate': DailyReportMetricContract(
        unit='%',
        tolerance=0.2,
        allowed_source_types=frozenset({
            'dingtalk_supplement',
            'root_owner_correction',
            'owner_daily',
            'quality_yield_daily',
            'computed_same_basis',
        }),
        requires_same_business_window=True,
        source_contracts=_confirmable_source_contracts(),
    ),
}


def daily_report_contract_for(field: str) -> DailyReportMetricContract:
    return DAILY_REPORT_METRIC_CONTRACTS[field]


def daily_report_tolerance_for(field: str) -> float:
    contract = DAILY_REPORT_METRIC_CONTRACTS.get(field)
    return contract.tolerance if contract is not None else 0.0


def fact_source_contract_for(
    field_name: str,
    source_type: str,
) -> FactSourceContract | None:
    metric_contract = DAILY_REPORT_METRIC_CONTRACTS.get(field_name)
    if metric_contract is None:
        return None
    source_contract = next(
        (
            source_contract
            for source_contract in metric_contract.source_contracts
            if source_contract.source_type == source_type
        ),
        None,
    )
    if source_contract is not None:
        return source_contract
    return next(
        (
            source_contract
            for source_contract in _projection_source_contracts(field_name)
            if source_contract.source_type == source_type
        ),
        None,
    )


def fact_source_failure_reason(
    field_name: str,
    *,
    source_key: str,
    source_type: str,
    source_ref: Any,
    trace_id: str,
    business_date: str | None = None,
    business_window: str | None = None,
    unit: str | None = None,
    metric_contract_version: str | None = None,
) -> str | None:
    source_contract = fact_source_contract_for(field_name, source_type)
    if source_contract is None:
        return 'source_type_missing_or_not_confirmable'
    if source_key not in source_contract.source_keys:
        return 'source_key_contract_mismatch'
    if not isinstance(source_ref, Mapping):
        return 'source_ref_mapping_required'
    for field in source_contract.required_ref_fields:
        if source_ref.get(field) in (None, ''):
            return f'source_ref_{field}_missing'
    if source_contract.source_ref_identity is not None:
        actual_identity = str(
            source_ref.get(source_contract.source_ref_identity_field) or ''
        ).strip()
        if actual_identity != source_contract.source_ref_identity:
            return 'source_ref_identity_mismatch'
    if source_contract.source_key_ref_field is not None:
        ref_source_key = str(source_ref.get(source_contract.source_key_ref_field) or '').strip()
        if ref_source_key != source_key:
            return 'source_key_ref_mismatch'
    for field in source_contract.positive_integer_ref_fields:
        try:
            positive_value = int(source_ref.get(field))
        except (TypeError, ValueError):
            return f'source_ref_{field}_invalid'
        if positive_value <= 0:
            return f'source_ref_{field}_invalid'
    for field, expected_value in source_contract.required_ref_values:
        actual_value = str(source_ref.get(field) or '').strip()
        if actual_value != expected_value:
            return f'source_ref_{field}_mismatch'
    fact_metadata = {
        'business_date': business_date,
        'business_window': business_window,
        'unit': unit,
        'metric_contract_version': metric_contract_version,
    }
    for field, expected_value in fact_metadata.items():
        if field not in source_ref or expected_value in (None, ''):
            continue
        if str(source_ref.get(field) or '').strip() != str(expected_value).strip():
            return f'source_ref_{field}_mismatch'
    ref_trace_id = str(source_ref.get('trace_id') or '').strip()
    if ref_trace_id != trace_id:
        return 'source_ref_trace_id_mismatch'
    if source_contract.trace_id_prefix is not None:
        expected_trace_id = (
            f'{source_contract.trace_id_prefix}'
            f'{source_ref.get("latest_row_id")}:{source_ref.get("row_count")}'
        )
        if ref_trace_id != expected_trace_id:
            return 'source_ref_trace_id_contract_mismatch'
    return None
