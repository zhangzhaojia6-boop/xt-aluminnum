from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location

from app.adapters.mes_adapter import MesSourceRecord
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_mes_sqlserver_stock_preview.py'


def _load_script_module():
    spec = spec_from_file_location('check_mes_sqlserver_stock_preview_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_stock_preview_reports_in_stock_completeness_without_raw_business_keys() -> None:
    module = _load_script_module()
    rows = [
        MesSourceRecord(
            source_id='stock-1',
            source_path='sqlserver:stock_records',
            event_time=datetime(2026, 6, 4, 8, 30),
            metadata={
                'BatchNumber': 'PB-001',
                'ContractCode': 'HT-001',
                'Customer': '客户A',
                'NetWeight': 1200,
                'GrossWeight': 1220,
                'InStockDate': datetime(2026, 6, 4, 8, 30),
                'Status': '已入库',
                'FromDepartment': '精整',
                'ToDepartment': '成品库',
            },
        ),
        MesSourceRecord(
            source_id='stock-2',
            source_path='sqlserver:stock_records',
            metadata={
                'BatchNumber': 'PB-002',
                'NetWeight': 800,
                'FromDepartment': '拉矫',
                'ToDepartment': '成品库',
                'Status': '1',
            },
        ),
    ]

    preview = module.build_stock_preview(rows)

    assert preview['sqlserver_count'] == 2
    assert preview['required_field_rates']['batch_no']['present'] == 2
    assert preview['required_field_rates']['in_stock_date']['present'] == 1
    assert preview['required_field_rates']['net_weight_tons']['rate'] == 1.0
    assert preview['weight_totals']['net_weight_tons'] == 2.0
    assert preview['weight_quality']['rows_with_both_weights'] == 1
    assert preview['weight_quality']['has_net_gt_gross_anomaly'] is False
    assert preview['department_counts'][0]['to_department'] == '成品库'
    assert preview['candidate_total_output_filter']['weight_field'] == 'NetWeight'
    assert preview['business_date_counts']['2026-06-04'] == 1
    assert preview['readiness']['finished_goods_output_candidate'] is False
    assert preview['readiness']['needs_unit_confirmation'] is True
    assert preview['samples'][0]['source']['hash']
    assert 'PB-001' not in repr(preview)
    assert 'HT-001' not in repr(preview)
    assert '客户A' not in repr(preview)


def test_build_stock_preview_flags_net_weight_greater_than_gross_weight() -> None:
    module = _load_script_module()
    rows = [
        MesSourceRecord(
            source_id='stock-1',
            source_path='sqlserver:stock_records',
            metadata={
                'BatchNumber': 'PB-001',
                'NetWeight': 1200,
                'GrossWeight': 800,
                'CreateDate': datetime(2026, 6, 4, 8, 30),
            },
        ),
    ]

    preview = module.build_stock_preview(rows)

    assert preview['required_field_rates']['in_stock_date']['rate'] == 1.0
    assert preview['weight_quality']['has_net_gt_gross_anomaly'] is True
    assert preview['readiness']['finished_goods_output_candidate'] is False


def test_build_total_output_candidate_summary_aggregates_rows() -> None:
    module = _load_script_module()
    summary = module.build_total_output_candidate_summary(
        [
            {
                'business_date': '2026-06-04',
                'from_department': '精整',
                'to_department': '成品库',
                'status': 1,
                'row_count': 2,
                'net_weight_tons': 5.5,
            },
            {
                'business_date': '2026-06-04',
                'from_department': '拉矫',
                'to_department': '成品库',
                'status': 1,
                'row_count': 1,
                'net_weight_tons': 2.25,
            },
        ],
        days=7,
    )

    assert summary['days'] == 7
    assert summary['row_count'] == 3
    assert summary['net_weight_tons'] == 7.75
    assert summary['items'][0]['from_department'] == '精整'


def test_build_total_output_candidate_summary_uses_production_business_day() -> None:
    module = _load_script_module()
    summary = module.build_total_output_candidate_summary(
        [
            {
                'event_time': datetime(2026, 6, 4, 6, 59),
                'from_department': '精整',
                'to_department': '成品库',
                'status': 1,
                'net_weight_tons': 5.5,
            },
        ],
        days=7,
    )

    assert summary['items'][0]['business_date'] == '2026-06-03'


def test_business_date_window_for_days_uses_full_production_business_dates() -> None:
    module = _load_script_module()

    window = module.business_date_window_for_days(days=7, now=datetime(2026, 6, 5, 6, 59))

    assert window['start_business_date'].isoformat() == '2026-05-29'
    assert window['end_business_date'].isoformat() == '2026-06-04'
    assert window['start_at'].isoformat(sep=' ') == '2026-05-29 07:30:00'
    assert window['end_at'].isoformat(sep=' ') == '2026-06-05 07:30:00'


def test_business_date_window_for_days_can_ignore_current_incomplete_business_date() -> None:
    module = _load_script_module()

    window = module.business_date_window_for_days(
        days=7,
        now=datetime(2026, 6, 5, 8, 1),
        completed_only=True,
    )

    assert window['start_business_date'].isoformat() == '2026-05-29'
    assert window['end_business_date'].isoformat() == '2026-06-04'
    assert window['start_at'].isoformat(sep=' ') == '2026-05-29 07:30:00'
    assert window['end_at'].isoformat(sep=' ') == '2026-06-05 07:30:00'
