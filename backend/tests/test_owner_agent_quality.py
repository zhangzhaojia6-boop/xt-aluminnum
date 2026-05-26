"""TDD: quality owner-agent (§3.3)."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.quality import QualityIssueLog, QualityYieldDaily
from app.services.owner_agents import quality as quality_agent


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def test_upsert_yield_inserts_then_updates(db_session):
    bd = date(2026, 5, 24)
    quality_agent.upsert_yield(
        db_session, business_date=bd, workshop_code='ZR2',
        yield_daily=0.92, yield_monthly=0.91,
        yield_target_m=0.93, yield_target_p_casting=0.91,
        yield_target_p_hot_roll=0.885, yield_overall_company=0.92,
        variance_arrow='↑',
    )
    db_session.commit()

    quality_agent.upsert_yield(
        db_session, business_date=bd, workshop_code='ZR2',
        yield_daily=0.94, yield_monthly=0.92,
        yield_target_m=0.93, yield_target_p_casting=0.91,
        yield_target_p_hot_roll=0.885, yield_overall_company=0.92,
        variance_arrow='↑',
    )
    db_session.commit()

    rows = db_session.query(QualityYieldDaily).all()
    assert len(rows) == 1
    assert float(rows[0].yield_daily) == 0.94
    assert rows[0].variance_arrow == '↑'


def test_upsert_yield_per_workshop_isolated(db_session):
    bd = date(2026, 5, 24)
    quality_agent.upsert_yield(db_session, business_date=bd, workshop_code='ZR2', yield_daily=0.9)
    quality_agent.upsert_yield(db_session, business_date=bd, workshop_code='ZR3', yield_daily=0.85)
    db_session.commit()
    assert db_session.query(QualityYieldDaily).count() == 2


def test_add_issue_appends(db_session):
    bd = date(2026, 5, 24)
    quality_agent.add_issue(
        db_session, business_date=bd, workshop_id=1,
        tracking_card_no='K-001', quality_issue_type='外观',
        quality_issue_desc='划痕', quality_photo_path='/tmp/a.jpg',
    )
    quality_agent.add_issue(
        db_session, business_date=bd, workshop_id=1,
        tracking_card_no='K-002', quality_issue_type='尺寸',
        quality_issue_desc='超差',
    )
    db_session.commit()
    assert db_session.query(QualityIssueLog).count() == 2
