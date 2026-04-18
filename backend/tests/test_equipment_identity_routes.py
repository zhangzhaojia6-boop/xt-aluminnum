from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    def get(self, model, key):
        _ = model
        return type(
            'EquipmentRow',
            (),
            {
                'id': key,
                'code': 'ZR2-3',
                'name': '3#机',
                'workshop_id': 7,
                'equipment_type': 'cast_roller',
                'spec': None,
                'operational_status': 'running',
                'shift_mode': 'three',
                'assigned_shift_ids': [1, 2, 3],
                'custom_fields': [{'name': 'al_liquid_kg', 'label': '铝液', 'type': 'number', 'unit': '公斤'}],
                'qr_code': 'XT-ZR2-3',
                'bound_user_id': 12,
                'sort_order': 0,
                'is_active': True,
                'bound_username': 'ZR2-3',
                'bound_user_name': '铸二车间 3#机',
            },
        )()


def test_equipment_identity_routes_are_registered() -> None:
    assert app.url_path_for('equipment-create-with-account') == '/api/v1/master/equipment/create-with-account'
    assert app.url_path_for('equipment-detail', equipment_id='5') == '/api/v1/master/equipment/5'
    assert app.url_path_for('equipment-reset-pin', equipment_id='5') == '/api/v1/master/equipment/5/reset-pin'
    assert app.url_path_for('equipment-toggle-status', equipment_id='5') == '/api/v1/master/equipment/5/toggle-status'


def test_create_with_account_endpoint_calls_service(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=2,
            username='admin',
            password_hash='x',
            name='管理员',
            role='admin',
            is_active=True,
        )

    def fake_create(db, **payload):
        assert isinstance(db, DummyDB)
        calls.append(payload)
        return {
            'equipment_id': 12,
            'username': 'ZR2-3',
            'pin': '384756',
            'qr_code': 'XT-ZR2-3',
            'workshop_name': '铸二车间',
            'machine_name': '3#机',
        }

    monkeypatch.setattr('app.routers.master.equipment_service.create_machine_with_account', fake_create)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    try:
        response = client.post(
            '/api/v1/master/equipment/create-with-account',
            json={
                'workshop_id': 7,
                'code': '3',
                'name': '3#机',
                'machine_type': 'cast_roller',
                'shift_mode': 'three',
                'assigned_shift_ids': [1, 2, 3],
                'custom_fields': [{'name': 'al_liquid_kg', 'label': '铝液', 'type': 'number', 'unit': '公斤'}],
                'operational_status': 'running',
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()['account'] == {
        'username': 'ZR2-3',
        'pin': '384756',
        'qr_code': 'XT-ZR2-3',
    }
    assert len(calls) == 1
    assert calls[0]['workshop_id'] == 7
    assert calls[0]['code'] == '3'
    assert calls[0]['name'] == '3#机'
    assert calls[0]['machine_type'] == 'cast_roller'
    assert calls[0]['shift_mode'] == 'three'
    assert calls[0]['assigned_shift_ids'] == [1, 2, 3]
    assert calls[0]['custom_fields'] == [{'name': 'al_liquid_kg', 'label': '铝液', 'type': 'number', 'unit': '公斤'}]
    assert calls[0]['operational_status'] == 'running'
    assert calls[0]['operator'].id == 2
    assert calls[0]['ip_address'] == 'testclient'
    assert calls[0]['user_agent']


def test_reset_pin_endpoint_calls_service(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=2,
            username='admin',
            password_hash='x',
            name='管理员',
            role='admin',
            is_active=True,
        )

    monkeypatch.setattr(
        'app.routers.master.equipment_service.reset_machine_pin',
        lambda db, *, equipment_id, **_kwargs: {'username': 'ZR2-3', 'new_pin': '902144'},
    )
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    try:
        response = client.post('/api/v1/master/equipment/12/reset-pin')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {'username': 'ZR2-3', 'new_pin': '902144'}


def test_toggle_status_endpoint_calls_service(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=2,
            username='admin',
            password_hash='x',
            name='管理员',
            role='admin',
            is_active=True,
        )

    monkeypatch.setattr(
        'app.routers.master.equipment_service.toggle_machine_status',
        lambda db, *, equipment_id, operational_status, **_kwargs: {
            'id': equipment_id,
            'operational_status': operational_status,
            'is_active': operational_status == 'running',
        },
    )
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    try:
        response = client.post('/api/v1/master/equipment/12/toggle-status', json={'operational_status': 'maintenance'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['operational_status'] == 'maintenance'
