from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models.master import Workshop
from app.models.system import User
from app.services.yield_matrix_delivery_target_service import resolve_yield_matrix_delivery_targets


def build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'yield-matrix-targets.db'}", future=True)
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

        payload = resolve_yield_matrix_delivery_targets(db, delivery_scope='factory', settings=build_settings())

    assert payload['resolution_status'] == 'resolved'
    assert payload['publisher_delivery_target'] == 'management'
    assert payload['publisher_target_key'] == 'management'
    assert payload['resolved_targets'][0]['logical_type'] == 'factory-observer'


def test_resolve_workshop_scope_accepts_matrix_workshop_key(tmp_path) -> None:
    with build_session(tmp_path) as db:
        db.add(Workshop(id=10, code='LZ1450', name='1450冷轧车间', workshop_type='cold_roll', sort_order=1, is_active=True))
        db.add(User(id=1, username='observer', password_hash='x', name='Obs', role='workshop_director', workshop_id=10, is_active=True))
        db.commit()

        payload = resolve_yield_matrix_delivery_targets(
            db,
            delivery_scope='workshop:cold_roll_1450',
            settings=build_settings(WECOM_BOT_WORKSHOP_WEBHOOK_MAP='{"10":"https://example.invalid/workshop-10"}'),
        )

    assert payload['resolution_status'] == 'resolved'
    assert payload['publisher_delivery_target'] == 'workshop'
    assert payload['publisher_target_key'] == '10'
    assert payload['resolved_targets'][0]['channel_key'] == '10'


def test_resolve_workshop_scope_conflict_falls_back_to_management(tmp_path) -> None:
    with build_session(tmp_path) as db:
        db.add_all(
            [
                Workshop(id=10, code='LZ2050', name='2050冷轧车间', workshop_type='cold_roll', sort_order=1, is_active=True),
                Workshop(id=11, code='LZ1650', name='1650冷轧车间', workshop_type='cold_roll', sort_order=2, is_active=True),
                User(id=3, username='ops', password_hash='x', name='Ops', role='ops-implementer', is_active=True),
            ]
        )
        db.commit()

        payload = resolve_yield_matrix_delivery_targets(
            db,
            delivery_scope='workshop:cold_roll_1650_2050',
            settings=build_settings(),
        )

    assert payload['resolution_status'] == 'conflict'
    assert payload['publisher_delivery_target'] == 'management'
