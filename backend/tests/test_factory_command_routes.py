from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app


class _DummyDB:
    pass


def _manager_user():
    return SimpleNamespace(
        id=1,
        role='manager',
        is_admin=False,
        is_manager=True,
        is_reviewer=False,
        data_scope_type='all',
    )


def _fake_db():
    yield _DummyDB()


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_factory_command_routes_are_registered(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _manager_user

    freshness = {'status': 'fresh', 'lag_seconds': 30, 'last_synced_at': '2026-05-02T08:00:00+00:00', 'source': 'mes_projection'}
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.build_overview',
        lambda db: {
            'freshness': freshness,
            'wip_tons': 12.0,
            'today_output_tons': 3.0,
            'stock_tons': 4.0,
            'abnormal_count': 1,
            'cost_estimate': {'label': '经营估算', 'estimated_cost': None, 'estimated_gross_margin': None},
            'missing_data': ['cost_inputs'],
        },
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.list_workshops',
        lambda db: [{'workshop_name': '冷轧', 'active_coil_count': 2, 'active_tons': 12.0, 'stalled_count': 0, 'freshness': freshness}],
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.list_machine_lines',
        lambda db: [
            {
                'line_code': '冷轧:01',
                'line_name': '1#轧机',
                'workshop_name': '冷轧',
                'active_coil_count': 2,
                'active_tons': 12.0,
                'finished_tons': 0.0,
                'stalled_count': 0,
                'cost_estimate': {'label': '经营估算'},
                'margin_estimate': {'label': '毛差估算'},
                'freshness': freshness,
            }
        ],
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.list_coils',
        lambda db: [{'coil_key': 'MES:1', 'tracking_card_no': 'BN-1', 'current_process': '轧制', 'next_process': '退火', 'destination': {'kind': 'in_progress'}}],
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.get_coil_flow',
        lambda db, *, coil_key: {'coil_key': coil_key, 'previous_process': '铸轧', 'current_process': '轧制', 'next_process': '退火', 'destination': {'kind': 'in_progress'}, 'freshness': freshness},
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.build_cost_benefit',
        lambda db: {'freshness': freshness, 'label': '经营估算', 'estimated_cost': None, 'estimated_gross_margin': None, 'missing_data': ['cost_inputs']},
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.list_destinations',
        lambda db: [{'kind': 'in_progress', 'label': '在制', 'coil_count': 1, 'tons': 12.0, 'freshness': freshness}],
    )

    client = TestClient(app)
    for path in (
        '/api/v1/factory-command/overview',
        '/api/v1/factory-command/workshops',
        '/api/v1/factory-command/machine-lines',
        '/api/v1/factory-command/coils',
        '/api/v1/factory-command/coils/MES:1/flow',
        '/api/v1/factory-command/cost-benefit',
        '/api/v1/factory-command/destinations',
    ):
        response = client.get(path)
        assert response.status_code == 200, path


def test_factory_command_rejects_non_manager(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role='mobile', is_admin=False, is_manager=False)
    monkeypatch.setattr('app.routers.factory_command.factory_command_service.build_overview', lambda db: {})

    response = TestClient(app).get('/api/v1/factory-command/overview')

    assert response.status_code == 403


def test_mes_sync_status_route(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _manager_user
    monkeypatch.setattr(
        'app.routers.mes.mes_sync_service.latest_sync_status',
        lambda db: {
            'cursor_key': 'coil_snapshots',
            'last_synced_at': '2026-05-02T08:00:00+00:00',
            'last_event_at': '2026-05-02T07:59:00+00:00',
            'lag_seconds': 60,
            'fetched_count': 10,
            'upserted_count': 8,
            'replayed_count': 2,
            'next_cursor': 'cursor-2',
            'status': 'success',
            'error_message': None,
        },
    )

    response = TestClient(app).get('/api/v1/mes/sync-status')

    assert response.status_code == 200
    assert response.json()['lag_seconds'] == 60
