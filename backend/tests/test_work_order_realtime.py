from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.work_order_service import submit_entry


def test_submit_entry_publishes_role_specific_realtime_event(monkeypatch) -> None:
    entry = SimpleNamespace(
        id=9,
        work_order_id=1,
        workshop_id=2,
        machine_id=11,
        shift_id=3,
        verified_at=datetime(2026, 3, 27, 8, 0, tzinfo=timezone.utc),
        approved_at=None,
        weighed_at=None,
        qc_at=None,
        verified_input_weight=10.0,
        verified_output_weight=9.7,
        input_weight=10.0,
        output_weight=9.7,
        yield_rate=None,
        entry_status='draft',
        locked_fields=[],
    )
    work_order = SimpleNamespace(id=1, tracking_card_no='RA240001')
    events = []

    class DummyDB:
        def commit(self):
            return None

        def refresh(self, _item):
            return None

    monkeypatch.setattr('app.services.work_order_service._ensure_entry', lambda *_args, **_kwargs: entry)
    monkeypatch.setattr('app.services.work_order_service._ensure_work_order', lambda *_args, **_kwargs: work_order)
    monkeypatch.setattr('app.services.work_order_service._ensure_entry_write_access', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service._recompute_work_order_rollups', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.services.work_order_service.record_entity_change', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        'app.services.work_order_service.apply_entry_submit',
        lambda entity, user_role: setattr(entity, 'entry_status', 'verified'),
    )
    monkeypatch.setattr(
        'app.services.work_order_service._serialize_entry',
        lambda *_args, **_kwargs: {'id': 9, 'entry_status': entry.entry_status},
    )
    monkeypatch.setattr(
        'app.services.work_order_service._build_entry_event_payload',
        lambda *_args, **_kwargs: ('entry_verified', {'tracking_card_no': 'RA240001'}),
    )
    monkeypatch.setattr(
        'app.services.work_order_service.event_bus.publish',
        lambda event_type, payload: events.append((event_type, payload)),
    )

    payload = submit_entry(
        DummyDB(),
        entry_id=9,
        operator=SimpleNamespace(id=2, role='weigher'),
    )

    assert payload == {'id': 9, 'entry_status': 'verified'}
    assert events == [('entry_verified', {'tracking_card_no': 'RA240001'})]
