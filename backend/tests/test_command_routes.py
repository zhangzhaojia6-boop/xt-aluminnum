from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.main import app


def _override_user(**overrides):
    payload = {
        'id': 1,
        'role': 'manager',
        'is_admin': False,
        'is_manager': True,
        'is_reviewer': True,
        'is_mobile_user': False,
    }
    payload.update(overrides)

    def _user():
        return SimpleNamespace(**payload)

    app.dependency_overrides[get_current_user] = _user


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_command_review_surface_is_surface_scoped() -> None:
    _override_user(is_manager=True, is_reviewer=True, is_mobile_user=False)
    client = TestClient(app)

    response = client.get('/api/v1/command/surface/review')

    assert response.status_code == 200
    payload = response.json()
    assert payload['surface'] == 'review'
    module_ids = {item['module_id'] for item in payload['modules']}
    assert {'01', '05', '07', '08', '09', '10', '11'}.issubset(module_ids)
    assert '16' not in module_ids
    assert '06' not in module_ids
    first_kpi = payload['modules'][0]['kpis'][0]
    assert {'label', 'value', 'unit', 'trend', 'status', 'icon_key'}.issubset(first_kpi)


def test_command_entry_surface_denies_review_only_user() -> None:
    _override_user(is_manager=False, is_reviewer=True, is_mobile_user=False)
    client = TestClient(app)

    response = client.get('/api/v1/command/surface/entry')

    assert response.status_code == 403


def test_admin_command_overview_uses_admin_modules() -> None:
    _override_user(is_admin=True, is_manager=True, is_reviewer=True, is_mobile_user=True)
    client = TestClient(app)

    response = client.get('/api/v1/admin/command-overview')

    assert response.status_code == 200
    payload = response.json()
    assert payload['surface'] == 'admin'
    module_ids = {item['module_id'] for item in payload['modules']}
    assert {'06', '12', '13', '14'} == module_ids


def test_admin_module_overview_endpoints_return_reference_view_models() -> None:
    _override_user(is_admin=True, is_manager=True, is_reviewer=True, is_mobile_user=True)
    client = TestClient(app)

    cases = [
        ('/api/v1/admin/ops-overview', '12', '系统运维与观测'),
        ('/api/v1/admin/governance-overview', '13', '权限与治理中心'),
        ('/api/v1/admin/master-overview', '14', '主数据与模板中心'),
    ]

    for path, module_id, title in cases:
        response = client.get(path)

        assert response.status_code == 200
        payload = response.json()
        assert payload['surface'] == 'admin'
        assert payload['module_id'] == module_id
        assert payload['title'] == title
        assert isinstance(payload['kpis'], list)
        assert isinstance(payload['status_summary'], list)
        assert isinstance(payload['primary_rows'], list)
        assert isinstance(payload['trend_series'], list)
        assert isinstance(payload['actions'], list)
        assert payload['updated_at']
