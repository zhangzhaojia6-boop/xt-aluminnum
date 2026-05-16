from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import create_access_token, create_refresh_token, get_password_hash
from app.core.deps import get_db
from app.database import Base
from app.main import app
from app.models.master import Equipment, Team, Workshop
from app.models.system import AuditLog, User
from app.routers import auth as auth_router


AUTH_TABLES = [
    Workshop.__table__,
    Team.__table__,
    User.__table__,
    Equipment.__table__,
    AuditLog.__table__,
]


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth-routes.db'}", future=True)
    Base.metadata.create_all(engine, tables=AUTH_TABLES)
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _override_db(session_factory) -> None:
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db


def _seed_user(
    session_factory,
    *,
    username: str = 'operator',
    password: str = 'Passw0rd!2026',
    is_active: bool = True,
    role: str = 'shift_leader',
) -> int:
    with session_factory() as db:
        user = User(
            username=username,
            password_hash=get_password_hash(password),
            name='Operator',
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        return user.id


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_login_returns_token_and_records_audit(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    user_id = _seed_user(session_factory)
    _override_db(session_factory)

    response = TestClient(app).post(
        '/api/v1/auth/login',
        json={'username': 'operator', 'password': 'Passw0rd!2026'},
    )

    assert response.status_code == 200
    body = response.json()
    assert body['access_token']
    assert body['refresh_token']
    assert body['token_type'] == 'bearer'
    assert body['user']['id'] == user_id
    assert body['user']['username'] == 'operator'
    assert body['machine_info'] is None

    with session_factory() as db:
        user = db.get(User, user_id)
        assert user.last_login is not None
        audit = db.query(AuditLog).filter(AuditLog.action == 'login').one()
        assert audit.user_id == user_id
        assert audit.module == 'auth'
        assert audit.table_name == 'users'


def test_login_rejects_wrong_password(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_user(session_factory)
    _override_db(session_factory)

    response = TestClient(app).post(
        '/api/v1/auth/login',
        json={'username': 'operator', 'password': 'wrong'},
    )

    assert response.status_code == 400
    assert response.json()['detail'] == 'Invalid username or password'


def test_login_rejects_disabled_user(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_user(session_factory, is_active=False)
    _override_db(session_factory)

    response = TestClient(app).post(
        '/api/v1/auth/login',
        json={'username': 'operator', 'password': 'Passw0rd!2026'},
    )

    assert response.status_code == 403
    assert response.json()['detail'] == 'User is disabled'


def test_login_bootstraps_initial_admin(tmp_path, monkeypatch) -> None:
    session_factory = build_sessionmaker(tmp_path)
    monkeypatch.setattr(auth_router.settings, 'INIT_ADMIN_USERNAME', 'bootstrap_admin')
    monkeypatch.setattr(auth_router.settings, 'INIT_ADMIN_PASSWORD', 'Bootstrap#Pass2026')
    monkeypatch.setattr(auth_router.settings, 'INIT_ADMIN_NAME', 'Bootstrap Admin')
    _override_db(session_factory)

    response = TestClient(app).post(
        '/api/v1/auth/login',
        json={'username': 'bootstrap_admin', 'password': 'Bootstrap#Pass2026'},
    )

    assert response.status_code == 200
    body = response.json()
    assert body['user']['username'] == 'bootstrap_admin'
    assert body['user']['role'] == 'admin'

    with session_factory() as db:
        users = db.query(User).all()
        assert len(users) == 1
        assert users[0].name == 'Bootstrap Admin'


def test_me_returns_current_user_for_valid_token(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    user_id = _seed_user(session_factory, username='reviewer', role='reviewer')
    _override_db(session_factory)
    token = create_access_token(subject=str(user_id))

    response = TestClient(app).get(
        '/api/v1/auth/me',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    assert response.json()['username'] == 'reviewer'
    assert response.json()['role'] == 'reviewer'


def test_me_rejects_invalid_token(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    _seed_user(session_factory)
    _override_db(session_factory)

    response = TestClient(app).get(
        '/api/v1/auth/me',
        headers={'Authorization': 'Bearer invalid-token'},
    )

    assert response.status_code == 401
    assert response.json()['detail'] == 'Invalid authentication credentials'


def test_refresh_returns_new_login_response(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    user_id = _seed_user(session_factory, username='refreshed')
    _override_db(session_factory)
    refresh = create_refresh_token(subject=str(user_id))

    response = TestClient(app).post('/api/v1/auth/refresh', json={'refresh_token': refresh})

    assert response.status_code == 200
    body = response.json()
    assert body['access_token']
    assert body['refresh_token']
    assert body['token_type'] == 'bearer'
    assert body['user']['id'] == user_id


def test_refresh_rejects_access_token(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    user_id = _seed_user(session_factory)
    _override_db(session_factory)
    access = create_access_token(subject=str(user_id))

    response = TestClient(app).post('/api/v1/auth/refresh', json={'refresh_token': access})

    assert response.status_code == 401
    assert response.json()['detail'] == 'Invalid or expired refresh token'


def test_logout_response_contract() -> None:
    response = TestClient(app).post('/api/v1/auth/logout')

    assert response.status_code == 200
    assert response.json() == {
        'success': True,
        'data': None,
        'message': 'logout success',
        'total': None,
    }
