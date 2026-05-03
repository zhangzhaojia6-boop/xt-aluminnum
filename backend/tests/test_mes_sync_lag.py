from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy.exc import ProgrammingError

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


class _RaisingQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        raise ProgrammingError('SELECT mes_coil_snapshots.mes_product_id', {}, Exception('no such column: mes_product_id'))

    def first(self):
        raise AssertionError('projection query should fail before first()')


class _MigrationMissingDB(_FakeDB):
    def query(self, model):
        if model is mes_sync_service.MesCoilSnapshot:
            return _RaisingQuery()
        return super().query(model)


def test_compute_sync_lag_seconds_prefers_cursor():
    cursor = SimpleNamespace(last_event_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC))
    db = _FakeDB(cursor=cursor)

    lag = mes_sync_service.compute_sync_lag_seconds(db, now=datetime(2026, 4, 11, 2, 5, tzinfo=UTC))

    assert lag == 300.0


def test_latest_sync_status_exposes_last_run_fields(monkeypatch):
    monkeypatch.setattr(mes_sync_service.settings, 'MES_ADAPTER', 'rest_api')
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


def test_latest_sync_status_reports_unconfigured_without_querying(monkeypatch):
    class NoQueryDB:
        def query(self, model):  # pragma: no cover - should never be called
            raise AssertionError(model)

    monkeypatch.setattr(mes_sync_service.settings, 'MES_ADAPTER', 'null')

    payload = mes_sync_service.latest_sync_status(NoQueryDB())

    assert payload['configured'] is False
    assert payload['migration_ready'] is True
    assert payload['status'] == 'unconfigured'
    assert payload['source'] == 'local_entry'
    assert payload['action_required'] == 'configure_mes'


def test_latest_sync_status_reports_projection_migration_missing(monkeypatch):
    monkeypatch.setattr(mes_sync_service.settings, 'MES_ADAPTER', 'rest_api')
    db = _MigrationMissingDB(cursor=None, run_log=None)

    payload = mes_sync_service.latest_sync_status(db, now=datetime(2026, 4, 11, 2, 6, tzinfo=UTC))

    assert payload['configured'] is True
    assert payload['migration_ready'] is False
    assert payload['status'] == 'migration_missing'
    assert payload['source'] == 'local_entry'
    assert payload['action_required'] == 'run_migration'
    assert payload['lag_seconds'] is None


def test_latest_sync_status_reports_failed_run(monkeypatch):
    monkeypatch.setattr(mes_sync_service.settings, 'MES_ADAPTER', 'rest_api')
    cursor = SimpleNamespace(cursor_value='cursor-2', last_event_at=datetime(2026, 4, 11, 2, 0, tzinfo=UTC), last_synced_at=datetime(2026, 4, 11, 2, 5, tzinfo=UTC))
    run_log = SimpleNamespace(
        status='failed',
        started_at=datetime(2026, 4, 11, 2, 4, tzinfo=UTC),
        finished_at=datetime(2026, 4, 11, 2, 5, tzinfo=UTC),
        fetched_count=0,
        upserted_count=0,
        replayed_count=0,
        error_message='vendor url timeout',
    )
    db = _FakeDB(cursor=cursor, run_log=run_log)

    payload = mes_sync_service.latest_sync_status(db, now=datetime(2026, 4, 11, 2, 6, tzinfo=UTC))

    assert payload['configured'] is True
    assert payload['migration_ready'] is True
    assert payload['status'] == 'failed'
    assert payload['last_run_status'] == 'failed'
    assert payload['last_error'] == 'vendor url timeout'
    assert payload['action_required'] == 'check_vendor'
