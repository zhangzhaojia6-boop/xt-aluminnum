from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def _fake_get_db():
    yield DummyDB()


def _user(role: str, *, is_reviewer: bool = False, is_manager: bool = False) -> User:
    return User(
        id=42,
        username=role,
        password_hash='x',
        name=role,
        role=role,
        is_reviewer=is_reviewer,
        is_manager=is_manager,
        is_active=True,
    )


def _override_user(user: User) -> None:
    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_current_user] = lambda: user


def _fake_report(status: str = 'reviewed') -> SimpleNamespace:
    now = datetime(2026, 3, 25, 9, 0, 0)
    return SimpleNamespace(
        id=5,
        report_date=date(2026, 3, 25),
        report_type='production',
        workshop_id=None,
        report_data={},
        text_summary='summary',
        generated_scope='all',
        output_mode='both',
        status=status,
        generated_at=now,
        reviewed_by=42,
        reviewed_at=now,
        published_by=None,
        published_at=None,
        created_at=now,
        updated_at=now,
    )


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_report_review_rejects_fill_only_user_before_service_call(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.routers.reports.report_service.review_report',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('service should not run')),
    )
    _override_user(_user('machine_operator', is_reviewer=False, is_manager=False))

    response = TestClient(app).post('/api/v1/reports/5/review', json={'note': 'x'})

    assert response.status_code == 403
    assert response.json()['detail'] == 'Report review access denied'


def test_report_review_allows_reviewer_role(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.review_report', lambda *_args, **_kwargs: _fake_report())
    _override_user(_user('reviewer', is_reviewer=True, is_manager=False))

    response = TestClient(app).post('/api/v1/reports/5/review', json={'note': 'x'})

    assert response.status_code == 200


def test_report_publish_rejects_reviewer_without_manager_access(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.routers.reports.report_service.publish_report',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('service should not run')),
    )
    _override_user(_user('reviewer', is_reviewer=True, is_manager=False))

    response = TestClient(app).post('/api/v1/reports/5/publish', json={'note': 'x'})

    assert response.status_code == 403
    assert response.json()['detail'] == 'Report publish access denied'


def test_report_publish_allows_manager_role(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.publish_report', lambda *_args, **_kwargs: _fake_report('published'))
    _override_user(_user('manager', is_reviewer=False, is_manager=True))

    response = TestClient(app).post('/api/v1/reports/5/publish', json={'note': 'x'})

    assert response.status_code == 200
    assert response.json()['status'] == 'published'


def test_daily_pipeline_rejects_fill_only_user_before_service_call(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.routers.reports.report_service.run_daily_pipeline',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('service should not run')),
    )
    _override_user(_user('machine_operator', is_reviewer=False, is_manager=False))

    response = TestClient(app).post('/api/v1/reports/run-daily-pipeline', json={'report_date': '2026-03-25'})

    assert response.status_code == 403
    assert response.json()['detail'] == 'Report publish access denied'


def test_daily_pipeline_allows_manager_role(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.routers.reports.report_service.run_daily_pipeline',
        lambda *_args, **_kwargs: (False, None, 0, True, 'boss summary', [_fake_report('reviewed')]),
    )
    _override_user(_user('manager', is_reviewer=False, is_manager=True))

    response = TestClient(app).post('/api/v1/reports/run-daily-pipeline', json={'report_date': '2026-03-25'})

    assert response.status_code == 200
    assert response.json()['is_final_version'] is True
