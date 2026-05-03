from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, create_engine, select


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / 'alembic'
    / 'versions'
    / '0026_unique_user_dingtalk_bindings.py'
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location('migration_0026_unique_user_dingtalk_bindings', MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_dingtalk_unique_binding_migration_keeps_active_user_binding(monkeypatch) -> None:
    module = _load_migration_module()
    engine = create_engine('sqlite:///:memory:', future=True)
    metadata = MetaData()
    users = Table(
        'users',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('username', String(64), nullable=False),
        Column('is_active', Boolean, nullable=False),
        Column('dingtalk_user_id', String(64), nullable=True),
        Column('dingtalk_union_id', String(64), nullable=True),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            users.insert(),
            [
                {'id': 1, 'username': 'inactive_old', 'is_active': False, 'dingtalk_user_id': 'dt_dup', 'dingtalk_union_id': 'union_dup'},
                {'id': 2, 'username': 'active_new', 'is_active': True, 'dingtalk_user_id': 'dt_dup', 'dingtalk_union_id': 'union_dup'},
                {'id': 3, 'username': 'active_other', 'is_active': True, 'dingtalk_user_id': 'dt_other', 'dingtalk_union_id': 'union_other'},
            ],
        )
        monkeypatch.setattr(module.op, 'execute', lambda statement: conn.execute(statement))

        module._normalize_and_clear_duplicates('dingtalk_user_id')
        module._normalize_and_clear_duplicates('dingtalk_union_id')

        rows = conn.execute(select(users.c.id, users.c.dingtalk_user_id, users.c.dingtalk_union_id).order_by(users.c.id)).all()

    assert rows == [(1, None, None), (2, 'dt_dup', 'union_dup'), (3, 'dt_other', 'union_other')]


def test_dingtalk_unique_binding_migration_trims_non_empty_bindings(monkeypatch) -> None:
    module = _load_migration_module()
    engine = create_engine('sqlite:///:memory:', future=True)
    metadata = MetaData()
    users = Table(
        'users',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('username', String(64), nullable=False),
        Column('is_active', Boolean, nullable=False),
        Column('dingtalk_user_id', String(64), nullable=True),
        Column('dingtalk_union_id', String(64), nullable=True),
    )
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            users.insert(),
            [
                {'id': 1, 'username': 'blank', 'is_active': True, 'dingtalk_user_id': '  ', 'dingtalk_union_id': '   '},
                {'id': 2, 'username': 'trimmed', 'is_active': True, 'dingtalk_user_id': ' dt_1 ', 'dingtalk_union_id': ' union_1 '},
            ],
        )
        monkeypatch.setattr(module.op, 'execute', lambda statement: conn.execute(statement))

        module._normalize_and_clear_duplicates('dingtalk_user_id')
        module._normalize_and_clear_duplicates('dingtalk_union_id')

        rows = conn.execute(select(users.c.id, users.c.dingtalk_user_id, users.c.dingtalk_union_id).order_by(users.c.id)).all()

    assert rows == [(1, None, None), (2, 'dt_1', 'union_1')]
