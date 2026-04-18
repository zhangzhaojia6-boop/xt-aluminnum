from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models.master import Workshop
from app.models.system import User
from app.services.contract_delivery_target_service import resolve_contract_delivery_targets


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'contract-targets.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, User.__table__])
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'WECOM_BOT_MANAGEMENT_WEBHOOK_URL': 'https://example.invalid/management',
        'WECOM_BOT_WORKSHOP_WEBHOOK_MAP': '{}',
        'WECOM_BOT_TEAM_WEBHOOK_MAP': '{}',
    }
    values.update(overrides)
    return Settings(**values)


def test_resolve_factory_scope_routes_to_management(tmp_path) -> None:
    with build_session(tmp_path) as db:
        db.add_all(
            [
                User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True),
                User(id=2, username='mgr', password_hash='x', name='Mgr', role='manager', is_active=True),
            ]
        )
        db.commit()

        payload = resolve_contract_delivery_targets(db, delivery_scope='factory', settings=build_settings())

    assert payload['resolution_status'] == 'resolved'
    assert payload['publisher_delivery_target'] == 'management'
    assert payload['publisher_target_key'] == 'management'
    assert payload['resolved_targets'][0]['logical_type'] == 'factory-observer'
    assert payload['resolved_targets'][0]['user_ids'] == [1, 2]


def test_resolve_workshop_scope_conflict_adds_rollout_admin_fallback(tmp_path) -> None:
    with build_session(tmp_path) as db:
        db.add(Workshop(id=10, code='ZD', name='铸锭车间', workshop_type='casting', sort_order=1, is_active=True))
        db.add_all(
            [
                User(id=1, username='observer-1', password_hash='x', name='Obs1', role='reviewer', workshop_id=10, is_active=True),
                User(id=2, username='observer-2', password_hash='x', name='Obs2', role='workshop_director', workshop_id=10, is_active=True),
                User(id=3, username='ops', password_hash='x', name='Ops', role='ops-implementer', is_active=True),
            ]
        )
        db.commit()

        payload = resolve_contract_delivery_targets(
            db,
            delivery_scope='workshop:ZD',
            settings=build_settings(WECOM_BOT_MANAGEMENT_WEBHOOK_URL='https://example.invalid/management'),
        )

    assert payload['resolution_status'] == 'conflict'
    assert payload['publisher_delivery_target'] == 'management'
    assert payload['publisher_target_key'] == 'management'
    assert [item['logical_type'] for item in payload['resolved_targets']] == ['workshop-observer', 'rollout-admin']
    assert payload['resolved_targets'][0]['user_ids'] == [1, 2]
    assert payload['resolved_targets'][1]['user_ids'] == [3]


def test_resolve_workshop_scope_blocks_when_workshop_is_unknown(tmp_path) -> None:
    with build_session(tmp_path) as db:
        payload = resolve_contract_delivery_targets(db, delivery_scope='workshop:UNKNOWN', settings=build_settings())

    assert payload['resolution_status'] == 'blocked'
    assert payload['resolved_targets'] == []
    assert payload['publisher_delivery_target'] == 'management'
