from datetime import date, datetime, timezone
from typing import Any
from types import SimpleNamespace

from app.adapters.mes_adapter import CardInfo
from app.core.idempotency import IdempotencyRecord
from app.services.work_order_service import (
    add_entry,
    build_previous_stage_output,
    create_work_order,
    filter_entry_payloads_for_scope,
    mask_table_payload,
    submit_entry,
)


def _user(**overrides):
    payload = {
        'id': 101,
        'role': 'shift_leader',
        'workshop_id': 1,
        'team_id': None,
        'data_scope_type': 'self_workshop',
        'is_mobile_user': False,
        'is_reviewer': False,
        'is_manager': False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_operational_role_only_sees_own_workshop_entries() -> None:
    visible = filter_entry_payloads_for_scope(
        [
            {'id': 1, 'workshop_id': 1, 'input_weight': 10},
            {'id': 2, 'workshop_id': 2, 'input_weight': 20},
        ],
        current_user=_user(role='shift_leader', workshop_id=1),
    )

    assert [item['id'] for item in visible] == [1]


def test_contracts_role_cannot_see_entries() -> None:
    visible = filter_entry_payloads_for_scope(
        [
            {'id': 1, 'workshop_id': 1},
            {'id': 2, 'workshop_id': 2},
        ],
        current_user=_user(role='contracts', workshop_id=None, data_scope_type='all'),
    )

    assert visible == []


def test_sensitive_header_fields_are_masked_for_shift_leader() -> None:
    masked = mask_table_payload(
        'work_orders',
        {
            'tracking_card_no': 'RA240001',
            'process_route_code': 'RA',
            'alloy_grade': 'A1050',
            'customer_name': 'Important Customer',
            'contract_weight': 9220,
            'previous_stage_output': {'workshop': 'hot_rolling', 'output_weight': 9220},
        },
        user_role='shift_leader',
    )

    assert masked['tracking_card_no'] == 'RA240001'
    assert masked['customer_name'] is None
    assert masked['contract_weight'] is None
    assert masked['previous_stage_output'] == {'workshop': 'hot_rolling', 'output_weight': 9220}


def test_previous_stage_output_contains_only_allowed_snapshot_fields() -> None:
    snapshot = build_previous_stage_output(
        SimpleNamespace(
            workshop_name='hot_rolling',
            verified_output_weight=9220,
            output_weight=9200,
            output_spec='6x1450',
            completed_at=datetime(2026, 3, 27, 7, 30, tzinfo=timezone.utc),
        )
    )

    assert snapshot == {
        'workshop': 'hot_rolling',
        'output_weight': 9220,
        'output_spec': '6x1450',
        'completed_at': '2026-03-27T07:30:00+00:00',
    }


class _DummyWorkOrderDB:
    def __init__(self):
        self.added = []

    def add(self, entity):
        self.added.append(entity)

    def flush(self):
        for index, entity in enumerate(self.added, start=1):
            if getattr(entity, 'id', None) is None:
                entity.id = 50 + index

    def commit(self):
        return None

    def refresh(self, _entity):
        return None


class _DummyQuery:
    def __init__(self, first_result=None):
        self.first_result = first_result

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.first_result


class _DummyCreateWorkOrderDB(_DummyWorkOrderDB):
    def __init__(self, first_result=None):
        super().__init__()
        self._query = _DummyQuery(first_result=first_result)

    def query(self, _model):
        return self._query


def test_add_entry_links_verified_ocr_submission(monkeypatch) -> None:
    linked = []
    db = _DummyWorkOrderDB()
    work_order = SimpleNamespace(id=1, current_station=None, overall_status='created')
    workshop = SimpleNamespace(id=1, code='casting', name='casting')

    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: work_order)
    monkeypatch.setattr('app.services.work_order_service._ensure_header_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service.build_scope_summary', lambda *_args, **_kwargs: SimpleNamespace())
    monkeypatch.setattr('app.services.work_order_service.resolve_work_order_entry_workshop_scope', lambda *_args, **_kwargs: 1)
    monkeypatch.setattr('app.services.work_order_service.can_view_all_work_order_entries', lambda *_args, **_kwargs: False)
    monkeypatch.setattr('app.services.work_order_service._ensure_workshop', lambda *_args, **_kwargs: workshop)
    monkeypatch.setattr('app.services.work_order_service._ensure_machine', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service._ensure_shift', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service._normalize_template_section_payload',
        lambda payload, **_kwargs: payload or {},
    )

    def fake_apply(entity, payload, *, user_role):
        assert 'ocr_submission_id' not in payload
        entity.input_weight = payload.get('input_weight')
        entity.output_weight = payload.get('output_weight')

    monkeypatch.setattr('app.services.work_order_service._apply_entry_fields', fake_apply)
    monkeypatch.setattr('app.services.work_order_service._calculate_yield_rate', lambda *_args, **_kwargs: 97.05)
    monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service.ocr_service.link_submission_to_entry',
        lambda _db, *, submission_id, entry_id, operator: linked.append((submission_id, entry_id, operator.id)),
    )
    monkeypatch.setattr(
        'app.services.work_order_service._serialize_entry',
        lambda _db, entity, *, user_role: {'id': entity.id, 'entry_status': entity.entry_status},
    )

    payload = add_entry(
        db,
        work_order_id=1,
        payload={
            'workshop_id': 1,
            'business_date': date(2026, 3, 28),
            'entry_type': 'completed',
            'input_weight': 9500,
            'output_weight': 9220,
            'ocr_submission_id': 12,
        },
        operator=_user(role='shift_leader', workshop_id=1),
    )

    assert payload == {'id': 51, 'entry_status': 'draft'}
    assert linked == [(12, 51, 101)]


def test_add_entry_returns_existing_entry_for_reused_idempotency_key(monkeypatch) -> None:
    db = _DummyWorkOrderDB()
    work_order = SimpleNamespace(id=1)
    entry = SimpleNamespace(id=88, work_order_id=1, workshop_id=1)

    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: work_order)
    monkeypatch.setattr('app.services.work_order_service._ensure_header_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service._ensure_entry', lambda *_args, **_kwargs: entry)
    monkeypatch.setattr('app.services.work_order_service._ensure_entry_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service.work_order_entry_idempotency_store.get',
        lambda *, scope, key, now=None: IdempotencyRecord(
            scope=scope,
            key=key,
            fingerprint='fp-1',
            value={'entry_id': 88},
            created_at=datetime(2026, 3, 28, 8, 0, 0, tzinfo=timezone.utc),
            expires_at=datetime(2026, 3, 29, 8, 0, 0, tzinfo=timezone.utc),
        ),
    )
    monkeypatch.setattr(
        'app.services.work_order_service._serialize_entry',
        lambda _db, entity, *, user_role: {'id': entity.id, 'entry_status': 'draft'},
    )

    payload = add_entry(
        db,
        work_order_id=1,
        payload={
            'workshop_id': 1,
            'business_date': date(2026, 3, 28),
            'entry_type': 'completed',
            'input_weight': 9500,
        },
        operator=_user(role='shift_leader', workshop_id=1),
        idempotency_key='550e8400-e29b-41d4-a716-446655440000',
    )

    assert payload == {'id': 88, 'entry_status': 'draft'}
    assert db.added == []


def test_add_entry_strips_readonly_fields_before_persist(monkeypatch) -> None:
    db = _DummyWorkOrderDB()
    work_order = SimpleNamespace(id=1, current_station=None, overall_status='created')
    workshop = SimpleNamespace(id=1, code='casting', name='casting')
    captured_payload: dict[str, Any] = {}

    def fake_apply(entity, payload, *, user_role):
        captured_payload.update(payload)
        entity.input_weight = payload.get('input_weight')
        entity.output_weight = payload.get('output_weight')

    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: work_order)
    monkeypatch.setattr('app.services.work_order_service._ensure_header_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service.build_scope_summary', lambda *_args, **_kwargs: SimpleNamespace())
    monkeypatch.setattr('app.services.work_order_service.resolve_work_order_entry_workshop_scope', lambda *_args, **_kwargs: 1)
    monkeypatch.setattr('app.services.work_order_service.can_view_all_work_order_entries', lambda *_args, **_kwargs: False)
    monkeypatch.setattr('app.services.work_order_service._ensure_workshop', lambda *_args, **_kwargs: workshop)
    monkeypatch.setattr('app.services.work_order_service._ensure_machine', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service._ensure_shift', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service._normalize_template_section_payload',
        lambda payload, **_kwargs: payload or {},
    )
    monkeypatch.setattr('app.services.work_order_service._apply_entry_fields', fake_apply)
    monkeypatch.setattr('app.services.work_order_service._calculate_yield_rate', lambda *_args, **_kwargs: 97.05)
    monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service._serialize_entry',
        lambda _db, entity, *, user_role: {'id': entity.id, 'yield_rate': entity.yield_rate},
    )

    payload = add_entry(
        db,
        work_order_id=1,
        payload={
            'workshop_id': 1,
            'business_date': date(2026, 3, 28),
            'entry_type': 'completed',
            'input_weight': 9500,
            'output_weight': 9220,
            'yield_rate': 88.88,
        },
        operator=_user(role='shift_leader', workshop_id=1),
    )

    assert 'yield_rate' not in captured_payload
    assert payload['yield_rate'] == 97.05


def test_create_work_order_prefills_mes_card_info(monkeypatch) -> None:
    db = _DummyCreateWorkOrderDB()

    class _FakeMesAdapter:
        def get_tracking_card_info(self, card_no: str):
            return CardInfo(
                card_no=card_no,
                process_route_code='MES-RA',
                alloy_grade='A3003',
            )

    monkeypatch.setattr('app.services.work_order_service.get_mes_adapter', lambda: _FakeMesAdapter())
    monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service._serialize_work_order',
        lambda _db, entity, *, user_role, entries=None: {
            'id': entity.id,
            'tracking_card_no': entity.tracking_card_no,
            'process_route_code': entity.process_route_code,
            'alloy_grade': entity.alloy_grade,
        },
    )

    payload = create_work_order(
        db,
        payload={'tracking_card_no': 'RA260001'},
        operator=_user(role='shift_leader', workshop_id=1),
    )

    assert payload == {
        'id': 51,
        'tracking_card_no': 'RA260001',
        'process_route_code': 'MES-RA',
        'alloy_grade': 'A3003',
    }


def test_submit_entry_pushes_completion_to_mes_when_work_order_completed(monkeypatch) -> None:
    pushed = []
    db = _DummyWorkOrderDB()
    entry = SimpleNamespace(
        id=77,
        work_order_id=1,
        entry_status='draft',
        entry_type='completed',
        verified_output_weight=None,
        output_weight=9220,
        yield_rate=97.2,
        weighed_at=None,
        verified_at=None,
        qc_at=None,
        approved_at=None,
        submitted_at=None,
        locked_fields=[],
    )
    work_order = SimpleNamespace(id=1, tracking_card_no='RA260001', overall_status='in_progress')

    class _FakeMesAdapter:
        def push_completion(self, card_no, output_weight, yield_rate):
            pushed.append((card_no, output_weight, yield_rate))
            return True

    monkeypatch.setattr('app.services.work_order_service._ensure_entry', lambda *_args, **_kwargs: entry)
    monkeypatch.setattr('app.services.work_order_service._ensure_entry_write_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service.apply_entry_submit',
        lambda entity, *, user_role: setattr(entity, 'entry_status', 'submitted'),
    )
    monkeypatch.setattr('app.services.work_order_service._calculate_yield_rate', lambda entity: entity.yield_rate)
    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: work_order)
    monkeypatch.setattr(
        'app.services.work_order_service._recompute_work_order_rollups',
        lambda _db, entity: setattr(entity, 'overall_status', 'completed'),
    )
    monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service._build_entry_event_payload', lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr('app.services.work_order_service._serialize_entry', lambda _db, entity, *, user_role: {'id': entity.id})
    monkeypatch.setattr('app.services.work_order_service.get_mes_adapter', lambda: _FakeMesAdapter())

    payload = submit_entry(
        db,
        entry_id=entry.id,
        operator=_user(role='shift_leader', workshop_id=1),
    )

    assert payload == {'id': 77}
    assert pushed == [('RA260001', 9220.0, 97.2)]


def test_owner_only_roles_can_submit_work_order_entries(monkeypatch) -> None:
    for role in ('contracts', 'inventory_keeper', 'utility_manager'):
        db = _DummyWorkOrderDB()
        entry = SimpleNamespace(
            id=77,
            work_order_id=1,
            workshop_id=1,
            shift_id=1,
            entry_status='draft',
            entry_type='completed',
            verified_output_weight=None,
            output_weight=9220,
            yield_rate=97.2,
            weighed_at=None,
            verified_at=None,
            qc_at=None,
            approved_at=None,
            submitted_at=None,
            locked_fields=[],
            created_by=101,
            created_by_user_id=101,
            machine_id=None,
        )
        work_order = SimpleNamespace(id=1, tracking_card_no='OWNER-CPK-20260417-A', overall_status='submitted')

        monkeypatch.setattr('app.services.work_order_service._ensure_entry', lambda *_args, **_kwargs: entry)
        monkeypatch.setattr('app.services.work_order_service._ensure_entry_write_access', lambda *_args, **_kwargs: None)
        monkeypatch.setattr('app.services.work_order_service._calculate_yield_rate', lambda entity: entity.yield_rate)
        monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: work_order)
        monkeypatch.setattr('app.services.work_order_service._recompute_work_order_rollups', lambda *_args, **_kwargs: None)
        monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
        monkeypatch.setattr('app.services.work_order_service._build_entry_event_payload', lambda *_args, **_kwargs: (None, None))
        monkeypatch.setattr('app.services.work_order_service._serialize_entry', lambda _db, entity, *, user_role: {'id': entity.id, 'entry_status': entity.entry_status})

        payload = submit_entry(
            db,
            entry_id=entry.id,
            operator=_user(role=role, workshop_id=1),
        )

        assert payload == {'id': 77, 'entry_status': 'submitted'}
