"""TDD: consumable_stat owner-agent — consumable + attendance."""
from __future__ import annotations

from datetime import date, time

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.consumable import DailyConsumableLog
from app.models.master import Workshop
from app.models.production import MobileShiftReport
from app.models.shift import ShiftConfig
from app.services.owner_agents import consumable_stat as cs_agent


@pytest.fixture
def db_with_workshop(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    ws = Workshop(code='ZR2', name='铸轧二车间', is_active=True)
    s.add(ws)
    s.commit()
    try:
        yield s, ws.id
    finally:
        s.close()


def test_upsert_consumable_log_validates_and_strips_unknown(db_with_workshop):
    s, ws_id = db_with_workshop
    bd = date(2026, 5, 24)
    cs_agent.upsert_consumable_log(
        s, workshop_id=ws_id, business_date=bd,
        payload={
            'electricity_daily': 1000.0,
            'electricity_monthly': 28000.0,
            'liquefied_gas_per_ton': 0.05,
        },
        workshop_type='casting',
    )
    s.commit()

    row = s.query(DailyConsumableLog).filter(
        DailyConsumableLog.workshop_id == ws_id,
        DailyConsumableLog.business_date == bd,
    ).one()
    assert row.payload == {
        'electricity_daily': 1000.0,
        'electricity_monthly': 28000.0,
        'liquefied_gas_per_ton': 0.05,
    }
    assert row.workshop_type == 'casting'


def test_upsert_consumable_log_accepts_packaging_inbound_output(db_with_workshop):
    s, ws_id = db_with_workshop
    bd = date(2026, 6, 4)
    cs_agent.upsert_consumable_log(
        s,
        workshop_id=ws_id,
        business_date=bd,
        payload={
            'd40_per_ton': 0.2,
            'steel_plate_per_ton': 0.3,
            'packaging_inbound_output_tons': 18.5,
        },
        workshop_type='finishing',
    )
    s.commit()

    row = s.query(DailyConsumableLog).filter(
        DailyConsumableLog.workshop_id == ws_id,
        DailyConsumableLog.business_date == bd,
    ).one()
    assert row.payload == {
        'd40_per_ton': 0.2,
        'steel_plate_per_ton': 0.3,
        'packaging_inbound_output_tons': 18.5,
    }


def test_upsert_consumable_log_accepts_ingot_daily_summary(db_with_workshop):
    s, ws_id = db_with_workshop
    bd = date(2026, 6, 10)
    cs_agent.upsert_consumable_log(
        s,
        workshop_id=ws_id,
        business_date=bd,
        payload={
            'ingot_block_count': 16,
            'ingot_input_tons': 48.5,
            'ingot_output_tons': 47.2,
            'ingot_exception_note': '无异常',
        },
        workshop_type='casting',
    )
    s.commit()

    row = s.query(DailyConsumableLog).filter(
        DailyConsumableLog.workshop_id == ws_id,
        DailyConsumableLog.business_date == bd,
    ).one()
    assert row.payload == {
        'ingot_block_count': 16.0,
        'ingot_input_tons': 48.5,
        'ingot_output_tons': 47.2,
        'ingot_exception_note': '无异常',
    }


def test_upsert_consumable_log_rejects_unknown_field(db_with_workshop):
    s, ws_id = db_with_workshop
    with pytest.raises(ValidationError):
        cs_agent.upsert_consumable_log(
            s, workshop_id=ws_id, business_date=date(2026, 5, 24),
            payload={'unknown_field': 1.0},
        )


def test_upsert_consumable_log_replaces_payload_on_second_call(db_with_workshop):
    s, ws_id = db_with_workshop
    bd = date(2026, 5, 24)
    cs_agent.upsert_consumable_log(
        s, workshop_id=ws_id, business_date=bd,
        payload={'electricity_daily': 1.0, 'electricity_monthly': 30.0},
    )
    s.commit()
    cs_agent.upsert_consumable_log(
        s, workshop_id=ws_id, business_date=bd,
        payload={'electricity_daily': 2.0},
    )
    s.commit()

    row = s.query(DailyConsumableLog).one()
    assert row.payload == {'electricity_daily': 2.0}


def test_write_attendance_sets_payload_and_count(db_with_workshop):
    s, ws_id = db_with_workshop
    sc = ShiftConfig(
        code='LONG', name='长白班', shift_type='day',
        start_time=time(7, 30), end_time=time(15, 30),
    )
    s.add(sc)
    s.commit()
    rpt = MobileShiftReport(
        business_date=date(2026, 5, 24),
        shift_config_id=sc.id,
        workshop_id=ws_id,
    )
    s.add(rpt)
    s.commit()

    payload = {'machine_lines': {'ZR2-1': 4, 'ZR2-2': 3}, 'quench': 2, 'department': {'qc': 1}}
    cs_agent.write_attendance(
        s, shift_report_id=rpt.id,
        attendance_payload=payload, attendance_count=10,
    )
    s.commit()

    row = s.query(MobileShiftReport).filter(MobileShiftReport.id == rpt.id).one()
    assert row.attendance_payload == payload
    assert row.attendance_count == 10
