from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.rule_config import RuleConfig
from app.rules.thresholds import DEFAULT_THRESHOLDS
from app.services import rule_config_service


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rule-config-service.db'}", future=True)
    Base.metadata.create_all(engine, tables=[RuleConfig.__table__])
    return sessionmaker(bind=engine, future=True)


def test_get_threshold_uses_fallback_when_db_is_empty(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    rule_config_service.invalidate_cache()
    with session_factory() as db:
        value = rule_config_service.get_threshold('MIN_WEIGHT', db=db)

    assert value == DEFAULT_THRESHOLDS['MIN_WEIGHT']


def test_get_threshold_prefers_workshop_then_factory_then_fallback(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    rule_config_service.invalidate_cache()
    with session_factory() as db:
        rule_config_service.set_threshold(
            db,
            scope_type='factory',
            scope_key=None,
            key='MAX_SINGLE_SHIFT_WEIGHT',
            value=80,
            updated_by=1,
        )
        rule_config_service.set_threshold(
            db,
            scope_type='workshop',
            scope_key='LZ01',
            key='MAX_SINGLE_SHIFT_WEIGHT',
            value=50,
            updated_by=1,
        )

        assert rule_config_service.get_threshold('MAX_SINGLE_SHIFT_WEIGHT', workshop_code='LZ01', db=db) == 50
        assert rule_config_service.get_threshold('MAX_SINGLE_SHIFT_WEIGHT', workshop_code='LZ02', db=db) == 80
        assert rule_config_service.get_threshold('MIN_ATTENDANCE', workshop_code='LZ01', db=db) == DEFAULT_THRESHOLDS['MIN_ATTENDANCE']


def test_set_threshold_invalidates_cache_immediately(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    rule_config_service.invalidate_cache()
    with session_factory() as db:
        rule_config_service.set_threshold(
            db,
            scope_type='workshop',
            scope_key='LZ01',
            key='MAX_SINGLE_SHIFT_WEIGHT',
            value=50,
            updated_by=1,
        )
        assert rule_config_service.get_threshold('MAX_SINGLE_SHIFT_WEIGHT', workshop_code='LZ01', db=db) == 50

        rule_config_service.set_threshold(
            db,
            scope_type='workshop',
            scope_key='LZ01',
            key='MAX_SINGLE_SHIFT_WEIGHT',
            value=45,
            updated_by=2,
        )

        assert rule_config_service.get_threshold('MAX_SINGLE_SHIFT_WEIGHT', workshop_code='LZ01', db=db) == 45

