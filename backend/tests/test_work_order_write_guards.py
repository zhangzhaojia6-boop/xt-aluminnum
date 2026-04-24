from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.work_order_service import submit_entry, update_entry


def _user(**overrides):
    payload = {
        'id': 101,
        'role': 'shift_leader',
        'workshop_id': 1,
        'team_id': None,
        'data_scope_type': 'self_workshop',
        'assigned_shift_ids': [],
        'is_mobile_user': False,
        'is_reviewer': False,
        'is_manager': False,
        'name': '当前用户',
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _entry(**overrides):
    payload = {
        'id': 77,
        'work_order_id': 1,
        'workshop_id': 1,
        'machine_id': 2,
        'shift_id': 1,
        'business_date': date(2026, 3, 28),
        'entry_status': 'draft',
        'entry_type': 'completed',
        'locked_fields': [],
        'input_weight': 9500,
        'output_weight': 9220,
        'verified_input_weight': None,
        'verified_output_weight': None,
        'scrap_weight': None,
        'spool_weight': None,
        'yield_rate': 97.05,
        'weighed_at': None,
        'verified_at': None,
        'qc_at': None,
        'approved_at': None,
        'submitted_at': None,
        'created_by': 201,
        'created_by_user_id': 201,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


class _DummyDB:
    def commit(self):
        return None

    def refresh(self, _entity):
        return None


def _install_update_success_mocks(monkeypatch, entry):
    monkeypatch.setattr('app.services.work_order_service._ensure_entry', lambda *_args, **_kwargs: entry)
    monkeypatch.setattr('app.services.work_order_service._model_to_dict', lambda entity: dict(entity.__dict__))
    monkeypatch.setattr('app.services.work_order_service._resolve_entry_workshop_type', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service._apply_entry_fields',
        lambda entity, payload, **_kwargs: setattr(entity, 'input_weight', payload.get('input_weight', entity.input_weight)),
    )
    monkeypatch.setattr('app.services.work_order_service._calculate_yield_rate', lambda *_args, **_kwargs: 97.11)
    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: SimpleNamespace(id=1))
    monkeypatch.setattr('app.services.work_order_service._recompute_work_order_rollups', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service._serialize_entry',
        lambda _db, entity, *, user_role: {'id': entity.id, 'entry_status': entity.entry_status, 'yield_rate': entity.yield_rate},
    )


def test_update_entry_denies_non_creator_in_same_workshop(monkeypatch) -> None:
    db = _DummyDB()
    entry = _entry(created_by=202, created_by_user_id=202)
    _install_update_success_mocks(monkeypatch, entry)

    with pytest.raises(HTTPException) as exc:
        update_entry(
            db,
            entry_id=entry.id,
            payload={'input_weight': 9520},
            operator=_user(id=101, workshop_id=1),
        )

    assert exc.value.status_code == 403


def test_update_entry_strips_readonly_fields_before_apply(monkeypatch) -> None:
    db = _DummyDB()
    entry = _entry(id=88, created_by=101, created_by_user_id=101)
    captured_payload: dict[str, object] = {}

    def fake_apply(entity, payload, **_kwargs):
        captured_payload.update(payload)
        entity.input_weight = payload.get('input_weight', entity.input_weight)

    monkeypatch.setattr('app.services.work_order_service._ensure_entry', lambda *_args, **_kwargs: entry)
    monkeypatch.setattr('app.services.work_order_service._ensure_entry_write_access', lambda *_args, **_kwargs: False)
    monkeypatch.setattr('app.services.work_order_service._model_to_dict', lambda entity: dict(entity.__dict__))
    monkeypatch.setattr('app.services.work_order_service._resolve_entry_template_key', lambda *_args, **_kwargs: 'casting')
    monkeypatch.setattr('app.services.work_order_service._resolve_entry_workshop_type', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service._apply_entry_fields', fake_apply)
    monkeypatch.setattr('app.services.work_order_service._calculate_yield_rate', lambda *_args, **_kwargs: 97.1)
    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: SimpleNamespace(id=1))
    monkeypatch.setattr('app.services.work_order_service._recompute_work_order_rollups', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service._normalize_template_section_payload',
        lambda payload, **_kwargs: payload or {},
    )
    monkeypatch.setattr(
        'app.services.work_order_service._serialize_entry',
        lambda _db, entity, *, user_role: {'id': entity.id, 'yield_rate': entity.yield_rate},
    )

    payload = update_entry(
        db,
        entry_id=entry.id,
        payload={'input_weight': 9600, 'yield_rate': 12.34},
        operator=_user(id=101, workshop_id=1),
    )

    assert 'yield_rate' not in captured_payload
    assert payload['yield_rate'] == 97.1


def test_update_entry_denies_assigned_shift_mismatch(monkeypatch) -> None:
    db = _DummyDB()
    entry = _entry(created_by=101, created_by_user_id=101, shift_id=1)
    _install_update_success_mocks(monkeypatch, entry)

    with pytest.raises(HTTPException) as exc:
        update_entry(
            db,
            entry_id=entry.id,
            payload={'input_weight': 9520},
            operator=_user(id=101, workshop_id=1, data_scope_type='assigned', assigned_shift_ids=[2]),
        )

    assert exc.value.status_code == 403


def test_update_entry_denies_submitted_entry_without_reviewer_override(monkeypatch) -> None:
    db = _DummyDB()
    entry = _entry(created_by=101, created_by_user_id=101, entry_status='submitted')
    _install_update_success_mocks(monkeypatch, entry)

    with pytest.raises(HTTPException) as exc:
        update_entry(
            db,
            entry_id=entry.id,
            payload={'input_weight': 9520},
            operator=_user(id=101, workshop_id=1),
        )

    assert exc.value.status_code == 403


def test_reviewer_override_can_update_submitted_entry_and_log_request_meta(monkeypatch) -> None:
    db = _DummyDB()
    entry = _entry(created_by=202, created_by_user_id=202, entry_status='submitted', locked_fields=['input_weight'])
    audit_calls = []

    monkeypatch.setattr('app.services.work_order_service._ensure_entry', lambda *_args, **_kwargs: entry)
    monkeypatch.setattr('app.services.work_order_service._model_to_dict', lambda entity: dict(entity.__dict__))
    monkeypatch.setattr('app.services.work_order_service._resolve_entry_workshop_type', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service._apply_entry_fields',
        lambda entity, payload, **_kwargs: setattr(entity, 'input_weight', payload.get('input_weight')),
    )
    monkeypatch.setattr('app.services.work_order_service._calculate_yield_rate', lambda *_args, **_kwargs: 97.4)
    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: SimpleNamespace(id=1))
    monkeypatch.setattr('app.services.work_order_service._recompute_work_order_rollups', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service.record_entity_change',
        lambda *_args, **kwargs: audit_calls.append(kwargs),
    )
    monkeypatch.setattr(
        'app.services.work_order_service._serialize_entry',
        lambda _db, entity, *, user_role: {'id': entity.id, 'input_weight': entity.input_weight},
    )

    payload = update_entry(
        db,
        entry_id=entry.id,
        payload={'input_weight': 9530},
        operator=_user(id=301, role='reviewer', workshop_id=1, is_reviewer=True, name='复核员'),
        override_reason='复核修正',
        ip_address='10.0.0.7',
        user_agent='pytest-agent',
    )

    assert payload == {'id': 77, 'input_weight': 9530}
    assert audit_calls[0]['reason'] == '复核修正'
    assert audit_calls[0]['ip_address'] == '10.0.0.7'
    assert audit_calls[0]['user_agent'] == 'pytest-agent'


def test_owner_only_creator_can_update_submitted_entry_without_override(monkeypatch) -> None:
    db = _DummyDB()
    entry = _entry(
        created_by=101,
        created_by_user_id=101,
        entry_status='submitted',
        locked_fields=['extra_payload'],
        machine_id=None,
        shift_id=1,
    )

    monkeypatch.setattr('app.services.work_order_service._ensure_entry', lambda *_args, **_kwargs: entry)
    monkeypatch.setattr('app.services.work_order_service._model_to_dict', lambda entity: dict(entity.__dict__))
    monkeypatch.setattr('app.services.work_order_service._resolve_entry_workshop_type', lambda *_args, **_kwargs: 'inventory')
    monkeypatch.setattr(
        'app.services.work_order_service._apply_entry_fields',
        lambda entity, payload, **_kwargs: setattr(entity, 'extra_payload', payload.get('extra_payload')),
    )
    monkeypatch.setattr('app.services.work_order_service._calculate_yield_rate', lambda *_args, **_kwargs: 97.4)
    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: SimpleNamespace(id=1))
    monkeypatch.setattr('app.services.work_order_service._recompute_work_order_rollups', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service._serialize_entry',
        lambda _db, entity, *, user_role: {'id': entity.id, 'extra_payload': entity.extra_payload},
    )

    payload = update_entry(
        db,
        entry_id=entry.id,
        payload={'extra_payload': {'shipment_weight': 88}},
        operator=_user(id=101, role='inventory_keeper', workshop_id=1),
    )

    assert payload == {'id': 77, 'extra_payload': {'shipment_weight': 88}}


def test_submit_entry_denies_non_creator_without_override_reason(monkeypatch) -> None:
    db = _DummyDB()
    entry = _entry(created_by=202, created_by_user_id=202, entry_status='draft')

    monkeypatch.setattr('app.services.work_order_service._ensure_entry', lambda *_args, **_kwargs: entry)
    monkeypatch.setattr('app.services.work_order_service._model_to_dict', lambda entity: dict(entity.__dict__))
    monkeypatch.setattr(
        'app.services.work_order_service.apply_entry_submit',
        lambda entity, *, user_role: setattr(entity, 'entry_status', 'submitted'),
    )
    monkeypatch.setattr('app.services.work_order_service._calculate_yield_rate', lambda *_args, **_kwargs: entry.yield_rate)
    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: SimpleNamespace(id=1))
    monkeypatch.setattr('app.services.work_order_service._recompute_work_order_rollups', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service._build_entry_event_payload', lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr('app.services.work_order_service._serialize_entry', lambda _db, entity, *, user_role: {'id': entity.id})

    with pytest.raises(HTTPException) as exc:
        submit_entry(
            db,
            entry_id=entry.id,
            operator=_user(id=101, workshop_id=1),
        )

    assert exc.value.status_code == 403
