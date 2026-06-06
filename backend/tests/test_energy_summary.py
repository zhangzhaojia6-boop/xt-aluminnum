from datetime import date

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_energy_summary_endpoint(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=8, username='energy', password_hash='x', name='Energy', role='admin', is_active=True)

    def fake_summary(db, *, business_date=None, workshop_id=None, shift_config_id=None):
        assert business_date == date(2026, 3, 25)
        assert workshop_id is None
        assert shift_config_id is None
        return [
            {
                'business_date': date(2026, 3, 25),
                'workshop_id': 1,
                'workshop_code': 'W1',
                'shift_config_id': 2,
                'shift_code': 'A',
                'electricity_value': 100.0,
                'gas_value': 20.0,
                'water_value': 10.0,
                'total_energy': 130.0,
                'output_weight': 50.0,
                'energy_per_ton': 2.6,
            }
        ]

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', fake_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25'})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body == [
        {
            'business_date': '2026-03-25',
            'workshop_id': 1,
            'workshop_code': 'W1',
            'shift_config_id': 2,
            'shift_code': 'A',
            'electricity_value': 100.0,
            'gas_value': 20.0,
            'water_value': 10.0,
            'total_energy': 130.0,
            'output_weight': 50.0,
            'energy_per_ton': 2.6,
        }
    ]

    row = body[0]
    for field_name in (
        'electricity_value',
        'gas_value',
        'water_value',
        'total_energy',
        'output_weight',
        'energy_per_ton',
    ):
        assert isinstance(row[field_name], float)

    app.dependency_overrides.clear()


def test_energy_summary_admin_passes_filters_to_service(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=18, username='energy-admin', password_hash='x', name='Energy Admin', role='admin', is_active=True)

    def fake_summary(db, *, business_date=None, workshop_id=None, shift_config_id=None):
        assert business_date == date(2026, 3, 25)
        assert workshop_id == 12
        assert shift_config_id == 101
        return []

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', fake_summary)

    client = TestClient(app)
    response = client.get(
        '/api/v1/energy/summary',
        params={'business_date': '2026-03-25', 'workshop_id': 12, 'shift_config_id': 101},
    )

    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()


def test_energy_summary_requires_authenticated_user() -> None:
    def fake_get_db():
        yield DummyDB()

    app.dependency_overrides[get_db] = fake_get_db

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25'})

    assert response.status_code == 401

    app.dependency_overrides.clear()


def test_energy_summary_denies_cross_workshop_scope(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=9,
            username='reviewer',
            password_hash='x',
            name='Reviewer',
            role='reviewer',
            workshop_id=11,
            data_scope_type='self_workshop',
            is_reviewer=True,
            is_active=True,
        )

    def forbidden_summary(*_args, **_kwargs):
        raise AssertionError('cross-workshop request must be blocked before querying energy summary')

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', forbidden_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25', 'workshop_id': 12})

    assert response.status_code == 403

    app.dependency_overrides.clear()


def test_energy_summary_scopes_self_workshop_user_to_own_workshop(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=10,
            username='reviewer-own',
            password_hash='x',
            name='Reviewer Own',
            role='reviewer',
            workshop_id=11,
            data_scope_type='self_workshop',
            is_reviewer=True,
            is_active=True,
        )

    def fake_summary(db, *, business_date=None, workshop_id=None, shift_config_id=None):
        assert workshop_id == 11
        assert shift_config_id is None
        return []

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', fake_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25'})

    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()


def test_energy_summary_denies_logged_in_non_manager_or_reviewer(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=11,
            username='operator',
            password_hash='x',
            name='Operator',
            role='machine_operator',
            workshop_id=11,
            data_scope_type='self_workshop',
            is_reviewer=False,
            is_active=True,
        )

    def forbidden_summary(*_args, **_kwargs):
        raise AssertionError('non-manager request must be blocked before querying energy summary')

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', forbidden_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25', 'workshop_id': 11})

    assert response.status_code == 403

    app.dependency_overrides.clear()


def test_energy_summary_denies_self_team_reviewer_without_team_safe_filter(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=12,
            username='team-reviewer',
            password_hash='x',
            name='Team Reviewer',
            role='reviewer',
            workshop_id=11,
            team_id=7,
            data_scope_type='self_team',
            is_reviewer=True,
            is_active=True,
        )

    def forbidden_summary(*_args, **_kwargs):
        raise AssertionError('self_team reviewer must not be expanded to workshop energy summary')

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', forbidden_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25', 'workshop_id': 11})

    assert response.status_code == 403

    app.dependency_overrides.clear()


def test_energy_summary_allows_manager_user_for_manage_surface(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=16,
            username='factory-manager',
            password_hash='x',
            name='Factory Manager',
            role='manager',
            data_scope_type='all',
            is_manager=True,
            is_active=True,
        )

    def fake_summary(db, *, business_date=None, workshop_id=None, shift_config_id=None):
        assert business_date == date(2026, 3, 25)
        assert workshop_id is None
        assert shift_config_id is None
        return []

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', fake_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25'})

    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()


def test_energy_summary_scopes_manager_to_own_workshop(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=17,
            username='workshop-manager',
            password_hash='x',
            name='Workshop Manager',
            role='manager',
            workshop_id=11,
            data_scope_type='self_workshop',
            is_manager=True,
            is_active=True,
        )

    def fake_summary(db, *, business_date=None, workshop_id=None, shift_config_id=None):
        assert business_date == date(2026, 3, 25)
        assert workshop_id == 11
        assert shift_config_id is None
        return []

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', fake_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25'})

    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()


def test_energy_summary_denies_self_team_cross_workshop(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=19,
            username='team-reviewer-cross',
            password_hash='x',
            name='Team Reviewer Cross',
            role='reviewer',
            workshop_id=11,
            team_id=7,
            data_scope_type='self_team',
            is_reviewer=True,
            is_active=True,
        )

    def forbidden_summary(*_args, **_kwargs):
        raise AssertionError('self_team reviewer must be blocked before cross-workshop energy query')

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', forbidden_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25', 'workshop_id': 12})

    assert response.status_code == 403

    app.dependency_overrides.clear()


def test_energy_summary_assigned_scope_requires_shift_config_id(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=13,
            username='assigned-reviewer',
            password_hash='x',
            name='Assigned Reviewer',
            role='reviewer',
            workshop_id=11,
            data_scope_type='assigned',
            assigned_shift_ids=[101],
            is_reviewer=True,
            is_active=True,
        )

    def forbidden_summary(*_args, **_kwargs):
        raise AssertionError('assigned reviewer without shift_config_id must be blocked')

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', forbidden_summary)

    client = TestClient(app)
    response = client.get('/api/v1/energy/summary', params={'business_date': '2026-03-25', 'workshop_id': 11})

    assert response.status_code == 403

    app.dependency_overrides.clear()


def test_energy_summary_assigned_scope_denies_unassigned_shift(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=14,
            username='assigned-reviewer-denied',
            password_hash='x',
            name='Assigned Reviewer Denied',
            role='reviewer',
            workshop_id=11,
            data_scope_type='assigned',
            assigned_shift_ids=[101],
            is_reviewer=True,
            is_active=True,
        )

    def forbidden_summary(*_args, **_kwargs):
        raise AssertionError('unassigned shift must be blocked before querying energy summary')

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', forbidden_summary)

    client = TestClient(app)
    response = client.get(
        '/api/v1/energy/summary',
        params={'business_date': '2026-03-25', 'workshop_id': 11, 'shift_config_id': 102},
    )

    assert response.status_code == 403

    app.dependency_overrides.clear()


def test_energy_summary_assigned_scope_allows_assigned_shift(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=15,
            username='assigned-reviewer-allowed',
            password_hash='x',
            name='Assigned Reviewer Allowed',
            role='reviewer',
            workshop_id=11,
            data_scope_type='assigned',
            assigned_shift_ids=[101],
            is_reviewer=True,
            is_active=True,
        )

    def fake_summary(db, *, business_date=None, workshop_id=None, shift_config_id=None):
        assert workshop_id == 11
        assert shift_config_id == 101
        return []

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.energy.energy_service.get_energy_summary', fake_summary)

    client = TestClient(app)
    response = client.get(
        '/api/v1/energy/summary',
        params={'business_date': '2026-03-25', 'workshop_id': 11, 'shift_config_id': 101},
    )

    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()
