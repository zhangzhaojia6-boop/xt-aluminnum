from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.main import app
from app.models.system import User


def test_yield_rate_deprecation_map_route_allows_manager() -> None:
    def fake_get_user() -> User:
        return User(id=1, username='manager', password_hash='x', name='Manager', role='manager', is_active=True)

    app.dependency_overrides[get_current_user] = fake_get_user

    response = TestClient(app).get('/api/v1/master/yield-rate-deprecation-map')

    assert response.status_code == 200
    payload = response.json()
    assert payload['formal_truth'] == 'yield_matrix_lane'
    assert any(item['surface_id'] == 'live_dashboard.local_yield_recalc' for item in payload['items'])

    app.dependency_overrides.clear()


def test_yield_rate_deprecation_map_route_rejects_reviewer() -> None:
    def fake_get_user() -> User:
        return User(id=2, username='reviewer', password_hash='x', name='Reviewer', role='reviewer', is_active=True)

    app.dependency_overrides[get_current_user] = fake_get_user

    response = TestClient(app).get('/api/v1/master/yield-rate-deprecation-map')

    assert response.status_code == 403

    app.dependency_overrides.clear()
