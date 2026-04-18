from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_production_import_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_import_shift_production_data(db, *, upload_file, current_user, template_code=None, duplicate_strategy='reject'):
        assert current_user.id == 1
        assert upload_file.filename == 'production_sample.csv'
        assert duplicate_strategy == 'reject'
        return SimpleNamespace(
            batch_id=101,
            batch_no='IMP-TEST-101',
            import_type='production_shift',
            summary={
                'batch_no': 'IMP-TEST-101',
                'total_rows': 2,
                'success_rows': 2,
                'failed_rows': 0,
                'skipped_rows': 0,
                'columns': ['business_date', 'shift_code'],
            },
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.production.production_service.import_shift_production_data', fake_import_shift_production_data)

    client = TestClient(app)
    response = client.post(
        '/api/v1/production/import',
        files={'file': ('production_sample.csv', b'business_date,shift_code\n2026-03-25,A\n', 'text/csv')},
    )

    assert response.status_code == 200
    body = response.json()
    assert body['batch_id'] == 101
    assert body['import_type'] == 'production_shift'
    assert body['summary']['success_rows'] == 2

    app.dependency_overrides.clear()
