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


def _scoped_manager_user():
    return SimpleNamespace(
        id=2,
        role='manager',
        is_admin=False,
        is_manager=True,
        is_reviewer=False,
        workshop_id=1,
        team_id=None,
        data_scope_type='self_workshop',
        assigned_shift_ids=[],
    )


def _mobile_user():
    return SimpleNamespace(
        id=3,
        role='machine_operator',
        is_admin=False,
        is_manager=False,
        is_reviewer=False,
        is_mobile_user=True,
        workshop_id=1,
        team_id=None,
        data_scope_type='self_workshop',
        assigned_shift_ids=[],
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
        lambda db, scope=None: {
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
        lambda db, scope=None: [{'workshop_name': '冷轧', 'active_coil_count': 2, 'active_tons': 12.0, 'stalled_count': 0, 'freshness': freshness}],
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.list_machine_lines',
        lambda db, scope=None: [
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
        lambda db, scope=None, **kwargs: [{'coil_key': 'MES:1', 'tracking_card_no': 'BN-1', 'current_process': '轧制', 'next_process': '退火', 'destination': {'kind': 'in_progress'}}],
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.get_coil_flow',
        lambda db, *, coil_key, scope=None: {'coil_key': coil_key, 'previous_process': '铸轧', 'current_process': '轧制', 'next_process': '退火', 'destination': {'kind': 'in_progress'}, 'freshness': freshness},
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.build_cost_benefit',
        lambda db, scope=None: {'freshness': freshness, 'label': '经营估算', 'estimated_cost': None, 'estimated_gross_margin': None, 'missing_data': ['cost_inputs']},
    )
    monkeypatch.setattr(
        'app.routers.factory_command.factory_command_service.list_destinations',
        lambda db, scope=None: [{'kind': 'in_progress', 'label': '在制', 'coil_count': 1, 'tons': 12.0, 'freshness': freshness}],
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


def test_factory_command_routes_pass_data_scope(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _scoped_manager_user

    def scoped_coils(_db, *, scope=None, **kwargs):
        assert scope is not None
        assert scope.data_scope_type == 'self_workshop'
        assert scope.workshop_id == 1
        return []

    monkeypatch.setattr('app.routers.factory_command.factory_command_service.list_coils', scoped_coils)

    response = TestClient(app).get('/api/v1/factory-command/coils')

    assert response.status_code == 200


def test_factory_command_coils_route_passes_filters_and_paging(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _scoped_manager_user
    seen = {}

    def scoped_coils(_db, *, scope=None, limit=100, offset=0, workshop=None, destination=None, query=None):
        seen.update(
            {
                'scope': scope,
                'limit': limit,
                'offset': offset,
                'workshop': workshop,
                'destination': destination,
                'query': query,
            }
        )
        return []

    monkeypatch.setattr('app.routers.factory_command.factory_command_service.list_coils', scoped_coils)

    response = TestClient(app).get('/api/v1/factory-command/coils?limit=20&offset=40&workshop=冷轧&destination=in_progress&query=BN')

    assert response.status_code == 200
    assert seen['scope'].data_scope_type == 'self_workshop'
    assert seen['limit'] == 20
    assert seen['offset'] == 40
    assert seen['workshop'] == '冷轧'
    assert seen['destination'] == 'in_progress'
    assert seen['query'] == 'BN'


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
            'error_message': 'vendor url timeout',
        },
    )

    response = TestClient(app).get('/api/v1/mes/sync-status')

    assert response.status_code == 200
    assert response.json()['lag_seconds'] == 60
    assert response.json()['error_message'] is None


def test_mes_sync_status_rejects_non_manager(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role='mobile', is_admin=False, is_manager=False, is_reviewer=False)
    monkeypatch.setattr('app.routers.mes.mes_sync_service.latest_sync_status', lambda db: {})

    response = TestClient(app).get('/api/v1/mes/sync-status')

    assert response.status_code == 403


def test_mobile_flow_suggestion_uses_mobile_authorized_endpoint(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _mobile_user

    def fake_suggestion(_db, *, tracking_card_no, scope=None):
        assert tracking_card_no == 'BN-1'
        assert scope.data_scope_type == 'self_workshop'
        return {
            'coil_key': 'MES:1',
            'tracking_card_no': 'BN-1',
            'previous_process': '铸轧',
            'current_process': '轧制',
            'next_process': '退火',
            'destination': {'kind': 'in_progress'},
        }

    monkeypatch.setattr('app.routers.mobile.factory_command_service.find_coil_flow_suggestion', fake_suggestion)

    response = TestClient(app).get('/api/v1/mobile/coil-flow-suggestion', params={'tracking_card_no': 'BN-1'})

    assert response.status_code == 200
    assert response.json()['next_process'] == '退火'


def test_mobile_flow_suggestion_preserves_ambiguous_status(monkeypatch):
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _mobile_user

    monkeypatch.setattr(
        'app.routers.mobile.factory_command_service.find_coil_flow_suggestion',
        lambda _db, *, tracking_card_no, scope=None: {
            'tracking_card_no': tracking_card_no,
            'destination': {},
            'flow_source': 'manual_pending_match',
            'match_status': 'ambiguous',
            'candidate_count': 2,
        },
    )

    response = TestClient(app).get('/api/v1/mobile/coil-flow-suggestion', params={'tracking_card_no': 'BN-1'})

    assert response.status_code == 200
    assert response.json()['flow_source'] == 'manual_pending_match'
    assert response.json()['match_status'] == 'ambiguous'
