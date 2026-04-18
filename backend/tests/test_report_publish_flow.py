from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def _fake_report(status: str):
    now = datetime(2026, 3, 25, 9, 0, 0)
    return SimpleNamespace(
        id=5,
        report_date=date(2026, 3, 25),
        report_type='production',
        workshop_id=None,
        report_data={'total_output_weight': 88.8},
        text_summary='2026-03-25 production stable.',
        generated_scope='confirmed_only',
        output_mode='both',
        status=status,
        generated_at=now,
        reviewed_by=1 if status in {'reviewed', 'published'} else None,
        reviewed_at=now if status in {'reviewed', 'published'} else None,
        published_by=1 if status == 'published' else None,
        published_at=now if status == 'published' else None,
        created_at=now,
        updated_at=now,
    )


def test_report_review_publish_endpoints(monkeypatch) -> None:
    calls: list[str] = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_review_report(db, *, report_id, operator, note=None):
        assert report_id == 5
        assert operator.id == 1
        assert note == 'ready for publish'
        calls.append('review')
        return _fake_report('reviewed')

    def fake_publish_report(db, *, report_id, operator, note=None):
        assert report_id == 5
        assert operator.id == 1
        assert note == 'final release'
        calls.append('publish')
        return _fake_report('published')

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.reports.report_service.review_report', fake_review_report)
    monkeypatch.setattr('app.routers.reports.report_service.publish_report', fake_publish_report)

    client = TestClient(app)
    review_resp = client.post('/api/v1/reports/5/review', json={'note': 'ready for publish'})
    publish_resp = client.post('/api/v1/reports/5/publish', json={'note': 'final release'})

    assert review_resp.status_code == 200
    assert review_resp.json()['status'] == 'reviewed'
    assert publish_resp.status_code == 200
    assert publish_resp.json()['status'] == 'published'
    assert calls == ['review', 'publish']

    app.dependency_overrides.clear()
