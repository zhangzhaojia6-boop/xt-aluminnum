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


def _raise_value_error(*_args, **_kwargs):
    raise ValueError('boom')


def _assert_report_value_error_maps_to_400(
    monkeypatch,
    *,
    service_name: str,
    path: str,
    payload: dict,
    user: User,
) -> None:
    monkeypatch.setattr(f'app.routers.reports.report_service.{service_name}', _raise_value_error)
    _override_user(user)

    response = TestClient(app, raise_server_exceptions=False).post(path, json=payload)

    assert response.status_code == 400
    assert response.json()['detail'] == 'boom'


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


def test_template_daily_preview_rejects_fill_only_user_before_service_call(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.routers.reports.template_daily_report.build_template_daily_report_payload',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('service should not run')),
    )
    _override_user(_user('machine_operator', is_reviewer=False, is_manager=False))

    response = TestClient(app).post('/api/v1/reports/template-daily/preview', json={'target_date': '2026-06-16'})

    assert response.status_code == 403
    assert response.json()['detail'] == 'Report publish access denied'


def test_template_daily_preview_allows_manager_role(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.routers.reports.template_daily_report.build_template_daily_report_payload',
        lambda *_args, **_kwargs: {
            'status': 'blocked',
            'text': None,
            'missing_fields': ['total_electricity_kwh'],
            'conflicts': [],
            'sources': {},
        },
    )
    _override_user(_user('manager', is_reviewer=False, is_manager=True))

    response = TestClient(app).post('/api/v1/reports/template-daily/preview', json={'target_date': '2026-06-16'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'blocked'
    assert payload['missing_fields'] == ['total_electricity_kwh']
    assert payload['missing_field_groups'] == {'energy': ['total_electricity_kwh']}


def test_report_generate_maps_value_error_to_400(monkeypatch) -> None:
    _assert_report_value_error_maps_to_400(
        monkeypatch,
        service_name='generate_daily_reports',
        path='/api/v1/reports/generate',
        payload={'report_date': '2026-03-25', 'report_type': 'production'},
        user=_user('admin', is_reviewer=True, is_manager=True),
    )


def test_report_review_maps_value_error_to_400(monkeypatch) -> None:
    _assert_report_value_error_maps_to_400(
        monkeypatch,
        service_name='review_report',
        path='/api/v1/reports/5/review',
        payload={'note': 'x'},
        user=_user('reviewer', is_reviewer=True, is_manager=False),
    )


def test_report_publish_maps_value_error_to_400(monkeypatch) -> None:
    _assert_report_value_error_maps_to_400(
        monkeypatch,
        service_name='publish_report',
        path='/api/v1/reports/5/publish',
        payload={'note': 'x'},
        user=_user('manager', is_reviewer=False, is_manager=True),
    )


def test_report_finalize_maps_value_error_to_400(monkeypatch) -> None:
    _assert_report_value_error_maps_to_400(
        monkeypatch,
        service_name='finalize_report',
        path='/api/v1/reports/5/finalize',
        payload={'note': 'x', 'force': False},
        user=_user('manager', is_reviewer=False, is_manager=True),
    )


def test_daily_pipeline_maps_value_error_to_400(monkeypatch) -> None:
    _assert_report_value_error_maps_to_400(
        monkeypatch,
        service_name='run_daily_pipeline',
        path='/api/v1/reports/run-daily-pipeline',
        payload={'report_date': '2026-03-25'},
        user=_user('manager', is_reviewer=False, is_manager=True),
    )
