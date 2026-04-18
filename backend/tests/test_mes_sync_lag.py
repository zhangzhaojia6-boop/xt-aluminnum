from datetime import UTC, datetime
from types import SimpleNamespace

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
    def __init__(self, cursor=None, snapshot=None, run_log=None):
        self._cursor = cursor
        self._snapshot = snapshot
        self._run_log = run_log

    def query(self, model):
        if model is mes_sync_service.MesSyncCursor:
            return _FakeQuery(self._cursor)
        if model is mes_sync_service.MesCoilSnapshot:
            return _FakeQuery(self._snapshot)
        if model is mes_sync_service.MesSyncRunLog:
            return _FakeQuery(self._run_log)
        raise AssertionError(model)


def test_compute_sync_lag_seconds_prefers_cursor():
    cursor = SimpleNamespace(last_event_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC))
    db = _FakeDB(cursor=cursor)

    lag = mes_sync_service.compute_sync_lag_seconds(db, now=datetime(2026, 4, 11, 2, 5, tzinfo=UTC))

    assert lag == 300.0


def test_latest_sync_status_exposes_last_run_fields():
    cursor = SimpleNamespace(cursor_value='cursor-2', last_event_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC), last_synced_at=datetime(2026, 4, 11, 2, 5, tzinfo=UTC))
    run_log = SimpleNamespace(
        status='success',
        started_at=datetime(2026, 4, 11, 2, 4, tzinfo=UTC),
        finished_at=datetime(2026, 4, 11, 2, 5, tzinfo=UTC),
        fetched_count=10,
        upserted_count=8,
        replayed_count=2,
        error_message=None,
    )
    db = _FakeDB(cursor=cursor, run_log=run_log)

    payload = mes_sync_service.latest_sync_status(db, now=datetime(2026, 4, 11, 2, 6, tzinfo=UTC))

    assert payload['cursor_value'] == 'cursor-2'
    assert payload['last_run_status'] == 'success'
    assert payload['lag_seconds'] == 360.0

