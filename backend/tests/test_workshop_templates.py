import pytest

from app.core.workshop_templates import get_workshop_template, resolve_workshop_type
from app.services.work_order_service import split_entry_form_payload


def test_resolve_workshop_type_prefers_explicit_type_and_supports_aliases() -> None:
    assert resolve_workshop_type(workshop_type='cold_roll', workshop_code=None, workshop_name=None) == 'cold_roll'
    assert resolve_workshop_type(workshop_type='hot_rolling', workshop_code=None, workshop_name=None) == 'hot_roll'
    assert resolve_workshop_type(workshop_type='cutting', workshop_code=None, workshop_name=None) == 'shearing'
    assert resolve_workshop_type(workshop_type='inventory', workshop_code=None, workshop_name=None) == 'inventory'


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
    template = get_workshop_template('cold_roll', user_role='shift_leader')

    assert template['display_name'] == '冷轧车间'
    assert template['tempo'] == 'fast'
    assert template['supports_ocr'] is False
    assert [field['name'] for field in template['entry_fields']] == [
        'batch_no',
        'input_spec',
        'alloy_grade',
        'material_state',
        'on_machine_time',
        'off_machine_time',
        'input_weight',
        'output_spec',
        'spool_weight',
        'output_weight',
    ]
    assert [field['name'] for field in template['readonly_fields']] == ['scrap_weight', 'yield_rate']
    assert template['readonly_fields'][0]['compute'] == 'input_weight - output_weight - spool_weight'
    assert template['readonly_fields'][1]['compute'] == 'output_weight / input_weight * 100'
    assert all(field['readonly'] is True for field in template['readonly_fields'])
    assert all(field['editable'] is False for field in template['readonly_fields'])


def test_hot_roll_template_supports_ocr_and_uses_real_fields() -> None:
    template = get_workshop_template('hot_roll', user_role='shift_leader')

    assert template['display_name'] == '热轧车间'
    assert template['tempo'] == 'fast'
    assert template['supports_ocr'] is True
    assert [field['name'] for field in template['entry_fields']] == [
        'alloy_grade',
        'furnace_no',
        'ingot_spec',
        'on_machine_time',
        'off_machine_time',
        'input_weight',
        'output_weight',
        'trim_weight',
    ]
    assert [field['name'] for field in template['readonly_fields']] == ['yield_rate']


def test_finishing_template_hides_contract_field_from_shift_leader_and_exposes_it_to_contracts() -> None:
    shift_leader_template = get_workshop_template('finishing', user_role='shift_leader')
    contracts_template = get_workshop_template('finishing', user_role='contracts')

    shift_leader_extra_names = [field['name'] for field in shift_leader_template['extra_fields']]
    shift_leader_shift_names = [field['name'] for field in shift_leader_template['shift_fields']]
    contracts_extra_names = [field['name'] for field in contracts_template['extra_fields']]
    shift_leader_entry_names = [field['name'] for field in shift_leader_template['entry_fields']]

    assert shift_leader_entry_names == [
        'batch_no',
        'input_spec',
        'alloy_grade',
        'material_state',
        'on_machine_time',
        'input_weight',
        'spool_weight',
        'off_machine_time',
        'output_weight',
        'tray_weight',
        'scrap_weight',
    ]
    assert shift_leader_shift_names == ['roll_speed', 'ring_count']
    assert shift_leader_extra_names == []
    assert 'customer_name' not in shift_leader_extra_names
    assert contracts_extra_names == ['contract_no', 'customer_name', 'contract_weight']
    assert contracts_template['extra_fields'][0]['editable'] is True


def test_casting_template_is_slow_and_includes_actual_extra_fields() -> None:
    template = get_workshop_template('casting', user_role='shift_leader')

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
    ]
    assert [field['name'] for field in template['shift_fields']] == [
        'paper_furnace',
        'static_furnace',
        'unit_output',
        'gas_consumption',
    ]
    assert template['extra_fields'] == []


def test_phase1_templates_split_owner_fields_for_energy_qc_and_contract_roles() -> None:
    shift_leader_template = get_workshop_template('hot_roll', user_role='shift_leader')
    energy_template = get_workshop_template('hot_roll', user_role='energy_stat')
    qc_template = get_workshop_template('hot_roll', user_role='qc')
    contracts_template = get_workshop_template('hot_roll', user_role='contracts')

    assert 'energy_kwh' not in [field['name'] for field in shift_leader_template['extra_fields']]
    assert [field['name'] for field in energy_template['extra_fields']] == ['energy_kwh', 'gas_m3']
    assert [field['name'] for field in qc_template['qc_fields']] == ['qc_grade', 'qc_notes']
    assert [field['name'] for field in contracts_template['extra_fields']] == [
        'contract_no',
        'customer_name',
        'contract_weight',
    ]


def test_inventory_template_splits_inventory_fields_for_inventory_keeper_role() -> None:
    inventory_template = get_workshop_template('inventory', user_role='inventory_keeper')

    assert inventory_template['display_name'] == '成品库与公辅'
    assert [field['name'] for field in inventory_template['entry_fields']] == [
        'storage_inbound_weight',
        'storage_inbound_area',
        'plant_to_park_inbound_weight',
        'park_to_storage_inbound_weight',
        'month_to_date_inbound_weight',
        'month_to_date_inbound_area',
        'shipment_weight',
        'shipment_area',
        'month_to_date_shipment_weight',
        'month_to_date_shipment_area',
        'consignment_weight',
        'finished_inventory_weight',
        'shearing_prepared_weight',
    ]
    assert [field['name'] for field in inventory_template['readonly_fields']] == ['actual_inventory_weight']
    assert inventory_template['readonly_fields'][0]['compute'] == 'finished_inventory_weight - consignment_weight'


def test_inventory_template_splits_utility_fields_for_utility_manager_role() -> None:
    utility_template = get_workshop_template('inventory', user_role='utility_manager')

    assert [field['name'] for field in utility_template['extra_fields']] == [
        'total_electricity_kwh',
        'new_plant_electricity_kwh',
        'park_electricity_kwh',
        'cast_roll_gas_m3',
        'smelting_gas_m3',
        'heating_furnace_gas_m3',
        'boiler_gas_m3',
        'total_gas_m3',
        'groundwater_ton',
        'tap_water_ton',
    ]


def test_inventory_template_splits_contract_progress_fields_for_contracts_role() -> None:
    contracts_template = get_workshop_template('inventory', user_role='contracts')

    assert [field['name'] for field in contracts_template['extra_fields']] == [
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
