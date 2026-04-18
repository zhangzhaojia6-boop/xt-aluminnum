from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_generate_report_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_generate_daily_reports(db, *, report_date, report_type, scope, output_mode, operator):
        assert report_date == date(2026, 3, 25)
        assert report_type == 'production'
        assert scope == 'auto_confirmed'
        assert output_mode == 'both'
        assert operator.id == 1
        return [
            SimpleNamespace(
                id=9,
                report_date=report_date,
                report_type=report_type,
                workshop_id=None,
                report_data={'total_output_weight': 100.5},
                text_summary='summary',
                generated_scope=scope,
                output_mode=output_mode,
                status='draft',
                generated_at=datetime(2026, 3, 25, 8, 0, 0),
                reviewed_by=None,
                reviewed_at=None,
                published_by=None,
                published_at=None,
                created_at=datetime(2026, 3, 25, 8, 0, 0),
                updated_at=datetime(2026, 3, 25, 8, 0, 0),
            )
        ]

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reports.report_service.generate_daily_reports', fake_generate_daily_reports)

    response = TestClient(app).post('/api/v1/reports/generate', json={'report_date': '2026-03-25', 'report_type': 'production'})

    assert response.status_code == 200
    body = response.json()
    assert body['count'] == 1
    assert body['reports'][0]['id'] == 9
    assert body['reports'][0]['report_type'] == 'production'
    assert body['reports'][0]['report_data']['total_output_weight'] == 100.5

    app.dependency_overrides.clear()
