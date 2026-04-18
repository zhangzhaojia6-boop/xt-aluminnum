from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_finalize_with_force_flag(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=5, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_finalize(db, *, report_id, operator, note=None, force=False):
        assert report_id == 99
        assert operator.id == 5
        assert force is True
        return SimpleNamespace(
            id=99,
            report_date=date(2026, 3, 26),
            report_type='production',
            workshop_id=None,
            report_data={'total_output_weight': 100.0},
            text_summary='summary',
            generated_scope='confirmed_only',
            output_mode='both',
            status='published',
            generated_at=datetime(2026, 3, 26, 8, 0, 0),
            reviewed_by=5,
            reviewed_at=datetime(2026, 3, 26, 9, 0, 0),
            published_by=5,
            published_at=datetime(2026, 3, 26, 10, 0, 0),
            final_text_summary='boss',
            final_confirmed_by=5,
            final_confirmed_at=datetime(2026, 3, 26, 10, 30, 0),
            is_final_version=True,
            quality_gate_status='blocked',
            quality_gate_summary='force publish',
            delivery_ready=False,
            created_at=datetime(2026, 3, 26, 8, 0, 0),
            updated_at=datetime(2026, 3, 26, 10, 30, 0),
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reports.report_service.finalize_report', fake_finalize)

    client = TestClient(app)
    response = client.post('/api/v1/reports/99/finalize', json={'note': 'force', 'force': True})
    assert response.status_code == 200
    assert response.json()['id'] == 99
    assert response.json()['is_final_version'] is True

    app.dependency_overrides.clear()
