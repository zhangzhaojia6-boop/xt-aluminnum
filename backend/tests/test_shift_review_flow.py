from datetime import date, datetime

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def _make_shift_payload(status: str) -> dict:
    now = datetime(2026, 3, 25, 8, 0, 0)
    return {
        'id': 12,
        'business_date': date(2026, 3, 25),
        'shift_config_id': 1,
        'shift_code': 'A',
        'shift_name': 'Day',
        'workshop_id': 1,
        'workshop_code': 'W1',
        'workshop_name': 'Melting',
        'team_id': 1,
        'team_code': 'T1',
        'team_name': 'Team-A',
        'equipment_id': None,
        'equipment_code': None,
        'equipment_name': None,
        'input_weight': 120.0,
        'output_weight': 110.0,
        'qualified_weight': 105.0,
        'scrap_weight': 5.0,
        'planned_headcount': 8,
        'actual_headcount': 7,
        'downtime_minutes': 10,
        'downtime_reason': None,
        'issue_count': 1,
        'electricity_kwh': 40.0,
        'data_source': 'import',
        'import_batch_id': 9,
        'data_status': status,
        'version_no': 1,
        'superseded_by_id': None,
        'reviewed_by': None,
        'reviewed_at': None,
        'confirmed_by': None,
        'confirmed_at': None,
        'rejected_by': None,
        'rejected_at': None,
        'rejected_reason': None,
        'voided_by': None,
        'voided_at': None,
        'voided_reason': None,
        'published_by': None,
        'published_at': None,
        'notes': None,
        'created_at': now,
        'updated_at': now,
    }


def test_shift_review_confirm_reject_void_endpoints(monkeypatch) -> None:
    calls: list[tuple[str, str | None]] = []
    current_status = {'value': 'pending'}

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_update_shift_data_status(db, *, shift_data_id, action, reason, operator):
        assert shift_data_id == 12
        assert operator.id == 1
        calls.append((action, reason))
        current_status['value'] = {
            'review': 'reviewed',
            'confirm': 'confirmed',
            'reject': 'rejected',
            'void': 'voided',
        }[action]
        return object()

    def fake_get_shift_data_detail(db, *, shift_data_id):
        assert shift_data_id == 12
        return _make_shift_payload(current_status['value']), [], []

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.production.production_service.update_shift_data_status', fake_update_shift_data_status)
    monkeypatch.setattr('app.routers.production.production_service.get_shift_data_detail', fake_get_shift_data_detail)

    client = TestClient(app)
    review_resp = client.post('/api/v1/production/shift-data/12/review', json={'reason': 'manual check'})
    confirm_resp = client.post('/api/v1/production/shift-data/12/confirm', json={})
    reject_resp = client.post('/api/v1/production/shift-data/12/reject', json={'reason': 'wrong weight'})
    void_resp = client.post('/api/v1/production/shift-data/12/void', json={'reason': 'superseded'})

    assert review_resp.status_code == 200
    assert review_resp.json()['item']['data_status'] == 'reviewed'
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()['item']['data_status'] == 'confirmed'
    assert reject_resp.status_code == 200
    assert reject_resp.json()['item']['data_status'] == 'rejected'
    assert void_resp.status_code == 200
    assert void_resp.json()['item']['data_status'] == 'voided'
    assert calls == [
        ('review', 'manual check'),
        ('confirm', None),
        ('reject', 'wrong weight'),
        ('void', 'superseded'),
    ]

    app.dependency_overrides.clear()
