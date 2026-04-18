from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def _fake_report():
    now = datetime(2026, 3, 25, 9, 0, 0)
    return SimpleNamespace(
        id=99,
        report_date=date(2026, 3, 25),
        report_type='production',
        workshop_id=None,
        report_data={'total_output_weight': 123.4, 'total_energy': 88.0},
        text_summary='summary',
        generated_scope='include_reviewed',
        output_mode='both',
        status='published',
        generated_at=now,
        reviewed_by=1,
        reviewed_at=now,
        published_by=1,
        published_at=now,
        final_text_summary='boss summary',
        final_confirmed_by=1,
        final_confirmed_at=now,
        is_final_version=True,
        created_at=now,
        updated_at=now,
    )


def test_report_export_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_get_report(db, *, report_id):
        assert report_id == 99
        return _fake_report()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reports.report_service.get_report', fake_get_report)

    client = TestClient(app)
    json_resp = client.get('/api/v1/reports/99/export', params={'format': 'json'})
    csv_resp = client.get('/api/v1/reports/99/export', params={'format': 'csv'})

    assert json_resp.status_code == 200
    assert json_resp.headers['content-type'].startswith('application/json')
    assert csv_resp.status_code == 200
    assert csv_resp.headers['content-type'].startswith('text/csv')

    app.dependency_overrides.clear()
