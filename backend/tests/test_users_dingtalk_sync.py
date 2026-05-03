from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.master import Equipment, Team, Workshop
from app.models.system import AuditLog, User
from app.services import dingtalk_service


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'users-dingtalk-sync.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[Workshop.__table__, Team.__table__, User.__table__, Equipment.__table__, AuditLog.__table__],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed_admin(db) -> User:
    admin = User(
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
    db.add(admin)
    db.flush()
    return admin


def _client_with_db(session_factory):
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
    return TestClient(app)


def test_admin_can_sync_dingtalk_contacts_into_mobile_users(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_admin(db)
        db.commit()

    monkeypatch.setattr(
        dingtalk_service.service,
        'fetch_department_users',
        lambda department_id=1: [
            {
                'userid': 'dt_200',
                'unionid': 'union_200',
                'name': '王五',
                'mobile': '13900002000',
            }
        ],
    )
    client = _client_with_db(session_factory)
    try:
        response = client.post('/api/v1/users/sync-dingtalk', json={'department_id': 1})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['created_count'] == 1
    assert payload['updated_count'] == 0
    assert payload['skipped_count'] == 0
    assert payload['users'][0]['username'] == '13900002000'

    with session_factory() as db:
        stored = db.execute(select(User).where(User.username == '13900002000')).scalar_one()
        assert stored.name == '王五'
        assert stored.role == 'shift_leader'
        assert stored.dingtalk_user_id == 'dt_200'
        assert stored.dingtalk_union_id == 'union_200'
        assert stored.is_mobile_user is True
        assert db.query(AuditLog).filter(AuditLog.action == 'sync_dingtalk').count() == 1


def test_dingtalk_sync_reports_not_configured(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_admin(db)
        db.commit()

    monkeypatch.setattr(
        dingtalk_service.service,
        'fetch_department_users',
        lambda department_id=1: (_ for _ in ()).throw(dingtalk_service.DingTalkNotConfigured('dingtalk_not_configured')),
    )
    client = _client_with_db(session_factory)
    try:
        response = client.post('/api/v1/users/sync-dingtalk', json={'department_id': 1})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()['detail'] == '钉钉应用未配置'


def test_dingtalk_sync_matches_existing_user_by_mobile_and_updates_binding(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_admin(db)
        db.add(
            User(
                username='13900002001',
                password_hash='x',
                name='旧姓名',
                role='shift_leader',
                data_scope_type='assigned',
                is_mobile_user=False,
                is_reviewer=False,
                is_manager=False,
                is_active=True,
            )
        )
        db.commit()

    monkeypatch.setattr(
        dingtalk_service.service,
        'fetch_department_users',
        lambda department_id=1: [
            {
                'userid': 'dt_201',
                'unionid': 'union_201',
                'name': '赵六',
                'mobile': '13900002001',
            }
        ],
    )
    client = _client_with_db(session_factory)
    try:
        response = client.post('/api/v1/users/sync-dingtalk', json={'department_id': 1})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['created_count'] == 0
    assert payload['updated_count'] == 1

    with session_factory() as db:
        users = db.execute(select(User).where(User.username == '13900002001')).scalars().all()
        assert len(users) == 1
        assert users[0].name == '赵六'
        assert users[0].dingtalk_user_id == 'dt_201'
        assert users[0].dingtalk_union_id == 'union_201'
        assert users[0].is_mobile_user is True
