from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_production_import_endpoint_is_disabled() -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    response = client.post(
        '/api/v1/production/import',
        files={'file': ('production_sample.csv', b'business_date,shift_code\n2026-03-25,A\n', 'text/csv')},
    )

    assert response.status_code == 410
    assert response.json()['detail'] == '生产导入功能已停用，请使用移动端每日填报。'

    app.dependency_overrides.clear()
