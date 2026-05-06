from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.auth import verify_password
from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.master import Equipment, Team, Workshop
from app.models.system import AuditLog, User


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'users-routes.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[Workshop.__table__, Team.__table__, User.__table__, Equipment.__table__, AuditLog.__table__],
    )
    return sessionmaker(bind=engine, future=True)


def seed_reference_data(session_factory):
    with session_factory() as db:
        workshop = Workshop(code='ZR2', name='铸二车间', sort_order=2, is_active=True)
        team = Team(code='ZR2-A', name='白班组', workshop_id=1, sort_order=1, is_active=True)
        db.add(workshop)
        db.flush()
        team.workshop_id = workshop.id
        db.add(team)
        db.flush()
        db.add_all(
            [
                User(
                    username='admin',
                    password_hash='x',
                    name='系统管理员',
                    role='admin',
                    workshop_id=None,
                    team_id=None,
                    data_scope_type='all',
                    is_mobile_user=False,
                    is_reviewer=True,
                    is_manager=True,
                    is_active=True,
                ),
                User(
                    username='leader01',
                    password_hash='hashed',
                    pin_code='123456',
                    name='张三',
                    role='shift_leader',
                    workshop_id=workshop.id,
                    team_id=team.id,
                    data_scope_type='self_workshop',
                    assigned_shift_ids=[1, 2, 3],
                    is_mobile_user=True,
                    is_reviewer=False,
                    is_manager=False,
                    is_active=True,
                    last_login=datetime(2026, 3, 30, 8, 15, tzinfo=timezone.utc),
                ),
            ]
        )
        db.flush()
        machine_one = Equipment(
            code='ZD-1',
            name='1#线',
            workshop_id=workshop.id,
            equipment_type='ingot_caster',
            operational_status='running',
            shift_mode='three',
            assigned_shift_ids=[1, 2, 3],
            qr_code='XT-ZD-1',
            bound_user_id=2,
            is_active=True,
        )
        machine_two = Equipment(
            code='ZD-2',
            name='2#线',
            workshop_id=workshop.id,
            equipment_type='ingot_caster',
            operational_status='running',
            shift_mode='three',
            assigned_shift_ids=[1, 2, 3],
            qr_code='XT-ZD-2',
            is_active=True,
        )
        db.add_all([machine_one, machine_two])
        db.commit()
        return {'workshop_id': workshop.id, 'team_id': team.id, 'machine_one_id': machine_one.id, 'machine_two_id': machine_two.id}


def test_users_routes_are_registered() -> None:
    assert app.url_path_for('users-list') == '/api/v1/users/'
    assert app.url_path_for('users-create') == '/api/v1/users/'
    assert app.url_path_for('users-sync-dingtalk') == '/api/v1/users/sync-dingtalk'
    assert app.url_path_for('users-update', user_id='5') == '/api/v1/users/5'
    assert app.url_path_for('users-delete', user_id='5') == '/api/v1/users/5'
    assert app.url_path_for('users-reset-password', user_id='5') == '/api/v1/users/5/reset-password'


def test_list_users_returns_paginated_payload_for_admin(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    refs = seed_reference_data(session_factory)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def fake_get_user() -> User:
        return User(
            id=1,
            username='admin',
            password_hash='x',
            name='系统管理员',
            role='admin',
            data_scope_type='all',
            is_mobile_user=False,
            is_reviewer=True,
            is_manager=True,
            is_active=True,
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    try:
        response = client.get('/api/v1/users/', params={'skip': 0, 'limit': 10})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['total'] == 2
    assert payload['skip'] == 0
    assert payload['limit'] == 10
    assert payload['items'][1] == {
        'id': 2,
        'username': 'leader01',
        'name': '张三',
        'role': 'shift_leader',
        'workshop_id': refs['workshop_id'],
        'workshop_name': '铸二车间',
        'team_id': refs['team_id'],
        'team_name': '白班组',
        'is_mobile_user': True,
        'is_reviewer': False,
        'is_manager': False,
        'is_active': True,
        'last_login': payload['items'][1]['last_login'],
        'bound_machine_id': 1,
        'bound_machine_name': '1#线',
    }
    assert payload['items'][1]['last_login'].startswith('2026-03-30T08:15:00')


def test_list_users_filters_by_machine_line_binding(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    refs = seed_reference_data(session_factory)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def fake_get_user() -> User:
        return User(
            id=1,
            username='admin',
            password_hash='x',
            name='系统管理员',
            role='admin',
            data_scope_type='all',
            is_mobile_user=False,
            is_reviewer=True,
            is_manager=True,
            is_active=True,
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    client = TestClient(app)
    try:
        bound_response = client.get('/api/v1/users/', params={'machine_binding': 'bound'})
        unbound_response = client.get('/api/v1/users/', params={'machine_binding': 'unbound'})
        exact_response = client.get('/api/v1/users/', params={'bound_machine_id': refs['machine_one_id']})
        empty_response = client.get('/api/v1/users/', params={'bound_machine_id': refs['machine_two_id']})
    finally:
        app.dependency_overrides.clear()

    assert bound_response.status_code == 200
    bound_payload = bound_response.json()
    assert bound_payload['total'] == 1
    assert bound_payload['items'][0]['username'] == 'leader01'
    assert bound_payload['items'][0]['bound_machine_id'] == refs['machine_one_id']

    assert unbound_response.status_code == 200
    unbound_payload = unbound_response.json()
    assert unbound_payload['total'] == 1
    assert unbound_payload['items'][0]['username'] == 'admin'
    assert unbound_payload['items'][0]['bound_machine_id'] is None

    assert exact_response.status_code == 200
    exact_payload = exact_response.json()
    assert exact_payload['total'] == 1
    assert exact_payload['items'][0]['username'] == 'leader01'

    assert empty_response.status_code == 200
    empty_payload = empty_response.json()
    assert empty_payload['total'] == 0
    assert empty_payload['items'] == []


def test_non_admin_cannot_access_users_routes(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    seed_reference_data(session_factory)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def fake_get_user() -> User:
        return User(
            id=2,
            username='reviewer',
            password_hash='x',
            name='审核员',
            role='reviewer',
            workshop_id=1,
            data_scope_type='self_workshop',
            is_mobile_user=False,
            is_reviewer=True,
            is_manager=False,
            is_active=True,
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user

    client = TestClient(app)
    try:
        response = client.get('/api/v1/users/')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_create_update_reset_and_deactivate_user(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    refs = seed_reference_data(session_factory)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def fake_get_user() -> User:
        return User(
            id=1,
            username='admin',
            password_hash='x',
            name='系统管理员',
            role='admin',
            data_scope_type='all',
            is_mobile_user=False,
            is_reviewer=True,
            is_manager=True,
            is_active=True,
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    client = TestClient(app)
    try:
        create_response = client.post(
            '/api/v1/users/',
            json={
                'username': 'weigher01',
                'password': 'Weight#2026',
                'name': '李四',
                'role': 'weigher',
                'workshop_id': refs['workshop_id'],
                'team_id': refs['team_id'],
                'is_mobile_user': True,
                'is_reviewer': False,
                'is_manager': False,
                'pin_code': '654321',
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created['username'] == 'weigher01'
        assert created['workshop_name'] == '铸二车间'
        assert created['team_name'] == '白班组'
        assert created['bound_machine_id'] is None
        assert created['bound_machine_name'] is None

        update_response = client.put(
            f"/api/v1/users/{created['id']}",
            json={
                'name': '李四班长',
                'role': 'shift_leader',
                'workshop_id': refs['workshop_id'],
                'team_id': refs['team_id'],
                'is_mobile_user': True,
                'is_reviewer': True,
                'is_manager': False,
                'pin_code': '111222',
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()['name'] == '李四班长'
        assert update_response.json()['role'] == 'shift_leader'
        assert update_response.json()['is_reviewer'] is True

        reset_response = client.post(
            f"/api/v1/users/{created['id']}/reset-password",
            json={'password': 'Reset#2026', 'pin_code': '222333'},
        )
        assert reset_response.status_code == 200
        assert reset_response.json()['message'] == '密码已重置'

        delete_response = client.delete(f"/api/v1/users/{created['id']}")
        assert delete_response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    with session_factory() as db:
        stored = db.execute(select(User).where(User.username == 'weigher01')).scalar_one()
        assert stored.name == '李四班长'
        assert stored.role == 'shift_leader'
        assert stored.pin_code == '222333'
        assert verify_password('Reset#2026', stored.password_hash) is True
        assert stored.is_active is False
        assert db.query(AuditLog).filter(AuditLog.table_name == 'users', AuditLog.record_id == stored.id).count() >= 4


def test_user_create_update_and_unbind_machine_line(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    refs = seed_reference_data(session_factory)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def fake_get_user() -> User:
        return User(
            id=1,
            username='admin',
            password_hash='x',
            name='系统管理员',
            role='admin',
            data_scope_type='all',
            is_mobile_user=False,
            is_reviewer=True,
            is_manager=True,
            is_active=True,
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    client = TestClient(app)
    try:
        create_response = client.post(
            '/api/v1/users/',
            json={
                'username': 'machine02',
                'password': 'Machine#2026',
                'name': '2#线主操',
                'role': 'shift_leader',
                'workshop_id': refs['workshop_id'],
                'team_id': refs['team_id'],
                'is_mobile_user': True,
                'bound_machine_id': refs['machine_two_id'],
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created['bound_machine_id'] == refs['machine_two_id']
        assert created['bound_machine_name'] == '2#线'

        occupied_response = client.put(
            '/api/v1/users/2',
            json={
                'workshop_id': refs['workshop_id'],
                'team_id': refs['team_id'],
                'bound_machine_id': refs['machine_two_id'],
            },
        )
        assert occupied_response.status_code == 400
        assert occupied_response.json()['detail'] == '机列已绑定其他用户'

        unbind_response = client.put(
            f"/api/v1/users/{created['id']}",
            json={'bound_machine_id': None},
        )
        assert unbind_response.status_code == 200
        assert unbind_response.json()['bound_machine_id'] is None
        assert unbind_response.json()['bound_machine_name'] is None
    finally:
        app.dependency_overrides.clear()

    with session_factory() as db:
        user = db.execute(select(User).where(User.username == 'machine02')).scalar_one()
        machine = db.get(Equipment, refs['machine_two_id'])
        assert machine.bound_user_id is None
        assert user.workshop_id == refs['workshop_id']


def test_user_machine_line_binding_rejects_cross_workshop(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    refs = seed_reference_data(session_factory)
    with session_factory() as db:
        other_workshop = Workshop(code='LH1', name='冷轧一车间', sort_order=3, is_active=True)
        db.add(other_workshop)
        db.flush()
        other_machine = Equipment(
            code='LH-1',
            name='冷轧1#线',
            workshop_id=other_workshop.id,
            equipment_type='cold_rolling',
            operational_status='running',
            shift_mode='three',
            assigned_shift_ids=[1, 2, 3],
            qr_code='XT-LH-1',
            is_active=True,
        )
        db.add(other_machine)
        db.commit()
        other_machine_id = other_machine.id

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def fake_get_user() -> User:
        return User(
            id=1,
            username='admin',
            password_hash='x',
            name='系统管理员',
            role='admin',
            data_scope_type='all',
            is_mobile_user=False,
            is_reviewer=True,
            is_manager=True,
            is_active=True,
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    client = TestClient(app)
    try:
        response = client.put(
            '/api/v1/users/2',
            json={
                'workshop_id': refs['workshop_id'],
                'team_id': refs['team_id'],
                'bound_machine_id': other_machine_id,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()['detail'] == '机列不属于所选车间'
