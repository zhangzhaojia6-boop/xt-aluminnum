from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


def test_daily_production_mapping_preview_route_is_retired() -> None:
    fake_db = object()

    def fake_get_db():
        yield fake_db

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    try:
        client = TestClient(app)
        response = client.get('/api/v1/imports/daily-production/mapping-preview?batch_id=7')

        assert response.status_code == 410
        assert response.json()['detail'] == '每日产量导入映射预览已停用，请使用移动端每日填报。'
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
