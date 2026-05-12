from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import create_access_token, get_password_hash
from app.core.deps import get_db
from app.database import Base
from app.main import app
from app.models.system import User
from app.models.user_preferences import UserPreferences  # noqa: F401 — ensure table metadata registers


TABLES = [
    User.__table__,
    UserPreferences.__table__,
]


def _build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'user-prefs.db'}", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _override_db(session_factory) -> None:
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db


def _seed_user(session_factory) -> int:
    with session_factory() as db:
        user = User(
            username='prefs_user',
            password_hash=get_password_hash('Passw0rd!2026'),
            name='Prefs User',
            role='admin',
            is_active=True,
        )
        db.add(user)
        db.commit()
        return user.id


def _auth_headers(user_id: int) -> dict[str, str]:
    token = create_access_token(subject=str(user_id))
    return {'Authorization': f'Bearer {token}'}


def _reset():
    app.dependency_overrides.clear()


def test_get_preferences_unauthenticated(tmp_path):
    session_factory = _build_sessionmaker(tmp_path)
    _override_db(session_factory)
    try:
        with TestClient(app) as client:
            resp = client.get('/api/v1/user/preferences')
        assert resp.status_code == 401
    finally:
        _reset()


def test_put_preferences_unauthenticated(tmp_path):
    session_factory = _build_sessionmaker(tmp_path)
    _override_db(session_factory)
    try:
        with TestClient(app) as client:
            resp = client.put('/api/v1/user/preferences', json={'theme': 'hud'})
        assert resp.status_code == 401
    finally:
        _reset()


def test_get_preferences_default_null(tmp_path):
    session_factory = _build_sessionmaker(tmp_path)
    _override_db(session_factory)
    try:
        user_id = _seed_user(session_factory)
        with TestClient(app) as client:
            resp = client.get('/api/v1/user/preferences', headers=_auth_headers(user_id))
        assert resp.status_code == 200
        assert resp.json() == {'theme': None}
    finally:
        _reset()


def test_put_then_get_preferences(tmp_path):
    session_factory = _build_sessionmaker(tmp_path)
    _override_db(session_factory)
    try:
        user_id = _seed_user(session_factory)
        headers = _auth_headers(user_id)
        with TestClient(app) as client:
            put_resp = client.put('/api/v1/user/preferences', json={'theme': 'hud'}, headers=headers)
            assert put_resp.status_code == 200
            assert put_resp.json() == {'theme': 'hud'}
            get_resp = client.get('/api/v1/user/preferences', headers=headers)
            assert get_resp.status_code == 200
            assert get_resp.json() == {'theme': 'hud'}
    finally:
        _reset()


def test_put_rejects_unknown_theme(tmp_path):
    session_factory = _build_sessionmaker(tmp_path)
    _override_db(session_factory)
    try:
        user_id = _seed_user(session_factory)
        with TestClient(app) as client:
            resp = client.put(
                '/api/v1/user/preferences',
                json={'theme': 'palantir'},
                headers=_auth_headers(user_id),
            )
        assert resp.status_code == 422
    finally:
        _reset()


def test_put_null_clears_preference(tmp_path):
    session_factory = _build_sessionmaker(tmp_path)
    _override_db(session_factory)
    try:
        user_id = _seed_user(session_factory)
        headers = _auth_headers(user_id)
        with TestClient(app) as client:
            client.put('/api/v1/user/preferences', json={'theme': 'hud'}, headers=headers)
            clear_resp = client.put('/api/v1/user/preferences', json={'theme': None}, headers=headers)
            assert clear_resp.status_code == 200
            assert clear_resp.json() == {'theme': None}
    finally:
        _reset()


def test_put_is_idempotent(tmp_path):
    session_factory = _build_sessionmaker(tmp_path)
    _override_db(session_factory)
    try:
        user_id = _seed_user(session_factory)
        headers = _auth_headers(user_id)
        with TestClient(app) as client:
            for _ in range(3):
                resp = client.put('/api/v1/user/preferences', json={'theme': 'hud'}, headers=headers)
                assert resp.status_code == 200
    finally:
        _reset()
