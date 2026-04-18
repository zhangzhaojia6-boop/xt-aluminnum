from datetime import date

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_energy_summary_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=8, username='energy', password_hash='x', name='Energy', role='admin', is_active=True)

    def fake_summary(db, *, business_date=None, workshop_id=None, shift_config_id=None):
        assert business_date == date(2026, 3, 25)
        assert workshop_id is None
        assert shift_config_id is None
        return [
            {
                'business_date': date(2026, 3, 25),
                'workshop_id': 1,
                'workshop_code': 'W1',
                'shift_config_id': 2,
                'shift_code': 'A',
                'electricity_value': 100.0,
                'gas_value': 20.0,
                'water_value': 10.0,
                'total_energy': 130.0,
                'output_weight': 50.0,
                'energy_per_ton': 2.6,
            }
        ]

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', fake_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25'})

    assert response.status_code == 200
    body = response.json()
    assert body[0]['workshop_code'] == 'W1'
    assert body[0]['energy_per_ton'] == 2.6

    app.dependency_overrides.clear()
