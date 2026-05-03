from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_password_hash
from app.core.deps import get_db
from app.database import Base
from app.main import app
from app.models.master import Team, Workshop
from app.models.system import AuditLog, User
from app.services import dingtalk_service


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'dingtalk-h5-login.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[Workshop.__table__, Team.__table__, User.__table__, AuditLog.__table__],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _client_with_db(session_factory):
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    return TestClient(app)


def _seed_user(
    db,
    *,
    username: str = 'leader_100',
    dingtalk_user_id: str | None = 'dt_100',
    dingtalk_union_id: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash('Pass#2026'),
        name='一车间班长',
        role='team_leader',
        dingtalk_user_id=dingtalk_user_id,
        dingtalk_union_id=dingtalk_union_id,
        data_scope_type='self_team',
        is_mobile_user=True,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def test_h5_login_returns_not_configured_when_corp_missing(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    monkeypatch.setattr(dingtalk_service.service, 'is_h5_configured', lambda: False)
    client = _client_with_db(session_factory)
    try:
        response = client.post('/api/v1/dingtalk/h5-login', json={'code': 'abc'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()['detail'] == 'dingtalk_not_configured'


def test_h5_login_returns_invalid_code(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    monkeypatch.setattr(dingtalk_service.service, 'is_h5_configured', lambda: True)
    monkeypatch.setattr(
        dingtalk_service.service,
        'exchange_code',
        lambda _code: (_ for _ in ()).throw(dingtalk_service.DingTalkCodeInvalid('bad code')),
    )
    client = _client_with_db(session_factory)
    try:
        response = client.post('/api/v1/dingtalk/h5-login', json={'code': 'abc'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()['detail'] == 'dingtalk_code_invalid'


def test_h5_login_returns_unbound_user_id(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    monkeypatch.setattr(dingtalk_service.service, 'is_h5_configured', lambda: True)
    monkeypatch.setattr(
        dingtalk_service.service,
        'exchange_code',
        lambda _code: {'userid': 'dt_unbound', 'unionid': 'union_unbound'},
    )
    client = _client_with_db(session_factory)
    try:
        response = client.post('/api/v1/dingtalk/h5-login', json={'code': 'abc'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()['detail']['code'] == 'dingtalk_user_not_bound'
    assert response.json()['detail']['dingtalk_user_id'] == 'dt_unbound'


def test_h5_login_rejects_conflicting_userid_and_unionid_bindings(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_user(db, username='leader_201', dingtalk_user_id='dt_conflict', dingtalk_union_id=None)
        _seed_user(db, username='leader_202', dingtalk_user_id='dt_other', dingtalk_union_id='union_conflict')
        db.commit()

    monkeypatch.setattr(dingtalk_service.service, 'is_h5_configured', lambda: True)
    monkeypatch.setattr(
        dingtalk_service.service,
        'exchange_code',
        lambda _code: {'userid': 'dt_conflict', 'unionid': 'union_conflict'},
    )
    client = _client_with_db(session_factory)
    try:
        response = client.post('/api/v1/dingtalk/h5-login', json={'code': 'abc'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'dingtalk_user_ambiguous'


def test_h5_login_rejects_inactive_stale_union_binding(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        active_user = _seed_user(db, username='leader_203', dingtalk_user_id='dt_stale', dingtalk_union_id=None)
        _seed_user(
            db,
            username='leader_204',
            dingtalk_user_id='dt_old',
            dingtalk_union_id='union_stale',
            is_active=False,
        )
        db.commit()

    monkeypatch.setattr(dingtalk_service.service, 'is_h5_configured', lambda: True)
    monkeypatch.setattr(
        dingtalk_service.service,
        'exchange_code',
        lambda _code: {'userid': 'dt_stale', 'unionid': 'union_stale'},
    )
    client = _client_with_db(session_factory)
    try:
        response = client.post('/api/v1/dingtalk/h5-login', json={'code': 'abc'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'dingtalk_user_ambiguous'
    with session_factory() as db:
        user = db.get(User, active_user.id)
        assert user is not None
        assert user.dingtalk_union_id is None


def test_h5_login_returns_login_response_shape(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        user = _seed_user(db, dingtalk_user_id='dt_100')
        db.commit()

    monkeypatch.setattr(dingtalk_service.service, 'is_h5_configured', lambda: True)
    monkeypatch.setattr(
        dingtalk_service.service,
        'exchange_code',
        lambda _code: {'userid': 'dt_100', 'unionid': 'union_100'},
    )
    client = _client_with_db(session_factory)
    try:
        response = client.post('/api/v1/dingtalk/h5-login', json={'code': 'abc'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['access_token']
    assert payload['token_type'] == 'bearer'
    assert payload['user']['id'] == user.id
    assert payload['user']['role'] == 'team_leader'
