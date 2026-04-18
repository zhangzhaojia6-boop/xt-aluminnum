from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_password_hash
from app.database import Base
from app.models.master import Team, Workshop
from app.models.system import User
from app.services.wecom_mapping_service import resolve_wecom_user


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'wecom-mapping.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, Team.__table__, User.__table__])
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed_user(db, *, username, dingtalk_user_id=None, is_active=True):
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


def test_resolve_wecom_user_matches_username(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        user = _seed_user(db, username="leader_01")
        db.commit()

    with session_factory() as db:
        result = resolve_wecom_user(db, wecom_userid="leader_01")
        assert result.status == "matched"
        assert result.user and result.user.id == user.id


def test_resolve_wecom_user_matches_dingtalk_userid(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        user = _seed_user(db, username="leader_02", dingtalk_user_id="wx_leader_02")
        db.commit()

    with session_factory() as db:
        result = resolve_wecom_user(db, wecom_userid="wx_leader_02")
        assert result.status == "matched"
        assert result.user and result.user.id == user.id


def test_resolve_wecom_user_supports_case_insensitive_match(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_user(db, username="Leader_03")
        db.commit()

    with session_factory() as db:
        result = resolve_wecom_user(db, wecom_userid="leader_03")
        assert result.status == "matched"
        assert result.matched_by == "case_insensitive"


def test_resolve_wecom_user_detects_ambiguous_mapping(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_user(db, username="leader_a", dingtalk_user_id="wx_conflict")
        _seed_user(db, username="leader_b", dingtalk_user_id="wx_conflict")
        db.commit()

    with session_factory() as db:
        result = resolve_wecom_user(db, wecom_userid="wx_conflict")
        assert result.status == "ambiguous"
        assert len(result.conflicts) == 2


def test_resolve_wecom_user_returns_inactive_when_user_disabled(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_user(db, username="leader_off", dingtalk_user_id="wx_off", is_active=False)
        db.commit()

    with session_factory() as db:
        result = resolve_wecom_user(db, wecom_userid="wx_off")
        assert result.status == "inactive"


def test_resolve_wecom_user_returns_not_found(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        result = resolve_wecom_user(db, wecom_userid="wx_unknown")
        assert result.status == "not_found"
