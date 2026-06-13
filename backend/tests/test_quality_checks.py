from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User
from app.services import quality_service


class DummyDB:
    pass


def _quality_issue_response(*, status: str, note: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        business_date=date(2026, 3, 26),
        issue_type='missing_data',
        source_type='quality',
        dimension_key='quality',
        field_name='status',
        issue_level='blocker',
        issue_desc='质量问题',
        status=status,
        resolved_by=4,
        resolved_at=datetime(2026, 3, 26, 10, 0, 0),
        resolve_note=note,
        created_at=datetime(2026, 3, 26, 9, 0, 0),
        updated_at=datetime(2026, 3, 26, 10, 0, 0),
    )


def test_quality_run_and_list(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=4, username='qc', password_hash='x', name='QC', role='admin', is_active=True)

    def fake_run(db, *, business_date, operator):
        assert business_date == date(2026, 3, 26)
        assert operator.id == 4
        return [
            SimpleNamespace(
                id=1,
                business_date=business_date,
                issue_type='missing_data',
                source_type='energy',
                dimension_key='energy',
                field_name='energy_value',
                issue_level='blocker',
                issue_desc='当日未导入能耗数据',
                status='open',
                resolved_by=None,
                resolved_at=None,
                resolve_note=None,
                created_at=datetime(2026, 3, 26, 8, 0, 0),
                updated_at=datetime(2026, 3, 26, 8, 0, 0),
            )
        ]

    def fake_list(db, *, business_date=None, issue_type=None, issue_level=None, status=None, issue_id=None):
        assert issue_id is None
        return [
            SimpleNamespace(
                id=2,
                business_date=date(2026, 3, 26),
                issue_type='unreconciled',
                source_type='reconciliation',
                dimension_key='reconciliation',
                field_name='status',
                issue_level='blocker',
                issue_desc='仍有 2 条差异未处理',
                status='open',
                resolved_by=None,
                resolved_at=None,
                resolve_note=None,
                created_at=datetime(2026, 3, 26, 9, 0, 0),
                updated_at=datetime(2026, 3, 26, 9, 0, 0),
            )
        ]

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.quality.quality_service.run_quality_checks', fake_run)
    monkeypatch.setattr('app.routers.quality.quality_service.list_issues', fake_list)

    client = TestClient(app)
    response = client.post('/api/v1/quality/run-checks', json={'business_date': '2026-03-26'})
    assert response.status_code == 200
    assert response.json()[0]['issue_type'] == 'missing_data'

    issues = client.get('/api/v1/quality/issues', params={'business_date': '2026-03-26'})
    assert issues.status_code == 200
    assert issues.json()[0]['issue_type'] == 'unreconciled'

    app.dependency_overrides.clear()


def test_quality_energy_presence_accepts_live_energy_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        quality_service.energy_service,
        'get_energy_summary',
        lambda db, *, business_date: [
            {'electricity_value': 11462.0, 'gas_value': 0.0, 'total_energy': 11462.0}
        ],
    )

    assert quality_service._has_energy_data(DummyDB(), business_date=date(2026, 6, 12), energy_rows=[]) is True


def test_quality_energy_presence_rejects_empty_energy_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        quality_service.energy_service,
        'get_energy_summary',
        lambda db, *, business_date: [
            {'electricity_value': 0.0, 'gas_value': 0.0, 'water_value': 0.0, 'total_energy': 0.0}
        ],
    )

    assert quality_service._has_energy_data(DummyDB(), business_date=date(2026, 6, 12), energy_rows=[]) is False


def test_quality_actions_reject_blank_note(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=4, username='qc', password_hash='x', name='QC', role='admin', is_active=True)

    calls: list[str | None] = []

    def fake_resolve(db, *, issue_id, operator, note=None):
        calls.append(note)
        return _quality_issue_response(status='resolved', note=note)

    def fake_ignore(db, *, issue_id, operator, note=None):
        calls.append(note)
        return _quality_issue_response(status='ignored', note=note)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.quality.quality_service.resolve_issue', fake_resolve)
    monkeypatch.setattr('app.routers.quality.quality_service.ignore_issue', fake_ignore)

    try:
        client = TestClient(app)
        for path in ('/api/v1/quality/issues/1/resolve', '/api/v1/quality/issues/1/ignore'):
            for payload in ({}, {'note': None}, {'note': '   '}):
                response = client.post(path, json=payload)
                assert response.status_code == 422
        assert calls == []
    finally:
        app.dependency_overrides.clear()


def test_quality_actions_trim_note_before_service(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=4, username='qc', password_hash='x', name='QC', role='admin', is_active=True)

    calls: list[tuple[str, str | None]] = []

    def fake_resolve(db, *, issue_id, operator, note=None):
        calls.append(('resolve', note))
        return _quality_issue_response(status='resolved', note=note)

    def fake_ignore(db, *, issue_id, operator, note=None):
        calls.append(('ignore', note))
        return _quality_issue_response(status='ignored', note=note)

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.quality.quality_service.resolve_issue', fake_resolve)
    monkeypatch.setattr('app.routers.quality.quality_service.ignore_issue', fake_ignore)

    try:
        client = TestClient(app)
        resolve_response = client.post('/api/v1/quality/issues/1/resolve', json={'note': ' 已复核完成 '})
        ignore_response = client.post('/api/v1/quality/issues/1/ignore', json={'note': ' 暂不纳入本期 '})

        assert resolve_response.status_code == 200
        assert ignore_response.status_code == 200
        assert resolve_response.json()['resolve_note'] == '已复核完成'
        assert ignore_response.json()['resolve_note'] == '暂不纳入本期'
        assert calls == [('resolve', '已复核完成'), ('ignore', '暂不纳入本期')]
    finally:
        app.dependency_overrides.clear()
