from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.mobile_report_service import save_or_submit_report


class _DummyDB:
    def __init__(self, shift):
        self._shift = shift

    def get(self, model, key):
        return self._shift

    def add(self, _entity):
        return None

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, _entity):
        return None


def _user(**overrides):
    payload = {
        'id': 11,
        'role': 'team_leader',
        'workshop_id': 1,
        'team_id': 10,
        'data_scope_type': 'self_team',
        'assigned_shift_ids': [],
        'is_mobile_user': True,
        'is_reviewer': False,
        'is_manager': False,
        'name': '班长',
        'dingtalk_user_id': 'dt-11',
        'dingtalk_union_id': 'union-11',
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _report(**overrides):
    payload = {
        'id': 7,
        'business_date': date(2026, 3, 28),
        'shift_config_id': 1,
        'workshop_id': 1,
        'team_id': 10,
        'owner_user_id': 11,
        'leader_user_id': 11,
        'leader_name': '班长',
        'dingtalk_user_id': 'dt-11',
        'dingtalk_union_id': 'union-11',
        'report_status': 'submitted',
        'submitted_by_user_id': 11,
        'last_action_by_user_id': 11,
        'attendance_count': 5,
        'input_weight': 95,
        'output_weight': 92,
        'scrap_weight': 1,
        'storage_prepared': None,
        'storage_finished': None,
        'shipment_weight': None,
        'contract_received': None,
        'electricity_daily': None,
        'gas_daily': None,
        'has_exception': False,
        'exception_type': None,
        'note': None,
        'optional_photo_url': None,
        'last_saved_at': None,
        'submitted_at': None,
        'returned_reason': None,
        'linked_production_data_id': None,
        'updated_at': None,
        'photo_file_path': None,
        'photo_file_name': None,
        'photo_uploaded_at': None,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_save_report_rejects_submitted_report_without_override_reason(monkeypatch) -> None:
    shift = SimpleNamespace(id=1, is_active=True)
    workshop = SimpleNamespace(id=1, name='冷轧')
    team = SimpleNamespace(id=10, name='甲班')
    db = _DummyDB(shift)

    monkeypatch.setattr('app.services.mobile_report_service.assert_mobile_user_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.mobile_report_service._resolve_workshop_team', lambda *_args, **_kwargs: (workshop, team))
    monkeypatch.setattr('app.services.mobile_report_service.assert_scope_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.mobile_report_service._find_mobile_report', lambda *_args, **_kwargs: _report())
    monkeypatch.setattr('app.services.mobile_report_service.assert_mobile_report_access', lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as exc:
        save_or_submit_report(
            db,
            payload={'business_date': date(2026, 3, 28), 'shift_id': 1, 'output_weight': 92},
            current_user=_user(),
            submit=False,
        )

    assert exc.value.status_code == 403


def test_admin_override_can_update_submitted_report_and_log_request_meta(monkeypatch) -> None:
    shift = SimpleNamespace(id=1, is_active=True, code='D', name='白班')
    workshop = SimpleNamespace(id=1, name='冷轧')
    team = SimpleNamespace(id=10, name='甲班')
    report = _report()
    db = _DummyDB(shift)
    audit_calls = []

    monkeypatch.setattr('app.services.mobile_report_service.assert_mobile_user_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.mobile_report_service._resolve_workshop_team', lambda *_args, **_kwargs: (workshop, team))
    monkeypatch.setattr('app.services.mobile_report_service.assert_scope_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.mobile_report_service._find_mobile_report', lambda *_args, **_kwargs: report)
    monkeypatch.setattr('app.services.mobile_report_service._model_to_dict', lambda entity: dict(entity.__dict__))
    monkeypatch.setattr('app.services.mobile_report_service.assert_mobile_report_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.mobile_report_service.record_entity_change',
        lambda *_args, **kwargs: audit_calls.append(kwargs),
    )
    monkeypatch.setattr(
        'app.services.mobile_report_service._serialize_mobile_report',
        lambda _db, report, **_kwargs: {'id': report.id, 'report_status': report.report_status, 'output_weight': report.output_weight},
    )

    payload = save_or_submit_report(
        db,
        payload={'business_date': date(2026, 3, 28), 'shift_id': 1, 'output_weight': 93, 'override_reason': '管理员修正'},
        current_user=_user(id=1, role='admin', workshop_id=None, team_id=None, data_scope_type='all'),
        submit=False,
        ip_address='10.0.0.8',
        user_agent='pytest-mobile',
    )

    assert payload == {'id': 7, 'report_status': 'draft', 'output_weight': 93}
    assert audit_calls[0]['reason'] == '管理员修正'
    assert audit_calls[0]['ip_address'] == '10.0.0.8'
    assert audit_calls[0]['user_agent'] == 'pytest-mobile'
