from __future__ import annotations

from typing import Any

from app.core.business_time import OWNER_DAILY_BUSINESS_DAY_START, PRODUCTION_BUSINESS_DAY_START


CORE_METRIC_CONTRACTS: dict[str, dict[str, Any]] = {
    'factory_total_output_tons': {
        'id': 'factory_total_output_tons',
        'label': '全厂总产量',
        'unit': 't',
        'primary_source': 'mes_stock_records.net_weight_tons',
        'fallback_source': 'mes_workshop_process_records.output_weight_tons when stock projection is absent; manual owner daily values are comparison only',
        'business_date_basis': 'production_business_date',
        'aggregation_rule': 'sum_mes_stock_in_to_finished_goods_first',
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
        'fallback_source': 'runtime output/input only for detail compatibility',
        'business_date_basis': 'production_business_date',
        'aggregation_rule': 'formal_matrix_first_runtime_detail_compat',
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
