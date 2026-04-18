from types import SimpleNamespace
from datetime import date
import json

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User
from app.services import mes_service


class DummyDB:
    pass


def test_mes_import_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_import_mes_export(db, *, upload_file, current_user):
        assert current_user.id == 1
        assert upload_file.filename == 'mes_export.csv'
        return SimpleNamespace(
            batch_id=301,
            batch_no='IMP-MES-301',
            import_type='mes_export',
            summary={
                'batch_no': 'IMP-MES-301',
                'total_rows': 1,
                'success_rows': 1,
                'failed_rows': 0,
                'columns': ['business_date', 'workshop_code', 'shift_code', 'metric_code', 'metric_name', 'metric_value'],
            },
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.mes.mes_service.import_mes_export', fake_import_mes_export)

    client = TestClient(app)
    response = client.post(
        '/api/v1/mes/import',
        files={
            'file': (
                'mes_export.csv',
                b'business_date,workshop_code,shift_code,metric_code,metric_name,metric_value\n2026-03-25,W1,A,output_weight,\xe4\xba\xa7\xe9\x87\x8f,120\n',
                'text/csv',
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body['batch_id'] == 301
    assert body['import_type'] == 'mes_export'
    assert body['summary']['success_rows'] == 1

    app.dependency_overrides.clear()


def test_mes_import_normalizes_mapped_data_for_json_storage() -> None:
    payload = {'business_date': date(2026, 4, 1), 'metric_value': 1150.0}
    normalized = mes_service._normalize_mapped_data(payload)

    assert normalized['business_date'] == '2026-04-01'
    assert normalized['metric_value'] == 1150.0
    json.dumps(normalized)
