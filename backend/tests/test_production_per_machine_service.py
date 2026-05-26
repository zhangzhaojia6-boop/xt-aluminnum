"""TDD: per-machine production upsert (G13).

Backend service for ShiftReportForm's per-machine entry. Each machine
gets its own ``ShiftProductionData`` row keyed on
``(business_date, shift_config_id, workshop_id, equipment_id)``.
"""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.master import Equipment, Workshop
from app.models.production import ShiftProductionData
from app.models.shift import ShiftConfig
from app.services.production_per_machine_service import upsert_per_machine_rows


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
    eq1 = Equipment(code='ZR2-1', name='1#', workshop_id=ws.id,
                    equipment_type='machine', operational_status='running')
    eq2 = Equipment(code='ZR2-2', name='2#', workshop_id=ws.id,
                    equipment_type='machine', operational_status='running')
    s.add_all([eq1, eq2])
    s.commit()
    try:
        yield s, ws.id, sc.id, eq1.id, eq2.id
    finally:
        s.close()


def test_upsert_inserts_one_row_per_machine(db_seeded):
    s, ws_id, sc_id, eq1_id, eq2_id = db_seeded
    bd = date(2026, 5, 24)
    upsert_per_machine_rows(
        s, business_date=bd, shift_config_id=sc_id, workshop_id=ws_id,
        team_id=None,
        rows=[
            {'equipment_id': eq1_id, 'input_weight': 10.0, 'output_weight': 9.5, 'scrap_weight': 0.3},
            {'equipment_id': eq2_id, 'input_weight': 8.0, 'output_weight': 7.6, 'scrap_weight': 0.2},
        ],
    )
    s.commit()

    rows = s.query(ShiftProductionData).filter(
        ShiftProductionData.business_date == bd,
        ShiftProductionData.shift_config_id == sc_id,
        ShiftProductionData.workshop_id == ws_id,
    ).all()
    assert len(rows) == 2
    by_eq = {r.equipment_id: r for r in rows}
    assert float(by_eq[eq1_id].input_weight) == 10.0
    assert float(by_eq[eq1_id].output_weight) == 9.5
    assert float(by_eq[eq2_id].scrap_weight) == 0.2


def test_upsert_updates_existing_machine_row(db_seeded):
    s, ws_id, sc_id, eq1_id, _eq2 = db_seeded
    bd = date(2026, 5, 24)
    upsert_per_machine_rows(
        s, business_date=bd, shift_config_id=sc_id, workshop_id=ws_id, team_id=None,
        rows=[{'equipment_id': eq1_id, 'input_weight': 10.0, 'output_weight': 9.0, 'scrap_weight': 0.5}],
    )
    s.commit()
    upsert_per_machine_rows(
        s, business_date=bd, shift_config_id=sc_id, workshop_id=ws_id, team_id=None,
        rows=[{'equipment_id': eq1_id, 'input_weight': 12.0, 'output_weight': 11.0, 'scrap_weight': 0.4}],
    )
    s.commit()

    rows = s.query(ShiftProductionData).filter(
        ShiftProductionData.equipment_id == eq1_id,
        ShiftProductionData.data_status != 'voided',
    ).all()
    assert len(rows) == 1
    assert float(rows[0].input_weight) == 12.0
    assert float(rows[0].output_weight) == 11.0


def test_upsert_marks_data_source_mobile(db_seeded):
    s, ws_id, sc_id, eq1_id, _eq2 = db_seeded
    bd = date(2026, 5, 24)
    upsert_per_machine_rows(
        s, business_date=bd, shift_config_id=sc_id, workshop_id=ws_id, team_id=None,
        rows=[{'equipment_id': eq1_id, 'input_weight': 5.0, 'output_weight': 4.7, 'scrap_weight': 0.1}],
    )
    s.commit()
    row = s.query(ShiftProductionData).filter(ShiftProductionData.equipment_id == eq1_id).one()
    assert row.data_source == 'mobile'
    assert row.data_status == 'pending'


def test_upsert_with_empty_rows_is_noop(db_seeded):
    s, ws_id, sc_id, _eq1, _eq2 = db_seeded
    bd = date(2026, 5, 24)
    upsert_per_machine_rows(
        s, business_date=bd, shift_config_id=sc_id, workshop_id=ws_id, team_id=None, rows=[],
    )
    s.commit()
    assert s.query(ShiftProductionData).count() == 0
