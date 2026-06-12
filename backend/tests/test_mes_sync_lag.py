from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.mes import MesSyncRunLog
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


class _MissingCursorTableDB(_FakeDB):
    def query(self, model):
        if model is mes_sync_service.MesSyncCursor:
            raise OperationalError('SELECT mes_sync_cursors.cursor_key', {}, Exception('no such table: mes_sync_cursors'))
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


def test_latest_sync_status_treats_recent_successful_sync_as_fresh_even_when_source_data_is_idle(monkeypatch):
    monkeypatch.setattr(mes_sync_service.settings, 'MES_ADAPTER', 'rest_api')
    cursor = SimpleNamespace(
        cursor_value='cursor-2',
        last_event_at=datetime(2026, 4, 11, 1, 0, tzinfo=UTC),
        last_synced_at=datetime(2026, 4, 11, 2, 5, tzinfo=UTC),
    )
    run_log = SimpleNamespace(
        status='success',
        started_at=datetime(2026, 4, 11, 2, 4, tzinfo=UTC),
        finished_at=datetime(2026, 4, 11, 2, 5, tzinfo=UTC),
        fetched_count=0,
        upserted_count=0,
        replayed_count=0,
        error_message=None,
    )
    db = _FakeDB(cursor=cursor, run_log=run_log)

    payload = mes_sync_service.latest_sync_status(db, now=datetime(2026, 4, 11, 2, 6, tzinfo=UTC))

    assert payload['lag_seconds'] == 3960.0
    assert payload['sync_freshness_seconds'] == 60.0
    assert payload['status'] == 'fresh'
    assert payload['action_required'] == 'none'


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


def test_latest_sync_status_reports_migration_missing_when_cursor_table_is_missing(monkeypatch):
    monkeypatch.setattr(mes_sync_service.settings, 'MES_ADAPTER', 'rest_api')
    db = _MissingCursorTableDB()

    payload = mes_sync_service.latest_sync_status(db, now=datetime(2026, 4, 11, 2, 6, tzinfo=UTC))

    assert payload['configured'] is True
    assert payload['migration_ready'] is False
    assert payload['status'] == 'migration_missing'
    assert payload['action_required'] == 'run_migration'


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


def test_recent_sync_runs_returns_newest_first_summary_and_duration(tmp_path, monkeypatch):
    monkeypatch.setattr(mes_sync_service.settings, 'MES_ADAPTER', 'rest_api')
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-sync-runs.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesSyncRunLog.__table__])
    db = sessionmaker(bind=engine, future=True)()
    try:
        db.add_all(
            [
                MesSyncRunLog(
                    cursor_key='coil_snapshots',
                    started_at=datetime(2026, 5, 7, 1, 0, tzinfo=UTC),
                    finished_at=datetime(2026, 5, 7, 1, 0, 8, tzinfo=UTC),
                    status='success',
                    fetched_count=50,
                    upserted_count=50,
                    replayed_count=0,
                    lag_seconds=12.5,
                ),
                MesSyncRunLog(
                    cursor_key='coil_snapshots',
                    started_at=datetime(2026, 5, 7, 1, 1, tzinfo=UTC),
                    finished_at=datetime(2026, 5, 7, 1, 1, 13, tzinfo=UTC),
                    status='failed',
                    fetched_count=0,
                    upserted_count=0,
                    replayed_count=0,
                    lag_seconds=45.25,
                    error_message='vendor timeout',
                ),
                MesSyncRunLog(
                    cursor_key='mes_dispatch',
                    started_at=datetime(2026, 5, 7, 1, 2, tzinfo=UTC),
                    finished_at=datetime(2026, 5, 7, 1, 2, 3, tzinfo=UTC),
                    status='success',
                    fetched_count=12,
                    upserted_count=11,
                ),
            ]
        )
        db.commit()

        payload = mes_sync_service.recent_sync_runs(db, limit=2)

        assert payload['cursor_key'] == 'coil_snapshots'
        assert payload['summary'] == {
            'total_count': 2,
            'success_count': 1,
            'failed_count': 1,
            'running_count': 0,
            'latest_status': 'failed',
        }
        assert [item['status'] for item in payload['items']] == ['failed', 'success']
        assert payload['items'][0]['duration_seconds'] == 13.0
        assert payload['items'][0]['lag_seconds'] == 45.25
        assert payload['items'][0]['error_message'] == 'vendor timeout'
        assert payload['items'][1]['duration_seconds'] == 8.0
        assert payload['items'][1]['fetched_count'] == 50
    finally:
        db.close()
