"""TDD: shipment_outflow owner-agent (§3.6)."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.production import ShipmentOutflowRecord
from app.services.owner_agents import shipment_outflow as outflow_agent


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def test_add_record_appends(db_session):
    bd = date(2026, 5, 24)
    outflow_agent.add_record(
        db_session, business_date=bd, customer_name='客户A',
        batch_no='B-001', alloy_state='1060-O', finished_spec='0.5x1250',
        coil_weight=3.2, net_weight=3.0, source_workshop_code='CPK',
    )
    outflow_agent.add_record(
        db_session, business_date=bd, customer_name='客户B',
        batch_no='B-002', alloy_state='3003-H14',
    )
    db_session.commit()
    assert db_session.query(ShipmentOutflowRecord).count() == 2


def test_replace_for_date_replaces_only_target_date(db_session):
    bd = date(2026, 5, 24)
    other = date(2026, 5, 23)
    outflow_agent.add_record(db_session, business_date=other, customer_name='保留', batch_no='K')
    outflow_agent.add_record(db_session, business_date=bd, customer_name='将被清', batch_no='X')
    db_session.commit()

    outflow_agent.replace_for_date(
        db_session, business_date=bd,
        rows=[
            {'customer_name': '客户A', 'batch_no': 'B-001', 'coil_weight': 3.0, 'net_weight': 2.9},
            {'customer_name': '客户B', 'batch_no': 'B-002', 'coil_weight': 4.5, 'net_weight': 4.4},
        ],
    )
    db_session.commit()

    target = db_session.query(ShipmentOutflowRecord).filter(
        ShipmentOutflowRecord.business_date == bd
    ).all()
    assert len(target) == 2
    assert {r.batch_no for r in target} == {'B-001', 'B-002'}

    kept = db_session.query(ShipmentOutflowRecord).filter(
        ShipmentOutflowRecord.business_date == other
    ).count()
    assert kept == 1
