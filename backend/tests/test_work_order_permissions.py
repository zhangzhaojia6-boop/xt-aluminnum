from app.core.field_lock import get_fields_to_lock, next_entry_status_for_role
from app.core.field_permissions import check_field_write, get_readable_fields, get_writable_fields


def test_machine_operator_can_only_write_owned_entry_fields() -> None:
    writable = set(get_writable_fields('work_order_entries', 'machine_operator'))

    assert 'input_weight' in writable
    assert 'output_weight' in writable
    assert check_field_write('work_order_entries', 'input_weight', 'machine_operator') is True
    assert check_field_write('work_order_entries', 'energy_kwh', 'machine_operator') is False


def test_machine_operator_cannot_read_sensitive_contract_fields() -> None:
    readable = set(get_readable_fields('work_orders', 'machine_operator'))

    assert 'alloy_grade' in readable
    assert 'customer_name' not in readable
    assert 'contract_weight' not in readable


def test_contracts_can_manage_contract_header_fields_globally() -> None:
    writable = set(get_writable_fields('work_orders', 'contracts'))
    readable = set(get_readable_fields('work_orders', 'contracts'))

    assert 'contract_no' in writable
    assert 'customer_name' in writable
    assert 'contract_weight' in writable
    assert 'contract_no' in readable
    assert 'customer_name' in readable
    assert 'contract_weight' in readable


def test_submit_locks_only_current_role_fields() -> None:
    locked = set(get_fields_to_lock('work_order_entries', 'machine_operator'))

    assert 'input_weight' in locked
    assert 'output_weight' in locked
    assert 'energy_kwh' not in locked


def test_entry_status_progression_is_role_aware() -> None:
    assert next_entry_status_for_role('machine_operator', current_status='draft') == 'submitted'
    assert next_entry_status_for_role('qc', current_status='submitted') == 'approved'
    assert next_entry_status_for_role('energy_stat', current_status='verified') == 'approved'
