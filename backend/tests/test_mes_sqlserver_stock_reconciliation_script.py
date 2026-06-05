from importlib.util import module_from_spec, spec_from_file_location

from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_mes_sqlserver_stock_reconciliation.py'


def _load_script_module():
    spec = spec_from_file_location('check_mes_sqlserver_stock_reconciliation_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_stock_reconciliation_report_compares_business_day_totals() -> None:
    module = _load_script_module()
    sql_summary = {
        'row_count': 10,
        'net_weight_tons': 100.0,
        'items': [
            {
                'business_date': '2026-06-03',
                'from_department': '精整',
                'to_department': '成品库',
                'status': '1',
                'row_count': 10,
                'net_weight_tons': 100.0,
            }
        ],
    }
    local_summary = {
        'row_count': 10,
        'net_weight_tons': 99.5,
        'items': [
            {
                'business_date': '2026-06-03',
                'from_department': '精整',
                'to_department': '成品库',
                'status': '1',
                'row_count': 10,
                'net_weight_tons': 99.5,
            }
        ],
    }

    report = module.build_stock_reconciliation_report(sql_summary, local_summary, days=7)

    assert report['sqlserver']['row_count'] == 10
    assert report['local_projection']['row_count'] == 10
    assert report['business_date_comparison'][0]['delta_tons'] == 0.5
    assert report['business_date_comparison'][0]['within_one_percent'] is True
    assert report['ready_for_cutover'] is False
    assert report['reasons'] == ['needs_at_least_7_business_dates']


def test_build_stock_reconciliation_report_flags_missing_local_projection() -> None:
    module = _load_script_module()

    report = module.build_stock_reconciliation_report(
        {'row_count': 5, 'net_weight_tons': 20.0, 'items': [{'business_date': '2026-06-03', 'net_weight_tons': 20.0}]},
        {'row_count': 0, 'net_weight_tons': 0.0, 'items': []},
        days=7,
    )

    assert report['ready_for_cutover'] is False
    assert 'local_projection_empty' in report['reasons']


def test_build_stock_reconciliation_report_ignores_local_only_cache_dates_for_cutover() -> None:
    module = _load_script_module()

    report = module.build_stock_reconciliation_report(
        {
            'row_count': 1,
            'net_weight_tons': 10.0,
            'items': [{'business_date': '2026-06-04', 'row_count': 1, 'net_weight_tons': 10.0}],
        },
        {
            'row_count': 2,
            'net_weight_tons': 15.0,
            'items': [
                {'business_date': '2026-06-04', 'row_count': 1, 'net_weight_tons': 10.0},
                {'business_date': '2026-05-28', 'row_count': 1, 'net_weight_tons': 5.0},
            ],
        },
        days=1,
    )

    assert report['local_projection']['row_count'] == 1
    assert report['local_projection']['total_cached_row_count'] == 2
    assert report['local_projection']['local_only_business_dates'] == ['2026-05-28']
    assert len(report['business_date_comparison']) == 1
    assert report['ready_for_cutover'] is False
    assert report['reasons'] == ['needs_at_least_7_business_dates']


def test_build_local_stock_summary_filters_finished_goods_candidate_rows() -> None:
    module = _load_script_module()
    rows = [
        {
            'business_date': '2026-06-03',
            'net_weight_tons': 10.5,
            'status_name': '1',
            'source_payload': {
                'FromDepartment': '精整',
                'ToDepartment': '成品库',
                'Status': 1,
            },
        },
        {
            'business_date': '2026-06-03',
            'net_weight_tons': 5.0,
            'status_name': '1',
            'source_payload': {
                'FromDepartment': '冷轧',
                'ToDepartment': '半成品库',
                'Status': 1,
            },
        },
    ]

    summary = module.build_local_stock_summary(rows, days=7)

    assert summary['row_count'] == 1
    assert summary['net_weight_tons'] == 10.5
    assert summary['items'][0]['from_department'] == '精整'


def test_local_stock_projection_columns_selects_required_existing_columns() -> None:
    module = _load_script_module()

    columns = module.local_stock_projection_columns(['business_date', 'net_weight_tons', 'source_payload', 'unused'])

    assert columns == ['business_date', 'net_weight_tons', 'source_payload']
