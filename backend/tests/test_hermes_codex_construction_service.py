from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.hermes_factory_brain import HermesCodexConstructionRun
from app.models.master import Team, Workshop
from app.models.system import User
from app.services.hermes_codex_construction_service import request_codex_construction


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Workshop.__table__, Team.__table__, User.__table__, HermesCodexConstructionRun.__table__],
    )
    return Session(engine)


def test_root_owner_can_request_heavy_construction(monkeypatch) -> None:
    db = _db()
    user = User(
        id=1,
        username='root',
        password_hash='x',
        name='张兆嘉',
        role='admin',
        is_active=True,
        dingtalk_user_id='dt-root',
    )
    db.add(user)
    db.commit()
    monkeypatch.setattr(
        'app.services.hermes_codex_construction_service.settings.HERMES_CODEX_CONSTRUCTION_ENABLED',
        True,
        raising=False,
    )
    monkeypatch.setattr(
        'app.services.hermes_codex_construction_service.settings.HERMES_OWNER_DINGTALK_USER_IDS',
        'dt-root',
        raising=False,
    )

    result = request_codex_construction(
        db,
        actor=user,
        request_text='直接修好并部署',
        trace_id='trace-codex-heavy-001',
        construction_type='heavy',
    )
    db.commit()

    assert result.status == 'requested'
    assert db.query(HermesCodexConstructionRun).one().authorization_level == 'root_owner'


def test_admin_without_configured_root_owner_identity_cannot_request_construction(monkeypatch) -> None:
    db = _db()
    user = User(
        id=2,
        username='admin',
        password_hash='x',
        name='管理员',
        role='admin',
        is_active=True,
        dingtalk_user_id='dt-admin',
    )
    db.add(user)
    db.commit()
    monkeypatch.setattr(
        'app.services.hermes_codex_construction_service.settings.HERMES_CODEX_CONSTRUCTION_ENABLED',
        True,
        raising=False,
    )
    monkeypatch.setattr(
        'app.services.hermes_codex_construction_service.settings.HERMES_OWNER_DINGTALK_USER_IDS',
        'dt-root',
        raising=False,
    )

    result = request_codex_construction(
        db,
        actor=user,
        request_text='帮我改代码',
        trace_id='trace-codex-admin-denied-001',
        construction_type='light',
    )

    assert result.status == 'denied'
    assert db.query(HermesCodexConstructionRun).count() == 0


def test_non_root_owner_cannot_request_construction(monkeypatch) -> None:
    db = _db()
    user = User(
        id=2,
        username='manager',
        password_hash='x',
        name='经理',
        role='manager',
        is_manager=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    monkeypatch.setattr(
        'app.services.hermes_codex_construction_service.settings.HERMES_CODEX_CONSTRUCTION_ENABLED',
        True,
        raising=False,
    )
    monkeypatch.setattr(
        'app.services.hermes_codex_construction_service.settings.HERMES_OWNER_DINGTALK_USER_IDS',
        'dt-root',
        raising=False,
    )

    result = request_codex_construction(
        db,
        actor=user,
        request_text='帮我改代码',
        trace_id='trace-codex-denied-001',
        construction_type='light',
    )

    assert result.status == 'denied'
    assert db.query(HermesCodexConstructionRun).count() == 0


def test_codex_construction_requires_feature_flag(monkeypatch) -> None:
    db = _db()
    user = User(
        id=1,
        username='root',
        password_hash='x',
        name='张兆嘉',
        role='admin',
        is_active=True,
        dingtalk_user_id='dt-root',
    )
    db.add(user)
    db.commit()
    monkeypatch.setattr(
        'app.services.hermes_codex_construction_service.settings.HERMES_CODEX_CONSTRUCTION_ENABLED',
        False,
        raising=False,
    )
    monkeypatch.setattr(
        'app.services.hermes_codex_construction_service.settings.HERMES_OWNER_DINGTALK_USER_IDS',
        'dt-root',
        raising=False,
    )

    result = request_codex_construction(
        db,
        actor=user,
        request_text='直接修好并部署',
        trace_id='trace-codex-disabled-001',
        construction_type='heavy',
    )

    assert result.status == 'disabled'
    assert db.query(HermesCodexConstructionRun).count() == 0
