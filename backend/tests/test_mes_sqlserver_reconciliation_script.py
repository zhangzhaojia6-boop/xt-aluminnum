from importlib.util import module_from_spec, spec_from_file_location
from types import SimpleNamespace

from app.adapters.mes_adapter import CoilSnapshot
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_mes_sqlserver_reconciliation.py'


def _load_script_module():
    spec = spec_from_file_location('check_mes_sqlserver_reconciliation_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_reconciliation_report_counts_matches_and_field_rates() -> None:
    module = _load_script_module()
    sql_rows = [
        CoilSnapshot(
            coil_id='MES:1',
            tracking_card_no='S-1',
            batch_no='B1',
            contract_no='HT-1',
            workshop_code='冷轧',
            process_code='冷轧',
            metadata={'Alloy': '3003', 'Specification': '0.8*1220*C', 'ProcessRoute': '冷轧-退火'},
        ),
        CoilSnapshot(
            coil_id='MES:2',
            tracking_card_no='S-2',
            batch_no='B2',
            workshop_code='退火',
            process_code='退火',
            metadata={'Alloy': '5052', 'Specification': '1.0*1000*C', 'ProcessRoute': '退火-精整'},
        ),
    ]
    local_rows = [
        SimpleNamespace(
            tracking_card_no='S-1',
            batch_no='B1',
            contract_no='HT-1',
            current_workshop='冷轧',
            current_process='冷轧',
            alloy_grade='3003',
            spec_display='0.8*1220*C',
            process_route_text='冷轧-退火',
        )
    ]

    report = module.build_reconciliation_report(sql_rows, local_rows)

    assert report['sqlserver_count'] == 2
    assert report['local_match_count'] == 1
    assert report['missing_local_count'] == 1
    assert report['match_rate'] == 0.5
    assert report['field_rates']['batch_no']['matched'] == 1
    assert report['field_rates']['alloy_grade']['rate'] == 1.0
    assert report['missing_local_samples'][0]['tracking_card']['hash']
    assert 'S-2' not in repr(report)


def test_local_projection_columns_uses_only_existing_columns() -> None:
    module = _load_script_module()

    columns = module.local_projection_columns(['coil_id', 'tracking_card_no', 'batch_no', 'current_workshop'])

    assert columns == ['coil_id', 'tracking_card_no', 'batch_no', 'current_workshop']


def test_build_reconciliation_report_prefers_coil_identity_over_duplicate_card() -> None:
    module = _load_script_module()
    sql_rows = [
        CoilSnapshot(
            coil_id='MES:2',
            tracking_card_no='S-1',
            batch_no='B2',
            workshop_code='冷轧',
            process_code='轧制',
            metadata={'Id': '2', 'Alloy': '3003', 'Specification': '0.8*1220*C', 'ProcessRoute': '冷轧-退火'},
        )
    ]
    local_rows = [
        SimpleNamespace(
            coil_id='MES:1',
            mes_product_id='1',
            tracking_card_no='S-1',
            batch_no='B1',
            current_workshop='退火',
            current_process='退火',
            alloy_grade='5052',
            spec_display='1.0*1000*C',
            process_route_text='退火-精整',
        ),
        SimpleNamespace(
            coil_id='MES:2',
            mes_product_id='2',
            tracking_card_no='S-1',
            batch_no='B2',
            current_workshop='冷轧',
            current_process='轧制',
            alloy_grade='3003',
            spec_display='0.8*1220*C',
            process_route_text='冷轧-退火',
        ),
    ]

    report = module.build_reconciliation_report(sql_rows, local_rows)

    assert report['local_match_count'] == 1
    assert report['field_rates']['batch_no']['rate'] == 1.0
    assert report['field_rates']['current_process']['rate'] == 1.0


def test_build_reconciliation_report_marks_field_mismatches_without_raw_cards() -> None:
    module = _load_script_module()
    sql_rows = [
        CoilSnapshot(
            coil_id='MES:1',
            tracking_card_no='S-1',
            workshop_code='冷轧',
            process_code='冷轧',
            metadata={'Alloy': '3003'},
        )
    ]
    local_rows = [
        SimpleNamespace(
            tracking_card_no='S-1',
            batch_no=None,
            contract_no=None,
            current_workshop='退火',
            current_process='退火',
            alloy_grade='5052',
            spec_display=None,
            process_route_text=None,
        )
    ]

    report = module.build_reconciliation_report(sql_rows, local_rows)

    assert report['field_rates']['current_workshop']['matched'] == 0
    assert report['field_rates']['current_workshop']['mismatched'] == 1
    assert {item['field'] for item in report['field_mismatch_samples']} >= {'alloy_grade'}
    assert 'S-1' not in repr(report)
