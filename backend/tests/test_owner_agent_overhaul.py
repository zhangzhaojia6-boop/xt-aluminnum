"""TDD: overhaul owner-agent (§3.8)."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.production import OverhaulDaily
from app.services.owner_agents import overhaul as overhaul_agent


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def test_upsert_inserts_then_updates(db_session):
    bd = date(2026, 5, 24)
    overhaul_agent.upsert_daily(
        db_session,
        business_date=bd,
        roller_grind_count=3,
        energy_kwh=100.0,
        gas_m3=5.5,
        note='初次',
    )
    db_session.commit()

    overhaul_agent.upsert_daily(
        db_session,
        business_date=bd,
        roller_grind_count=4,
        energy_kwh=120.0,
        gas_m3=6.5,
        note='更新',
    )
    db_session.commit()

    rows = db_session.query(OverhaulDaily).filter(OverhaulDaily.business_date == bd).all()
    assert len(rows) == 1
    r = rows[0]
    assert r.roller_grind_count == 4
    assert float(r.energy_kwh) == 120.0
    assert float(r.gas_m3) == 6.5
    assert r.note == '更新'


def test_upsert_clears_fields_on_none(db_session):
    bd = date(2026, 5, 24)
    overhaul_agent.upsert_daily(
        db_session, business_date=bd,
        roller_grind_count=3, energy_kwh=100.0, gas_m3=5.5, note='hi',
    )
    db_session.commit()
    overhaul_agent.upsert_daily(
        db_session, business_date=bd,
        roller_grind_count=None, energy_kwh=None, gas_m3=None, note=None,
    )
    db_session.commit()

    r = db_session.query(OverhaulDaily).filter(OverhaulDaily.business_date == bd).one()
    assert r.roller_grind_count is None
    assert r.energy_kwh is None
    assert r.gas_m3 is None
    assert r.note is None
