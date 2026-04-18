from app.core.field_lock import get_fields_to_lock, next_entry_status_for_role
from app.core.field_permissions import check_field_write, get_readable_fields, get_writable_fields


def test_shift_leader_can_only_write_owned_entry_fields() -> None:
    writable = set(get_writable_fields('work_order_entries', 'shift_leader'))

    assert 'input_weight' in writable
    assert 'output_weight' in writable
    assert 'verified_input_weight' not in writable
    assert check_field_write('work_order_entries', 'input_weight', 'shift_leader') is True
    assert check_field_write('work_order_entries', 'verified_input_weight', 'shift_leader') is False


def test_shift_leader_cannot_read_sensitive_contract_fields() -> None:
    readable = set(get_readable_fields('work_orders', 'shift_leader'))

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
    locked = set(get_fields_to_lock('work_order_entries', 'weigher'))

    assert 'verified_input_weight' in locked
    assert 'verified_output_weight' in locked
    assert 'input_weight' not in locked


def test_entry_status_progression_is_role_aware() -> None:
    assert next_entry_status_for_role('shift_leader', current_status='draft') == 'submitted'
    assert next_entry_status_for_role('weigher', current_status='submitted') == 'verified'
    assert next_entry_status_for_role('qc', current_status='verified') == 'approved'
