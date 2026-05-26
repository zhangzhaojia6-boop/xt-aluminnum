"""TDD: planning owner-agent (§3.4)."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.production import AlloySpecBreakdown, ProductionPlanDaily
from app.services.owner_agents import planning as planning_agent


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def test_upsert_plan_inserts_then_updates(db_session):
    bd = date(2026, 5, 24)
    planning_agent.upsert_plan(
        db_session, business_date=bd, workshop_code='ZR2',
        input_daily=100.0, input_monthly=2500.0,
        contract_today=80.0, contract_total_remaining=1200.0,
        billet_total=300.0,
    )
    db_session.commit()
    planning_agent.upsert_plan(
        db_session, business_date=bd, workshop_code='ZR2',
        input_daily=150.0, input_monthly=2550.0,
        contract_today=90.0, contract_total_remaining=1110.0,
        billet_total=350.0,
    )
    db_session.commit()

    rows = db_session.query(ProductionPlanDaily).all()
    assert len(rows) == 1
    assert float(rows[0].input_daily) == 150.0
    assert float(rows[0].billet_total) == 350.0


def test_replace_alloy_breakdown_replaces_only_same_date_workshop(db_session):
    bd = date(2026, 5, 24)
    other_bd = date(2026, 5, 23)
    db_session.add(AlloySpecBreakdown(
        business_date=other_bd, workshop_code='ZR2',
        alloy_grade='1060', spec_text='kept', weight_tons=10.0,
    ))
    db_session.add(AlloySpecBreakdown(
        business_date=bd, workshop_code='ZR3',
        alloy_grade='3003', spec_text='kept-other-ws', weight_tons=20.0,
    ))
    db_session.commit()

    planning_agent.replace_alloy_breakdown(
        db_session, business_date=bd, workshop_code='ZR2',
        rows=[
            {'alloy_grade': '1060', 'spec_text': '0.5x1250', 'weight_tons': 12.0,
             'scrap_count_casting1': 1, 'scrap_count_casting2': 0},
            {'alloy_grade': '5052', 'spec_text': '1.0x1450', 'weight_tons': 8.5,
             'scrap_count_casting1': 0, 'scrap_count_casting2': 2},
        ],
    )
    db_session.commit()

    target_rows = db_session.query(AlloySpecBreakdown).filter(
        AlloySpecBreakdown.business_date == bd,
        AlloySpecBreakdown.workshop_code == 'ZR2',
    ).all()
    assert len(target_rows) == 2
    grades = {r.alloy_grade for r in target_rows}
    assert grades == {'1060', '5052'}

    kept = db_session.query(AlloySpecBreakdown).filter(
        AlloySpecBreakdown.spec_text == 'kept'
    ).count()
    assert kept == 1
    other_ws = db_session.query(AlloySpecBreakdown).filter(
        AlloySpecBreakdown.spec_text == 'kept-other-ws'
    ).count()
    assert other_ws == 1


def test_replace_alloy_breakdown_with_empty_iterable_clears(db_session):
    bd = date(2026, 5, 24)
    db_session.add(AlloySpecBreakdown(
        business_date=bd, workshop_code='ZR2',
        alloy_grade='1060', weight_tons=10.0,
    ))
    db_session.commit()
    planning_agent.replace_alloy_breakdown(
        db_session, business_date=bd, workshop_code='ZR2', rows=[],
    )
    db_session.commit()

    n = db_session.query(AlloySpecBreakdown).filter(
        AlloySpecBreakdown.business_date == bd,
        AlloySpecBreakdown.workshop_code == 'ZR2',
    ).count()
    assert n == 0
