from datetime import date

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_attendance_confirmation_routes_are_registered() -> None:
    assert app.url_path_for('attendance-draft') == '/api/v1/attendance/draft'
    assert app.url_path_for('attendance-confirm') == '/api/v1/attendance/confirm'
    assert app.url_path_for('attendance-anomalies') == '/api/v1/attendance/anomalies'
    assert app.url_path_for('attendance-summary') == '/api/v1/attendance/summary'


def test_attendance_draft_endpoint_calls_service(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=8,
            username='leader',
            password_hash='x',
            name='班长',
            role='shift_leader',
            workshop_id=2,
            team_id=10,
            is_mobile_user=True,
            is_active=True,
        )

    def fake_build_draft(db, *, machine_id, shift_id, business_date, current_user):
        assert machine_id == 11
        assert shift_id == 3
        assert business_date == date(2026, 3, 27)
        assert current_user.id == 8
        return {
            'machine_id': 11,
            'machine_name': '1#',
            'shift_id': 3,
            'shift_name': '白班',
            'business_date': '2026-03-27',
            'headcount_expected': 5,
            'status': 'draft',
            'items': [],
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.attendance.attendance_confirm_service.build_draft', fake_build_draft)

    client = TestClient(app)
    response = client.get('/api/v1/attendance/draft', params={'machine_id': 11, 'shift_id': 3, 'business_date': '2026-03-27'})

    assert response.status_code == 200
    assert response.json()['headcount_expected'] == 5
    assert response.json()['machine_name'] == '1#'

    app.dependency_overrides.clear()


def test_attendance_confirm_endpoint_calls_service(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=8,
            username='leader',
            password_hash='x',
            name='班长',
            role='shift_leader',
            workshop_id=2,
            team_id=10,
            is_mobile_user=True,
            is_active=True,
        )

    def fake_submit_confirmation(db, *, payload, current_user):
        assert payload['machine_id'] == 11
        assert payload['shift_id'] == 3
        assert payload['business_date'] == date(2026, 3, 27)
        assert len(payload['items']) == 1
        assert current_user.id == 8
        return {
            'id': 21,
            'machine_id': 11,
            'machine_name': '1#',
            'shift_id': 3,
            'shift_name': '白班',
            'business_date': '2026-03-27',
            'headcount_expected': 1,
            'status': 'confirmed',
            'items': payload['items'],
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.attendance.attendance_confirm_service.submit_confirmation', fake_submit_confirmation)

    client = TestClient(app)
    response = client.post(
        '/api/v1/attendance/confirm',
        json={
            'machine_id': 11,
            'shift_id': 3,
            'business_date': '2026-03-27',
            'items': [
                {
                    'employee_id': 1,
                    'leader_status': 'present',
                    'override_reason': None,
                    'notes': '',
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()['status'] == 'confirmed'

    app.dependency_overrides.clear()


def test_attendance_anomalies_and_summary_endpoints_call_service(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=1, username='hr', password_hash='x', name='HR', role='statistician', is_active=True)

    def fake_list_anomalies(db, *, workshop_id, date_from, date_to, current_user):
        assert workshop_id == 2
        assert date_from == date(2026, 3, 1)
        assert date_to == date(2026, 3, 27)
        assert current_user.id == 1
        return [
            {
                'business_date': '2026-03-27',
                'workshop_name': '冷轧2050车间',
                'machine_name': '1#',
                'shift_name': '白班',
                'employee_name': '李四',
                'leader_status': 'business_trip',
                'auto_status': 'absent',
                'hr_status': 'pending',
            }
        ]

    def fake_build_summary(db, *, business_date, current_user):
        assert business_date == date(2026, 3, 27)
        assert current_user.id == 1
        return {
            'business_date': '2026-03-27',
            'pending_count': 1,
            'confirmed_count': 5,
            'hr_reviewed_count': 2,
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.attendance.attendance_confirm_service.list_anomalies', fake_list_anomalies)
    monkeypatch.setattr('app.routers.attendance.attendance_confirm_service.build_summary', fake_build_summary)

    client = TestClient(app)
    anomalies = client.get(
        '/api/v1/attendance/anomalies',
        params={'workshop_id': 2, 'date_from': '2026-03-01', 'date_to': '2026-03-27'},
    )
    summary = client.get('/api/v1/attendance/summary', params={'business_date': '2026-03-27'})

    assert anomalies.status_code == 200
    assert anomalies.json()[0]['employee_name'] == '李四'
    assert summary.status_code == 200
    assert summary.json()['confirmed_count'] == 5

    app.dependency_overrides.clear()
