import pytest

from app.core.workshop_templates import (
    OVERHAUL_OWNER_FIELDS,
    get_workshop_template,
    get_workshop_template_definition,
    resolve_workshop_type,
)
from app.services.work_order_service import split_entry_form_payload


def test_resolve_workshop_type_prefers_explicit_type_and_supports_aliases() -> None:
    assert resolve_workshop_type(workshop_type='cold_roll', workshop_code=None, workshop_name=None) == 'cold_roll'
    assert resolve_workshop_type(workshop_type='hot_rolling', workshop_code=None, workshop_name=None) == 'hot_roll'
    assert resolve_workshop_type(workshop_type='cutting', workshop_code=None, workshop_name=None) == 'shearing'
    assert resolve_workshop_type(workshop_type='inventory', workshop_code=None, workshop_name=None) == 'inventory'


def test_overhaul_owner_can_fill_structured_machine_stop_records() -> None:
    field = next(item for item in OVERHAUL_OWNER_FIELDS if item["name"] == "machine_stop_records")

    assert field["type"] == "machine_stop_list"
    assert field["role_write"] == ["overhaul_owner"]


@pytest.mark.parametrize(
    ('workshop_code', 'workshop_name', 'expected'),
    [
        ('LZ2050', '2050冷轧车间', 'cold_roll'),
        ('LZ1450', '1450冷轧车间', 'cold_roll'),
        ('LZ3', '冷轧三车间', 'cold_roll'),
        ('RZ', '热轧车间', 'hot_roll'),
        ('JZ', '精整车间', 'finishing'),
        ('JQ', '园区剪切车间', 'shearing'),
        ('ZR2', '铸二车间', 'casting'),
        ('ZD', '铸锭车间', 'casting'),
        ('CPK', '成品库', 'inventory'),
    ],
)
def test_resolve_workshop_type_infers_real_factory_workshops(
    workshop_code: str,
    workshop_name: str,
    expected: str,
) -> None:
    assert resolve_workshop_type(workshop_type=None, workshop_code=workshop_code, workshop_name=workshop_name) == expected


def test_cold_roll_template_matches_paper_report_fields() -> None:
    template = get_workshop_template('cold_roll', user_role='machine_operator')

    assert template['display_name'] == '冷轧车间'
    assert template['tempo'] == 'fast'
    assert template['supports_ocr'] is False
    assert [field['name'] for field in template['entry_fields']] == [
        'tracking_card_no',
        'process_stage',
        'pass_count',
        'input_spec',
        'alloy_grade',
        'material_state',
        'input_weight',
        'output_spec',
        'spool_weight',
        'output_weight',
    ]
    readonly_names = [field['name'] for field in template['readonly_fields']]
    assert readonly_names == [
        'scrap_weight',
        'yield_rate',
    ]
    scrap_index = readonly_names.index('scrap_weight')
    yield_index = readonly_names.index('yield_rate')
    assert template['readonly_fields'][scrap_index]['compute'] == 'input_weight - output_weight - spool_weight'
    assert template['readonly_fields'][yield_index]['compute'] == 'output_weight / input_weight * 100'
    assert template['readonly_fields'][scrap_index]['readonly'] is True
    assert template['readonly_fields'][yield_index]['readonly'] is True
    assert template['readonly_fields'][scrap_index]['editable'] is False
    assert template['readonly_fields'][yield_index]['editable'] is False


def test_hot_roll_template_supports_ocr_and_uses_real_fields() -> None:
    template = get_workshop_template('hot_roll', user_role='machine_operator')

    assert template['display_name'] == '热轧车间'
    assert template['tempo'] == 'fast'
    assert template['supports_ocr'] is True
    assert [field['name'] for field in template['entry_fields']] == [
        'alloy_grade',
        'furnace_no',
        'ingot_spec',
        'input_weight',
        'output_weight',
        'trim_weight',
    ]
    assert [field['name'] for field in template['readonly_fields']] == [
        'scrap_weight',
        'yield_rate',
    ]


class _TemplateConfigQuery:
    def __init__(self, config, *, miss_first: bool = False):
        self.config = config
        self.miss_first = miss_first
        self.calls = 0

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        self.calls += 1
        if self.miss_first and self.calls == 1:
            return None
        return self.config


class _TemplateConfigDB:
    def __init__(self, config, *, miss_first: bool = False):
        self.query_obj = _TemplateConfigQuery(config, miss_first=miss_first)

    def query(self, _model):
        return self.query_obj


def test_casting_config_cannot_drop_machine_output_field() -> None:
    stale_config = type(
        'TemplateConfig',
        (),
        {
            'template_key': 'casting',
            'display_name': '铸造车间',
            'tempo': 'slow',
            'supports_ocr': True,
            'entry_fields': [
                {'name': 'alloy_grade', 'label': '合金', 'type': 'text', 'required': True},
                {'name': 'ingot_spec', 'label': '规格', 'type': 'text', 'required': True},
                {'name': 'cast_speed', 'label': '速度', 'type': 'number', 'unit': 'mm/min'},
                {'name': 'input_weight', 'label': '投入铝锭', 'type': 'number', 'unit': 'kg'},
                {'name': 'scrap_weight', 'label': '废料', 'type': 'number', 'unit': 'kg'},
                {'name': 'skin_weight', 'label': '皮料段', 'type': 'number', 'unit': 'kg'},
                {'name': 'quality_issue_type', 'label': '质量类型', 'type': 'text'},
            ],
            'extra_fields': [],
            'qc_fields': [],
            'readonly_fields': [{'name': 'yield_rate', 'label': '成品率', 'compute': 'output_weight / input_weight * 100'}],
        },
    )()

    template = get_workshop_template_definition('ZR3', db=_TemplateConfigDB(stale_config, miss_first=True))
    names = [field['name'] for field in template['entry_fields']]

    assert names == [
        'alloy_grade',
        'ingot_spec',
        'cast_speed',
        'input_weight',
        'scrap_weight',
        'skin_weight',
        'output_weight',
    ]


def test_finishing_template_hides_contract_field_from_machine_operator_and_exposes_it_to_contracts() -> None:
    machine_operator_template = get_workshop_template('finishing', user_role='machine_operator')
    contracts_template = get_workshop_template('finishing', user_role='contracts')

    machine_operator_extra_names = [field['name'] for field in machine_operator_template['extra_fields']]
    machine_operator_shift_names = [field['name'] for field in machine_operator_template['shift_fields']]
    contracts_extra_names = [field['name'] for field in contracts_template['extra_fields']]
    machine_operator_entry_names = [field['name'] for field in machine_operator_template['entry_fields']]

    assert machine_operator_entry_names == [
        'tracking_card_no',
        'input_spec',
        'alloy_grade',
        'material_state',
        'input_weight',
        'output_weight',
    ]
    assert machine_operator_shift_names == []
    assert machine_operator_extra_names == []
    assert 'customer_name' not in machine_operator_extra_names
    assert contracts_extra_names == ['contract_no', 'customer_name', 'contract_weight']
    assert contracts_template['extra_fields'][0]['editable'] is True


def test_casting_template_is_slow_and_includes_actual_extra_fields() -> None:
    template = get_workshop_template('casting', user_role='machine_operator')

    assert template['display_name'] == '铸造车间'
    assert template['tempo'] == 'slow'
    assert template['supports_ocr'] is True
    assert [field['name'] for field in template['entry_fields']] == [
        'alloy_grade',
        'ingot_spec',
        'cast_speed',
        'input_weight',
        'scrap_weight',
        'skin_weight',
        'paper_furnace',
        'static_furnace',
        'output_weight',
    ]
    assert next(field for field in template['entry_fields'] if field['name'] == 'output_weight')['label'] == '单机产量'
    assert [field['name'] for field in template['shift_fields']] == []
    assert template['extra_fields'] == []


def test_phase1_templates_split_owner_fields_for_energy_qc_and_contract_roles() -> None:
    machine_operator_template = get_workshop_template('hot_roll', user_role='machine_operator')
    energy_template = get_workshop_template('hot_roll', user_role='energy_stat')
    qc_template = get_workshop_template('hot_roll', user_role='qc')
    contracts_template = get_workshop_template('hot_roll', user_role='contracts')

    assert 'energy_kwh' not in [field['name'] for field in machine_operator_template['extra_fields']]
    assert [field['name'] for field in energy_template['extra_fields']] == ['energy_kwh', 'gas_m3', 'energy_note']
    assert [field['name'] for field in qc_template['qc_fields']] == ['plant_wide_yield_rate']
    assert [field['name'] for field in contracts_template['extra_fields']] == [
        'contract_no',
        'customer_name',
        'contract_weight',
    ]


def test_inventory_template_splits_inventory_fields_for_inventory_keeper_role() -> None:
    inventory_template = get_workshop_template('inventory', user_role='inventory_keeper')

    assert inventory_template['display_name'] == '成品库'
    assert [field['name'] for field in inventory_template['entry_fields']] == [
        'park_inbound_daily',
        'park_inbound_monthly',
        'park_outbound_daily',
        'park_outbound_monthly',
        'new_plant_inbound_daily',
        'new_plant_inbound_monthly',
        'new_plant_outbound_daily',
        'new_plant_outbound_monthly',
        'consignment_weight',
    ]
    assert [field['name'] for field in inventory_template['readonly_fields']] == ['actual_inventory_weight']
    assert inventory_template['readonly_fields'][0]['compute'] == 'finished_inventory_weight - consignment_weight'


def test_inventory_template_splits_utility_fields_for_utility_manager_role() -> None:
    utility_template = get_workshop_template('inventory', user_role='utility_manager')

    assert [field['name'] for field in utility_template['extra_fields']] == []


def test_inventory_template_exposes_wip_and_contract_progress_to_planning_role() -> None:
    contracts_template = get_workshop_template('inventory', user_role='contracts')

    assert [field['name'] for field in contracts_template['extra_fields']] == [
        'wip_total',
        'daily_contract_weight',
        'daily_hot_roll_contract_weight',
        'month_to_date_contract_weight',
        'month_to_date_hot_roll_contract_weight',
        'remaining_contract_weight',
        'remaining_hot_roll_contract_weight',
        'remaining_contract_delta_weight',
        'billet_inventory_weight',
        'daily_input_weight',
        'month_to_date_input_weight',
    ]


def test_recovery_and_overhaul_owner_fields_keep_daily_entry_shape_with_machine_stops() -> None:
    from app.routers.mobile import ROLE_FIELD_MAPPING

    recovery_fields = ROLE_FIELD_MAPPING['recovery_owner']['direct_fields']
    overhaul_fields = ROLE_FIELD_MAPPING['overhaul_owner']['direct_fields']

    assert ROLE_FIELD_MAPPING['recovery_owner']['label'] == '回收产量'
    assert [field['name'] for field in recovery_fields] == [
        'recovery_weight',
        'recovery_material_type',
        'recovery_notes',
    ]
    assert ROLE_FIELD_MAPPING['overhaul_owner']['label'] == '大修磨辊子+能耗'
    assert [field['name'] for field in overhaul_fields] == [
        'machine_stop_records',
        'roller_grinding_count',
        'overhaul_energy_kwh',
        'overhaul_gas_m3',
        'overhaul_notes',
    ]


def test_split_entry_form_payload_routes_real_report_fields_between_standard_and_extra_payload() -> None:
    payload = {
        'business_date': '2026-03-30',
        'input_weight': 9430,
        'output_weight': 9220,
        'alloy_grade': '5052',
        'batch_no': 'B2026033001',
        'furnace_no': 'RZ-260330',
        'gas_consumption': 382,
        'trim_weight': 80,
    }

    split_payload = split_entry_form_payload(payload)

    assert split_payload['work_order_values'] == {'alloy_grade': '5052'}
    assert split_payload['entry_values'] == {
        'business_date': '2026-03-30',
        'input_weight': 9430,
        'output_weight': 9220,
    }
    assert split_payload['extra_values'] == {
        'batch_no': 'B2026033001',
        'furnace_no': 'RZ-260330',
        'gas_consumption': 382,
        'trim_weight': 80,
    }
    assert split_payload['qc_values'] == {}
