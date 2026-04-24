from datetime import date

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.schemas.dashboard import DeliveryStatusOut
from app.models.system import User


class DummyDB:
    pass


def test_delivery_status_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=6, username='stat', password_hash='x', name='Stat', role='stat', is_active=True)

    def fake_delivery_status(db, *, target_date):
        assert target_date == date(2026, 3, 26)
        return {
            'target_date': '2026-03-26',
            'imports_completed': True,
            'reconciliation_open_count': 0,
            'quality_open_count': 1,
            'blocker_count': 0,
            'reports_generated': 3,
            'reports_reviewed_count': 1,
            'reports_published_count': 0,
            'reports_published': 1,
            'reports_published_deprecated': True,
            'delivery_ready': True,
            'missing_steps': [],
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.dashboard.report_service.build_delivery_status', fake_delivery_status)

    client = TestClient(app)
    response = client.get('/api/v1/dashboard/delivery-status', params={'target_date': '2026-03-26'})
    assert response.status_code == 200
    assert response.json()['delivery_ready'] is True
    assert response.json()['reports_reviewed_count'] == 1
    assert response.json()['reports_published_count'] == 0
    parsed = DeliveryStatusOut.model_validate(response.json())
    assert parsed.delivery_ready is True
    assert parsed.reports_generated == 3
    assert parsed.missing_steps == []

    app.dependency_overrides.clear()
