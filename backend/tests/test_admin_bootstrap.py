from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_password_hash, verify_password
from app.database import Base
from app.models.master import Team, Workshop
from app.models.system import User
from app.services import bootstrap


SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'create_admin.py'


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'admin-bootstrap.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, Team.__table__, User.__table__])
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _load_create_admin_module():
    spec = importlib.util.spec_from_file_location('create_admin_under_test', SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_admin(session_factory, *, password: str = 'Existing#2026') -> int:
    with session_factory() as db:
        user = User(
            username='admin',
            password_hash=get_password_hash(password),
            name='Existing Admin',
            role='admin',
            data_scope_type='all',
            is_mobile_user=False,
            is_reviewer=True,
            is_manager=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        return user.id


def test_create_admin_preserves_existing_password_hash(tmp_path, monkeypatch) -> None:
    session_factory = build_sessionmaker(tmp_path)
    admin_id = _seed_admin(session_factory)
    module = _load_create_admin_module()
    monkeypatch.setattr(module, 'get_sessionmaker', lambda: session_factory)

    user = module.create_admin('admin', 'New#2026', 'System Admin')

    assert user.id == admin_id
    with session_factory() as db:
        stored = db.get(User, admin_id)
        assert verify_password('Existing#2026', stored.password_hash) is True
        assert verify_password('New#2026', stored.password_hash) is False
        assert stored.role == 'admin'
        assert stored.is_active is True


def test_ensure_admin_user_preserves_existing_password_hash(tmp_path, monkeypatch) -> None:
    session_factory = build_sessionmaker(tmp_path)
    admin_id = _seed_admin(session_factory)
    monkeypatch.setattr(bootstrap.settings, 'INIT_ADMIN_USERNAME', 'admin')
    monkeypatch.setattr(bootstrap.settings, 'INIT_ADMIN_PASSWORD', 'New#2026')
    monkeypatch.setattr(bootstrap.settings, 'INIT_ADMIN_NAME', 'System Admin')

    with session_factory() as db:
        user = bootstrap.ensure_admin_user(db)
        assert user.id == admin_id
        stored = db.get(User, admin_id)
        assert verify_password('Existing#2026', stored.password_hash) is True
        assert verify_password('New#2026', stored.password_hash) is False
        assert stored.role == 'admin'
        assert stored.is_active is True


def test_create_admin_creates_missing_admin_with_requested_password(tmp_path, monkeypatch) -> None:
    session_factory = build_sessionmaker(tmp_path)
    module = _load_create_admin_module()
    monkeypatch.setattr(module, 'get_sessionmaker', lambda: session_factory)

    user = module.create_admin('admin', 'Initial#2026', 'System Admin')

    with session_factory() as db:
        stored = db.get(User, user.id)
        assert stored.username == 'admin'
        assert verify_password('Initial#2026', stored.password_hash) is True
        assert stored.role == 'admin'
        assert stored.data_scope_type == 'all'
