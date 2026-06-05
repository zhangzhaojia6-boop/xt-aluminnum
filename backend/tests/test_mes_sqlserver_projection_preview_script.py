from importlib.util import module_from_spec, spec_from_file_location

from app.adapters.mes_adapter import CoilSnapshot
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_mes_sqlserver_projection_preview.py'


def _load_script_module():
    spec = spec_from_file_location('check_mes_sqlserver_projection_preview_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_projection_preview_reports_completeness_without_raw_tracking_cards() -> None:
    module = _load_script_module()
    rows = [
        CoilSnapshot(
            coil_id='MES:1',
            tracking_card_no='S-1',
            batch_no='B1',
            contract_no='HT-1',
            workshop_code='冷轧',
            process_code='冷轧',
            metadata={
                'MaterialCode': 'S-1',
                'Customer': '客户A',
                'Alloy': '3003',
                'Specification': '0.8*1220*C',
                'FeedingWeight': 1.2,
                'CurrentWorkShop': '冷轧',
                'CurrentProcess': '冷轧',
                'ProcessRoute': '冷轧-退火',
            },
        ),
        CoilSnapshot(
            coil_id='MES:2',
            tracking_card_no='S-2',
            metadata={},
        ),
    ]

    preview = module.build_projection_preview(rows)

    assert preview['sqlserver_count'] == 2
    assert preview['required_field_rates']['tracking_card_no']['present'] == 2
    assert preview['required_field_rates']['alloy_grade']['present'] == 1
    assert preview['required_field_rates']['alloy_grade']['rate'] == 0.5
    assert preview['samples'][0]['tracking_card']['hash']
    assert 'S-1' not in repr(preview)
    assert '客户A' not in repr(preview)
