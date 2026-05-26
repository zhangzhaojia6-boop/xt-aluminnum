"""TDD: storage owner-agent (§3.5) — writes 4 storage scalars to a shift_report."""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.master import Workshop
from app.models.production import MobileShiftReport
from app.models.shift import ShiftConfig
from app.services.owner_agents import storage as storage_agent


@pytest.fixture
def db_with_report(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    ws = Workshop(code='CPK', name='成品库', is_active=True)
    sc = ShiftConfig(
        code='LONG', name='长白班', shift_type='day',
        start_time=time(7, 30), end_time=time(15, 30),
    )
    s.add_all([ws, sc])
    s.commit()
    rpt = MobileShiftReport(
        business_date=date(2026, 5, 24),
        shift_config_id=sc.id,
        workshop_id=ws.id,
    )
    s.add(rpt)
    s.commit()
    rpt_id = rpt.id
    try:
        yield s, rpt_id
    finally:
        s.close()


def test_write_storage_four_sets_all_scalars(db_with_report):
    s, rpt_id = db_with_report
    storage_agent.write_storage_four(
        s, shift_report_id=rpt_id,
        storage_prepared=10.0, storage_finished=20.0,
        shipment_weight=15.0, contract_received=8.0,
    )
    s.commit()

    row = s.query(MobileShiftReport).filter(MobileShiftReport.id == rpt_id).one()
    assert float(row.storage_prepared) == 10.0
    assert float(row.storage_finished) == 20.0
    assert float(row.shipment_weight) == 15.0
    assert float(row.contract_received) == 8.0


def test_write_storage_four_overwrites(db_with_report):
    s, rpt_id = db_with_report
    storage_agent.write_storage_four(
        s, shift_report_id=rpt_id,
        storage_prepared=1.0, storage_finished=2.0,
        shipment_weight=3.0, contract_received=4.0,
    )
    s.commit()
    storage_agent.write_storage_four(
        s, shift_report_id=rpt_id,
        storage_prepared=None, storage_finished=22.0,
        shipment_weight=None, contract_received=44.0,
    )
    s.commit()

    row = s.query(MobileShiftReport).filter(MobileShiftReport.id == rpt_id).one()
    assert row.storage_prepared is None
    assert float(row.storage_finished) == 22.0
    assert row.shipment_weight is None
    assert float(row.contract_received) == 44.0
