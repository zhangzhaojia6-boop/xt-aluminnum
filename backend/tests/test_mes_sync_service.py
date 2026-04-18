from datetime import UTC, datetime
from types import SimpleNamespace

from app.adapters.mes_adapter import CoilSnapshot
from app.services import mes_sync_service


class _FakeQuery:
    def __init__(self, value):
        self._value = value

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._value


class _FakeDB:
    def __init__(self):
        self.added = []
        self.cursor = None

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None

    def query(self, model):
        if model is mes_sync_service.MesSyncCursor:
            return _FakeQuery(self.cursor)
        if model is mes_sync_service.MesCoilSnapshot:
            return _FakeQuery(None)
        if model is mes_sync_service.MesSyncRunLog:
            return _FakeQuery(None)
        raise AssertionError(model)


def test_sync_coil_snapshots_updates_cursor_and_stats(monkeypatch):
    db = _FakeDB()
    cursor = SimpleNamespace(cursor_key='coil_snapshots', cursor_value='cursor-1', last_event_at=None, last_synced_at=None, window_started_at=None)
    db.cursor = cursor
    snapshot = CoilSnapshot(
        coil_id='coil-1',
        tracking_card_no='RA260001',
        workshop_code='ZR2',
        process_code='casting',
        machine_code='ZD-1',
        shift_code='A',
        status='in_progress',
        updated_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC),
    )

    monkeypatch.setattr('app.services.mes_sync_service._ensure_cursor', lambda _db, *, cursor_key: cursor)
    monkeypatch.setattr('app.services.mes_sync_service._upsert_snapshot', lambda _db, *, snapshot, synced_at: (True, False))
    monkeypatch.setattr(
        'app.services.mes_sync_service.get_mes_adapter',
        lambda: SimpleNamespace(list_coil_snapshots=lambda **kwargs: ([snapshot], 'cursor-2')),
    )

    payload = mes_sync_service.sync_coil_snapshots(db, now=datetime(2026, 4, 11, 2, 5, tzinfo=UTC))

    assert payload.status == 'success'
    assert payload.fetched_count == 1
    assert payload.upserted_count == 1
    assert payload.next_cursor == 'cursor-2'
    assert cursor.cursor_value == 'cursor-2'

