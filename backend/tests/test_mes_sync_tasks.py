import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.adapters import NullMesAdapter, get_mes_adapter, set_mes_adapter
from app.services import mes_sync_service
from app.tasks import mes_sync as mes_sync_tasks


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _ConfiguredAdapter(NullMesAdapter):
    pass


def test_mes_sync_task_initializes_configured_adapter_when_run_standalone(monkeypatch) -> None:
    original_adapter = get_mes_adapter()
    session = _FakeSession()
    configured_adapter = _ConfiguredAdapter()
    monkeypatch.setattr(mes_sync_tasks, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(mes_sync_tasks.settings, 'MES_ADAPTER', 'sqlserver')
    monkeypatch.setattr(mes_sync_tasks, 'create_mes_adapter', lambda: configured_adapter)
    set_mes_adapter(NullMesAdapter())

    try:
        result = mes_sync_tasks._run_sync_group(lambda _service, _session: {'adapter': type(get_mes_adapter()).__name__})
    finally:
        set_mes_adapter(original_adapter)

    assert result == {'adapter': '_ConfiguredAdapter'}
    assert get_mes_adapter() is original_adapter
    assert session.commits == 1


def test_mes_sync_task_commits_failed_vendor_run_log(monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(mes_sync_tasks, 'get_sessionmaker', lambda: lambda: session)

    def vendor_failure(_service, _session):
        raise mes_sync_service.MesSyncVendorError('temporary vendor outage')

    with pytest.raises(RuntimeError, match='temporary vendor outage'):
        mes_sync_tasks._run_sync_group(vendor_failure)

    assert session.commits == 1
    assert session.rollbacks == 0


def test_mes_sync_task_rolls_back_database_errors(monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(mes_sync_tasks, 'get_sessionmaker', lambda: lambda: session)

    def database_failure(_service, _session):
        raise SQLAlchemyError('database unavailable')

    with pytest.raises(SQLAlchemyError, match='database unavailable'):
        mes_sync_tasks._run_sync_group(database_failure)

    assert session.commits == 0
    assert session.rollbacks == 1


def test_mes_sync_task_rolls_back_unknown_errors(monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(mes_sync_tasks, 'get_sessionmaker', lambda: lambda: session)

    def unknown_failure(_service, _session):
        raise RuntimeError('unexpected transform failure')

    with pytest.raises(RuntimeError, match='unexpected transform failure'):
        mes_sync_tasks._run_sync_group(unknown_failure)

    assert session.commits == 0
    assert session.rollbacks == 1


def test_mes_sync_task_publishes_realtime_event_after_commit(monkeypatch) -> None:
    session = _FakeSession()
    published = []
    monkeypatch.setattr(mes_sync_tasks, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(mes_sync_tasks, '_publish_sync_event', lambda result: published.append(result))

    result = mes_sync_tasks._run_sync_group(
        lambda _service, _session: {'projection': [{'cursor_key': 'mes_workshop_process_records', 'status': 'success'}]}
    )

    assert session.commits == 1
    assert session.rollbacks == 0
    assert published == [result]
