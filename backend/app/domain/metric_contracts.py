from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Mapping

from app.core.business_time import OWNER_DAILY_BUSINESS_DAY_START, PRODUCTION_BUSINESS_DAY_START


DAILY_REPORT_METRIC_CONTRACT_VERSION = '2026-07-11'

_UNIT_ALIASES = {
    '吨': frozenset({'吨', 't', 'ton', 'tons'}),
    'kwh': frozenset({'kwh', '度', '千瓦时'}),
    '%': frozenset({'%', 'percent', 'percentage', '百分点'}),
    'm³': frozenset({'m³', 'm3', '立方米'}),
    'kwh/吨': frozenset({'kwh/吨', 'kwh/t', '度/吨', '千瓦时/吨'}),
    '元/吨': frozenset({'元/吨', '元/t', 'yuan/ton'}),
}


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
    unit: str | None
    tolerance: float
    value_kind: str = 'finite_number'
    confirmation_allowed: bool = True
    allowed_non_confirmed_statuses: frozenset[str] = frozenset({'missing', 'conflict'})
    requires_non_confirmed_reason_action: bool = True
    confirmed_failure_reason: str | None = None
    requires_same_business_window: bool = False
    source_contracts: tuple[FactSourceContract, ...] = ()
    metric_contract_version: str = DAILY_REPORT_METRIC_CONTRACT_VERSION
    field_name: str = ''

    @property
    def allowed_source_types(self) -> frozenset[str]:
        if not self.confirmation_allowed:
            return frozenset()
        return frozenset(
            contract.source_type
            for contract in _canonical_source_contracts(self.field_name, self)
        )


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


def _canonical_source_contracts(
    field_name: str,
    metric_contract: DailyReportMetricContract,
) -> tuple[FactSourceContract, ...]:
    return metric_contract.source_contracts + _projection_source_contracts(field_name)


def _confirmable_source_contracts() -> tuple[FactSourceContract, ...]:
    return (
        _dingtalk_source_contract(),
        _root_owner_correction_source_contract(),
    )


def _bind_metric_contracts(
    contracts: Mapping[str, DailyReportMetricContract],
) -> dict[str, DailyReportMetricContract]:
    return {
        field_name: replace(contract, field_name=field_name)
        for field_name, contract in contracts.items()
    }


DAILY_REPORT_METRIC_CONTRACTS: dict[str, DailyReportMetricContract] = _bind_metric_contracts({
    'total_output_daily': DailyReportMetricContract(
        unit='吨',
        tolerance=20.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'workshop_output_daily': DailyReportMetricContract(
        unit='吨',
        tolerance=0.0,
        value_kind='numeric_mapping',
        source_contracts=_confirmable_source_contracts(),
    ),
    'finished_inbound_daily': DailyReportMetricContract(
        unit='吨',
        tolerance=20.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'daily_input_weight': DailyReportMetricContract(
        unit='吨',
        tolerance=0.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'wip_total': DailyReportMetricContract(
        unit='吨',
        tolerance=20.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'total_electricity_kwh': DailyReportMetricContract(
        unit='kWh',
        tolerance=20.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'total_gas_m3': DailyReportMetricContract(
        unit='m³',
        tolerance=0.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'electricity_per_ton': DailyReportMetricContract(
        unit='kWh/吨',
        tolerance=0.2,
        requires_same_business_window=True,
        source_contracts=(_electricity_per_ton_source_contract(),),
    ),
    'daily_yield_rate': DailyReportMetricContract(
        unit='%',
        tolerance=0.2,
        requires_same_business_window=True,
        source_contracts=_confirmable_source_contracts(),
    ),
    'cost_per_ton': DailyReportMetricContract(
        unit='元/吨',
        tolerance=0.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'remaining_contract_weight': DailyReportMetricContract(
        unit='吨',
        tolerance=0.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'monthly_total_output': DailyReportMetricContract(
        unit='吨',
        tolerance=0.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'annual_total_output': DailyReportMetricContract(
        unit='吨',
        tolerance=0.0,
        source_contracts=_confirmable_source_contracts(),
    ),
    'anomaly_explanation_daily': DailyReportMetricContract(
        unit=None,
        tolerance=0.0,
        value_kind='nonempty_text',
        source_contracts=_confirmable_source_contracts(),
    ),
    'dingtalk_specialist_evidence': DailyReportMetricContract(
        unit=None,
        tolerance=0.0,
        value_kind='evidence_collection',
        source_contracts=(_dingtalk_source_contract(),),
    ),
    'source_status': DailyReportMetricContract(
        unit=None,
        tolerance=0.0,
        value_kind='diagnostic_status',
        confirmation_allowed=False,
        allowed_non_confirmed_statuses=frozenset({'candidate', 'missing', 'conflict'}),
        confirmed_failure_reason=(
            'source_status_confirmed_not_allowed_without_persisted_diagnostic_anchor'
        ),
    ),
    'daily_report_readiness': DailyReportMetricContract(
        unit=None,
        tolerance=0.0,
        value_kind='diagnostic_status',
        confirmation_allowed=False,
        allowed_non_confirmed_statuses=frozenset({'candidate', 'missing', 'conflict'}),
        confirmed_failure_reason=(
            'daily_report_readiness_confirmed_not_allowed_without_persisted_diagnostic_anchor'
        ),
    ),
})


def daily_report_contract_for(field: str) -> DailyReportMetricContract:
    return DAILY_REPORT_METRIC_CONTRACTS[field]


def daily_report_tolerance_for(field: str) -> float:
    contract = DAILY_REPORT_METRIC_CONTRACTS.get(field)
    return contract.tolerance if contract is not None else 0.0


def metric_value_failure_reason(field_name: str, value: Any) -> str | None:
    contract = DAILY_REPORT_METRIC_CONTRACTS.get(field_name)
    if contract is None:
        return 'metric_contract_missing'
    if not contract.confirmation_allowed:
        return contract.confirmed_failure_reason or 'confirmed_not_allowed_by_metric_policy'
    if contract.value_kind == 'finite_number':
        return None if _is_finite_number(value) else 'value_not_finite'
    if contract.value_kind == 'numeric_mapping':
        if not isinstance(value, Mapping) or not value:
            return 'value_not_numeric_mapping'
        if any(
            not str(key or '').strip() or not _is_finite_number(item)
            for key, item in value.items()
        ):
            return 'value_not_numeric_mapping'
        return None
    if contract.value_kind == 'nonempty_text':
        return None if isinstance(value, str) and value.strip() else 'value_not_nonempty_text'
    if contract.value_kind == 'evidence_collection':
        if isinstance(value, Mapping):
            items = (value,)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            items = tuple(value)
        else:
            items = ()
        if not items or any(not isinstance(item, Mapping) or not item for item in items):
            return 'value_not_evidence_collection'
        return None
    return 'value_kind_not_supported'


def metric_unit_failure_reason(field_name: str, unit: Any) -> str | None:
    contract = DAILY_REPORT_METRIC_CONTRACTS.get(field_name)
    if contract is None:
        return 'metric_contract_missing'
    normalized = str(unit or '').strip().lower()
    if contract.unit is None:
        return 'unit_not_applicable' if normalized else None
    if not normalized:
        return 'unit_missing'
    expected = contract.unit.strip().lower()
    return None if normalized in _UNIT_ALIASES.get(expected, frozenset({expected})) else 'unit_field_contract_mismatch'


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def fact_source_contract_for(
    field_name: str,
    source_type: str,
) -> FactSourceContract | None:
    metric_contract = DAILY_REPORT_METRIC_CONTRACTS.get(field_name)
    if (
        metric_contract is None
        or not metric_contract.confirmation_allowed
    ):
        return None
    return next(
        (
            source_contract
            for source_contract in _canonical_source_contracts(field_name, metric_contract)
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
