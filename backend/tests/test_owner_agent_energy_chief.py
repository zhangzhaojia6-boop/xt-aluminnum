"""TDD: energy_chief owner-agent (§3.1)."""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.energy import MachineEnergyDailyCompare, MachineEnergyRecord
from app.models.master import Equipment, Workshop
from app.models.production import MobileShiftReport
from app.models.reconciliation import DataReconciliationItem
from app.models.shift import ShiftConfig
from app.services.owner_agents import energy_chief as ec_agent


@pytest.fixture
def db_seeded(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    ws = Workshop(code='ZR2', name='铸轧二', is_active=True)
    sc = ShiftConfig(
        code='LONG', name='长白班', shift_type='day',
        start_time=time(7, 30), end_time=time(15, 30),
    )
    s.add_all([ws, sc])
    s.commit()
    eq = Equipment(
        code='ZR2-3', name='3号机', workshop_id=ws.id,
        equipment_type='machine', operational_status='running',
    )
    s.add(eq)
    s.commit()
    rpt = MobileShiftReport(
        business_date=date(2026, 5, 24),
        shift_config_id=sc.id,
        workshop_id=ws.id,
    )
    s.add(rpt)
    s.commit()
    try:
        yield s, rpt.id, eq.id, ws.id
    finally:
        s.close()


def test_upsert_shift_record_inserts_then_updates(db_seeded):
    s, rpt_id, eq_id, _ws_id = db_seeded
    ec_agent.upsert_shift_record(
        s, shift_report_id=rpt_id, machine_id=eq_id,
        machine_code='ZR2-3', machine_name='3号机',
        energy_kwh=1000.0, gas_m3=200.0,
    )
    s.commit()
    ec_agent.upsert_shift_record(
        s, shift_report_id=rpt_id, machine_id=eq_id,
        machine_code='ZR2-3', machine_name='3号机',
        energy_kwh=1100.0, gas_m3=220.0,
    )
    s.commit()

    rows = s.query(MachineEnergyRecord).filter(
        MachineEnergyRecord.shift_report_id == rpt_id,
        MachineEnergyRecord.machine_id == eq_id,
    ).all()
    assert len(rows) == 1
    assert float(rows[0].energy_kwh) == 1100.0
    assert float(rows[0].gas_m3) == 220.0


def test_upsert_daily_compare_writes_arrow(db_seeded):
    s, _rpt_id, eq_id, ws_id = db_seeded
    bd = date(2026, 5, 24)
    ec_agent.upsert_daily_compare(
        s, business_date=bd, machine_id=eq_id, workshop_id=ws_id,
        gas_per_ton_today=18.5, gas_per_ton_yesterday=19.0,
        gas_per_ton_target=18.0, compare_arrow='↓',
    )
    s.commit()

    row = s.query(MachineEnergyDailyCompare).filter(
        MachineEnergyDailyCompare.business_date == bd,
        MachineEnergyDailyCompare.machine_id == eq_id,
    ).one()
    assert float(row.gas_per_ton_today) == 18.5
    assert row.compare_arrow == '↓'


def test_record_reconciliation_marks_ok_within_tolerance(db_seeded):
    s, _r, _e, _w = db_seeded
    bd = date(2026, 5, 24)
    ec_agent.record_meter_vs_shifts_reconciliation(
        s, business_date=bd,
        dimension_key='ZR2', field_name='gas_m3',
        meter_cumulative=300.0, sum_of_shifts=300.005,
        tolerance=0.01,
    )
    s.commit()
    item = s.query(DataReconciliationItem).one()
    assert item.status == 'ok'
    assert item.reconciliation_type == 'energy_meter_vs_shifts'


def test_record_reconciliation_marks_open_when_outside_tolerance(db_seeded):
    s, _r, _e, _w = db_seeded
    bd = date(2026, 5, 24)
    ec_agent.record_meter_vs_shifts_reconciliation(
        s, business_date=bd,
        dimension_key='ZR2', field_name='gas_m3',
        meter_cumulative=300.0, sum_of_shifts=290.0,
        tolerance=0.5,
    )
    s.commit()
    item = s.query(DataReconciliationItem).one()
    assert item.status == 'open'
    assert float(item.diff_value) == pytest.approx(10.0)
