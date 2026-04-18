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
        db.add(
            Equipment(
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
        )
        db.commit()
        return {'workshop_id': workshop.id, 'team_id': team.id}


def test_users_routes_are_registered() -> None:
    assert app.url_path_for('users-list') == '/api/v1/users/'
    assert app.url_path_for('users-create') == '/api/v1/users/'
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
