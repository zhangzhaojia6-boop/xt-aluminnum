from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_daily_pipeline_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=3, username='boss', password_hash='x', name='Boss', role='admin', is_active=True)

    def fake_run_pipeline(db, *, report_date, scope, output_mode, force, operator):
        assert report_date == date(2026, 3, 25)
        assert scope == 'include_reviewed'
        assert output_mode == 'both'
        assert force is False
        assert operator.id == 3
        report = SimpleNamespace(
            id=21,
            report_date=report_date,
            report_type='production',
            workshop_id=None,
            report_data={'total_output_weight': 200.0},
            text_summary='summary',
            generated_scope=scope,
            output_mode=output_mode,
            status='draft',
            generated_at=datetime(2026, 3, 25, 8, 0, 0),
            reviewed_by=None,
            reviewed_at=None,
            published_by=None,
            published_at=None,
            final_text_summary='boss summary',
            final_confirmed_by=None,
            final_confirmed_at=None,
            is_final_version=False,
            created_at=datetime(2026, 3, 25, 8, 0, 0),
            updated_at=datetime(2026, 3, 25, 8, 0, 0),
        )
        return False, None, 0, True, 'boss summary', [report]

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reports.report_service.run_daily_pipeline', fake_run_pipeline)

    client = TestClient(app)
    response = client.post(
        '/api/v1/reports/run-daily-pipeline',
        json={'report_date': '2026-03-25', 'scope': 'include_reviewed', 'output_mode': 'both', 'force': False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body['blocked'] is False
    assert body['reports'][0]['id'] == 21
    assert body['boss_text_summary'] == 'boss summary'

    app.dependency_overrides.clear()
