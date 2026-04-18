from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


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
