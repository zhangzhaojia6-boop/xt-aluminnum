from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_reconciliation_dimension_key(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=4, username='stat', password_hash='x', name='Stat', role='stat', is_active=True)

    def fake_generate(db, *, business_date, reconciliation_type, operator):
        assert business_date == date(2026, 3, 25)
        assert reconciliation_type == 'energy_vs_production'
        assert operator.id == 4
        return [
            SimpleNamespace(
                id=31,
                business_date=business_date,
                reconciliation_type='energy_vs_production',
                source_a='energy',
                source_b='shift_production_data',
                dimension_key='workshop:W1|shift:A',
                field_name='energy_total',
                source_a_value='120',
                source_b_value='100',
                diff_value=20.0,
                status='open',
                resolved_by=None,
                resolved_at=None,
                resolve_note=None,
                created_at=datetime(2026, 3, 25, 10, 0, 0),
                updated_at=datetime(2026, 3, 25, 10, 0, 0),
            )
        ]

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reconciliation.reconciliation_service.generate_reconciliation', fake_generate)

    client = TestClient(app)
    response = client.post(
        '/api/v1/reconciliation/generate',
        json={'business_date': '2026-03-25', 'reconciliation_type': 'energy_vs_production'},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]['dimension_key'].startswith('workshop:')

    app.dependency_overrides.clear()
