from datetime import date
import json

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User
from app.services import energy_service


class DummyDB:
    pass


def test_energy_import_endpoint_is_disabled() -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=7, username='energy', password_hash='x', name='Energy', role='admin', is_active=True)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    response = client.post(
        '/api/v1/energy/import',
        files={
            'file': (
                'energy_sample.csv',
                b'business_date,workshop_code,shift_code,energy_type,energy_value\n2026-03-25,W1,A,electricity,100\n',
                'text/csv',
            )
        },
    )

    assert response.status_code == 410
    assert response.json()['detail'] == '能耗导入功能已停用，请使用电工/内勤每日填报。'

    app.dependency_overrides.clear()


def test_energy_import_normalizes_mapped_data_for_json_storage() -> None:
    payload = {'business_date': date(2026, 4, 1), 'energy_value': 100.5}
    normalized = energy_service._normalize_mapped_data(payload)

    assert normalized['business_date'] == '2026-04-01'
    assert normalized['energy_value'] == 100.5
    json.dumps(normalized)
