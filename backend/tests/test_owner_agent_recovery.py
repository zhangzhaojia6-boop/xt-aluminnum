"""TDD: recovery owner-agent (§3.7).

Single-table single-row upsert keyed on business_date.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.production import RecoveryDaily
from app.services.owner_agents import recovery as recovery_agent


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def test_upsert_inserts_when_no_row(db_session):
    bd = date(2026, 5, 24)
    row = recovery_agent.upsert_daily(db_session, business_date=bd, recovery_output_tons=12.5, note='hello')
    db_session.commit()

    fetched = db_session.query(RecoveryDaily).filter(RecoveryDaily.business_date == bd).one()
    assert fetched.id == row.id
    assert float(fetched.recovery_output_tons) == 12.5
    assert fetched.note == 'hello'


def test_upsert_updates_when_row_exists(db_session):
    bd = date(2026, 5, 24)
    recovery_agent.upsert_daily(db_session, business_date=bd, recovery_output_tons=10.0, note='first')
    db_session.commit()
    recovery_agent.upsert_daily(db_session, business_date=bd, recovery_output_tons=15.0, note='second')
    db_session.commit()

    rows = db_session.query(RecoveryDaily).filter(RecoveryDaily.business_date == bd).all()
    assert len(rows) == 1
    assert float(rows[0].recovery_output_tons) == 15.0
    assert rows[0].note == 'second'


def test_upsert_idempotent_on_repeated_call(db_session):
    bd = date(2026, 5, 24)
    a = recovery_agent.upsert_daily(db_session, business_date=bd, recovery_output_tons=8.0, note='x')
    db_session.commit()
    b = recovery_agent.upsert_daily(db_session, business_date=bd, recovery_output_tons=8.0, note='x')
    db_session.commit()

    assert a.id == b.id
    assert db_session.query(RecoveryDaily).count() == 1


def test_upsert_clears_note_when_none(db_session):
    bd = date(2026, 5, 24)
    recovery_agent.upsert_daily(db_session, business_date=bd, recovery_output_tons=8.0, note='kept')
    db_session.commit()
    recovery_agent.upsert_daily(db_session, business_date=bd, recovery_output_tons=8.0, note=None)
    db_session.commit()

    row = db_session.query(RecoveryDaily).filter(RecoveryDaily.business_date == bd).one()
    assert row.note is None
