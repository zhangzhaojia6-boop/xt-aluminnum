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


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'wecom-login.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[Workshop.__table__, Team.__table__, User.__table__, AuditLog.__table__],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed_user(db, *, username: str, dingtalk_user_id: str | None = None, is_active: bool = True) -> User:
    workshop = Workshop(code=f"W_{username}", name=f"车间{username}", is_active=True, sort_order=1)
    db.add(workshop)
    db.flush()
    user = User(
        username=username,
        password_hash=get_password_hash("Pass#2026"),
        name=username,
        role="team_leader",
        workshop_id=workshop.id,
        dingtalk_user_id=dingtalk_user_id,
        data_scope_type="self_workshop",
        is_mobile_user=True,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def _client_with_db(session_factory):
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    return TestClient(app)


def _patch_dingtalk_login(monkeypatch, *, open_id: str, union_id: str = "union-test", nick: str = "test") -> None:
    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_APP_KEY", "fake_key")
    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_APP_SECRET", "fake_secret")
    monkeypatch.setattr("app.routers.dingtalk._get_user_access_token", lambda _code: "fake_token")
    monkeypatch.setattr(
        "app.routers.dingtalk._get_user_info",
        lambda _token: {
            "unionId": union_id,
            "openId": open_id,
            "nick": nick,
        },
    )


def test_wecom_login_matches_username(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        user = _seed_user(db, username="leader_100", dingtalk_user_id="leader_100")
        db.commit()

    _patch_dingtalk_login(monkeypatch, open_id="leader_100", union_id="union-leader-100")
    client = _client_with_db(session_factory)
    try:
        response = client.post("/api/v1/dingtalk/login", json={"code": "abc"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == user.id
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"


def test_wecom_login_matches_dingtalk_userid(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        user = _seed_user(db, username="leader_101", dingtalk_user_id="wx_101")
        db.commit()

    _patch_dingtalk_login(monkeypatch, open_id="wx_101", union_id="union-wx-101")
    client = _client_with_db(session_factory)
    try:
        response = client.post("/api/v1/dingtalk/login", json={"code": "abc"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["user_id"] == user.id


def test_wecom_login_returns_readable_403_when_not_found(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    _patch_dingtalk_login(monkeypatch, open_id="wx_not_exists", union_id="union-wx-not-exists")
    client = _client_with_db(session_factory)
    try:
        response = client.post("/api/v1/dingtalk/login", json={"code": "abc"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "未绑定系统账号" in response.json()["detail"]


def test_wecom_login_returns_readable_403_when_inactive(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_user(db, username="leader_102", dingtalk_user_id="wx_102", is_active=False)
        db.commit()

    _patch_dingtalk_login(monkeypatch, open_id="wx_102", union_id="union-wx-102")
    client = _client_with_db(session_factory)
    try:
        response = client.post("/api/v1/dingtalk/login", json={"code": "abc"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "未绑定系统账号" in response.json()["detail"]


def test_wecom_login_returns_readable_403_when_ambiguous(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        user_a = _seed_user(db, username="leader_201", dingtalk_user_id="wx_dup")
        user_b = _seed_user(db, username="leader_202", dingtalk_user_id="wx_dup")
        db.commit()

    _patch_dingtalk_login(monkeypatch, open_id="wx_dup", union_id="union-wx-dup")
    client = _client_with_db(session_factory)
    try:
        response = client.post("/api/v1/dingtalk/login", json={"code": "abc"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["user_id"] in {user_a.id, user_b.id}


def test_wecom_login_returns_503_when_disabled(tmp_path, monkeypatch) -> None:
    session_factory = _session_factory(tmp_path)
    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_APP_KEY", "")
    monkeypatch.setattr("app.routers.dingtalk.settings.DINGTALK_APP_SECRET", "fake_secret")
    client = _client_with_db(session_factory)
    try:
        response = client.post("/api/v1/dingtalk/login", json={"code": "abc"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "钉钉应用未配置" in response.json()["detail"]
