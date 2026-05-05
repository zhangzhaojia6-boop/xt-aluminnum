import builtins
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


def _fake_get_user() -> User:
    return User(
        id=1,
        username='admin',
        password_hash='x',
        name='Admin',
        role='admin',
        is_active=True,
    )


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


def _override_admin() -> None:
    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_current_user] = _fake_get_user


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_report_list_endpoint_filters(monkeypatch) -> None:
    captured = {}

    def fake_list_reports(db, *, start_date, end_date, report_type, status):
        captured['start_date'] = start_date
        captured['end_date'] = end_date
        captured['report_type'] = report_type
        captured['status'] = status
        return [_fake_report()]

    _override_admin()
    monkeypatch.setattr('app.routers.reports.report_service.list_reports', fake_list_reports)

    response = TestClient(app).get(
        '/api/v1/reports',
        params={
            'start_date': '2026-03-01',
            'end_date': '2026-03-31',
            'report_type': 'production',
            'status': 'published',
        },
    )

    assert response.status_code == 200
    assert captured == {
        'start_date': date(2026, 3, 1),
        'end_date': date(2026, 3, 31),
        'report_type': 'production',
        'status': 'published',
    }
    assert response.json()[0]['id'] == 99


def test_report_detail_endpoint_hit(monkeypatch) -> None:
    calls = []

    def fake_get_report(db, *, report_id):
        calls.append(report_id)
        return _fake_report()

    _override_admin()
    monkeypatch.setattr('app.routers.reports.report_service.get_report', fake_get_report)

    response = TestClient(app).get('/api/v1/reports/99')

    assert response.status_code == 200
    assert response.json()['id'] == 99
    assert calls == [99]


def test_report_detail_endpoint_404(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.get_report', lambda *_args, **_kwargs: None)
    _override_admin()

    response = TestClient(app).get('/api/v1/reports/404')

    assert response.status_code == 404
    assert response.json()['detail'] == 'report not found'


def test_report_export_endpoint(monkeypatch) -> None:
    def fake_get_report(db, *, report_id):
        assert report_id == 99
        return _fake_report()

    _override_admin()
    monkeypatch.setattr('app.routers.reports.report_service.get_report', fake_get_report)

    client = TestClient(app)
    json_resp = client.get('/api/v1/reports/99/export', params={'format': 'json'})
    csv_resp = client.get('/api/v1/reports/99/export', params={'format': 'csv'})

    assert json_resp.status_code == 200
    assert json_resp.headers['content-type'].startswith('application/json')
    assert csv_resp.status_code == 200
    assert csv_resp.headers['content-type'].startswith('text/csv')


def test_report_export_xlsx_endpoint(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.get_report', lambda *_args, **_kwargs: _fake_report())
    _override_admin()

    response = TestClient(app).get('/api/v1/reports/99/export', params={'format': 'xlsx'})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    assert response.headers['content-disposition'] == 'attachment; filename=report_99.xlsx'
    assert response.content.startswith(b'PK')


def test_report_export_xlsx_missing_pandas_returns_400(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'pandas':
            raise ImportError('no pandas')
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, '__import__', fake_import)
    monkeypatch.setattr('app.routers.reports.report_service.get_report', lambda *_args, **_kwargs: _fake_report())
    _override_admin()

    response = TestClient(app).get('/api/v1/reports/99/export', params={'format': 'xlsx'})

    assert response.status_code == 400
    assert response.json()['detail'] == 'xlsx export not available: no pandas'


def test_report_export_invalid_format_returns_400(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.get_report', lambda *_args, **_kwargs: _fake_report())
    _override_admin()

    response = TestClient(app).get('/api/v1/reports/99/export', params={'format': 'pdf'})

    assert response.status_code == 400
    assert response.json()['detail'] == 'format must be json/csv/xlsx'


def test_report_export_missing_report_returns_404(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.get_report', lambda *_args, **_kwargs: None)
    _override_admin()

    response = TestClient(app).get('/api/v1/reports/404/export', params={'format': 'json'})

    assert response.status_code == 404
    assert response.json()['detail'] == 'report not found'
