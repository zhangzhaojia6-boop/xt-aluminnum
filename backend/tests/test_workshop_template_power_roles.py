import pytest
from app.core.workshop_templates import get_workshop_template


def test_admin_gets_all_entry_fields_editable():
    result = get_workshop_template('casting', user_role='admin')
    assert result['entry_fields'], "admin should receive at least one entry field"
    for field in result['entry_fields']:
        assert field['editable'] is True, f"field {field['name']} should be editable for admin"


def test_manager_gets_all_entry_fields_editable():
    result = get_workshop_template('casting', user_role='manager')
    assert result['entry_fields'], "manager should receive at least one entry field"
    for field in result['entry_fields']:
        assert field['editable'] is True, f"field {field['name']} should be editable for manager"


def test_shift_leader_gets_entry_fields_editable():
    result = get_workshop_template('casting', user_role='shift_leader')
    assert result['entry_fields'], "shift_leader should receive entry fields"


def test_viewer_gets_no_editable_entry_fields():
    result = get_workshop_template('casting', user_role='viewer')
    editable = [f for f in result['entry_fields'] if f.get('editable')]
    assert not editable, "viewer should have no editable entry fields"
