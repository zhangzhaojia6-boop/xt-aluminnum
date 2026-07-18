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
    published = []
    monkeypatch.setattr(mes_sync_tasks, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(
        mes_sync_tasks,
        '_publish_sync_event',
        lambda event_type, payload: published.append((event_type, payload)),
    )

    def vendor_failure(_service, _session):
        raise mes_sync_service.MesSyncVendorError(
            'temporary vendor outage password=must-not-leak',
            cursor_key='coil_snapshots',
            attempt_count=3,
            failure_kind='connection_failed',
        )

    with pytest.raises(RuntimeError, match='temporary vendor outage'):
        mes_sync_tasks._run_sync_group(vendor_failure)

    assert session.commits == 1
    assert session.rollbacks == 0
    assert published[0][0] == 'mes_sync_failed'
    assert published[0][1]['steps'] == [
        {
            'cursor_key': 'coil_snapshots',
            'status': 'failed',
            'attempt_count': 3,
            'failure_kind': 'connection_failed',
            'recovered': False,
            'action': 'check_mes_connection',
        }
    ]
    assert 'must-not-leak' not in str(published)


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
    monkeypatch.setattr(
        mes_sync_tasks,
        '_publish_sync_event',
        lambda event_type, payload: published.append((event_type, payload)),
    )

    result = mes_sync_tasks._run_sync_group(
        lambda _service, _session: {'projection': [{'cursor_key': 'mes_workshop_process_records', 'status': 'success'}]}
    )

    assert session.commits == 1
    assert session.rollbacks == 0
    assert published == [('mes_sync_completed', {'result': result})]


def test_mes_sync_task_publishes_failed_and_recovered_signals_without_error_text(monkeypatch) -> None:
    session = _FakeSession()
    published = []
    monkeypatch.setattr(mes_sync_tasks, 'get_sessionmaker', lambda: lambda: session)
    monkeypatch.setattr(
        mes_sync_tasks,
        '_publish_sync_event',
        lambda event_type, payload: published.append((event_type, payload)),
    )
    result = {
        'projection': [
            {
                'cursor_key': 'mes_dispatch',
                'status': 'success',
                'attempt_count': 2,
                'failure_kind': 'query_timeout',
                'recovered': True,
                'error_message': 'token=must-not-leak',
            },
            {
                'cursor_key': 'mes_stock',
                'status': 'failed',
                'attempt_count': 3,
                'failure_kind': 'schema_changed',
                'recovered': False,
                'error_message': 'password=must-not-leak',
            },
        ]
    }

    assert mes_sync_tasks._run_sync_group(lambda _service, _session: result) == result

    assert [item[0] for item in published] == [
        'mes_sync_completed',
        'mes_sync_failed',
        'mes_sync_recovered',
    ]
    assert published[1][1]['steps'][0]['failure_kind'] == 'schema_changed'
    assert published[1][1]['steps'][0]['action'] == 'check_mes_schema'
    assert published[2][1]['steps'][0]['failure_kind'] == 'query_timeout'
    assert published[2][1]['steps'][0]['action'] == 'check_mes_timeout'
    assert 'must-not-leak' not in str(published)


def test_publish_sync_event_forwards_to_persistent_database_event_bus(monkeypatch) -> None:
    from app.core import event_bus as event_bus_module

    published = []
    def publish(event_type, payload):
        published.append((event_type, payload))
        return {'id': 17, 'event_type': event_type, 'payload': payload}

    monkeypatch.setattr(event_bus_module.event_bus, 'publish', publish)

    event = mes_sync_tasks._publish_sync_event(
        'mes_sync_recovered',
        {
            'steps': [
                {
                    'cursor_key': 'mes_dispatch',
                    'status': 'success',
                    'attempt_count': 2,
                    'failure_kind': 'query_timeout',
                    'recovered': True,
                    'action': 'check_mes_timeout',
                }
            ]
        },
    )

    assert published[0][0] == 'mes_sync_recovered'
    assert published[0][1]['source'] == 'mes_projection'
    assert published[0][1]['steps'][0]['failure_kind'] == 'query_timeout'
    assert event['id'] == 17
