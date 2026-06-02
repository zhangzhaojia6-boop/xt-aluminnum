"""Step 5 — owner-agent flow smoke tests.

Each Layer-2 owner-agent module has a fixed-schema entry helper
(see docs/truth-source-three-layer-schema.md §3.1-3.8). This file exercises
each helper end-to-end against an in-memory SQLite DB to confirm:
  - the upsert/append helper actually writes to its target table
  - re-running with the same key updates instead of duplicating
  - the row reads back with the values we passed in

Tests are kept narrow: they assert *the agent boundary writes the right
columns*, not the full reconciliation chain.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.consumable import DailyConsumableLog
from app.models.energy import (
    MachineEnergyDailyCompare,
    MachineEnergyRecord,
)
from app.models.production import (
    AlloySpecBreakdown,
    MobileShiftReport,
    OverhaulDaily,
    ProductionPlanDaily,
    RecoveryDaily,
    ShipmentOutflowRecord,
)
from app.models.quality import QualityIssueLog, QualityYieldDaily
from app.models.reconciliation import DataReconciliationItem
from app.services.owner_agents import (
    consumable_stat,
    energy_chief,
    overhaul,
    planning,
    quality,
    recovery,
    shipment_outflow,
    storage,
)


@pytest.fixture()
def db(tmp_path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'owner-agents.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            DailyConsumableLog.__table__,
            MachineEnergyRecord.__table__,
            MachineEnergyDailyCompare.__table__,
            MobileShiftReport.__table__,
            ProductionPlanDaily.__table__,
            AlloySpecBreakdown.__table__,
            ShipmentOutflowRecord.__table__,
            RecoveryDaily.__table__,
            OverhaulDaily.__table__,
            QualityYieldDaily.__table__,
            QualityIssueLog.__table__,
            DataReconciliationItem.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_shift_report(db: Session) -> int:
    row = MobileShiftReport(
        business_date=date(2026, 5, 27),
        shift_config_id=1,
        workshop_id=1,
        team_id=1,
        report_status='draft',
    )
    db.add(row)
    db.flush()
    return row.id


def test_energy_chief_writes_three_targets(db: Session):
    shift_report_id = _seed_shift_report(db)

    rec = energy_chief.upsert_shift_record(
        db,
        shift_report_id=shift_report_id,
        machine_id=42,
        machine_code='ZR2-1',
        machine_name='铸轧二车间 1#',
        energy_kwh=1234.5,
        gas_m3=678.9,
    )
    assert rec.id is not None and rec.energy_kwh == 1234.5

    rec2 = energy_chief.upsert_shift_record(
        db,
        shift_report_id=shift_report_id,
        machine_id=42,
        energy_kwh=999.9,
    )
    assert rec2.id == rec.id  # idempotent

    cmp_row = energy_chief.upsert_daily_compare(
        db,
        business_date=date(2026, 5, 27),
        machine_id=42,
        gas_per_ton_today=12.3,
        gas_per_ton_yesterday=12.0,
        gas_per_ton_target=11.8,
        compare_arrow='↑',
    )
    assert cmp_row.compare_arrow == '↑'
    assert float(cmp_row.gas_per_ton_today) == pytest.approx(12.3)

    item = energy_chief.record_meter_vs_shifts_reconciliation(
        db,
        business_date=date(2026, 5, 27),
        dimension_key='workshop:ZR2',
        field_name='gas_m3',
        meter_cumulative=1000.0,
        sum_of_shifts=999.5,
    )
    assert item.status == 'open'
    assert float(item.diff_value) == pytest.approx(0.5)


def test_consumable_stat_consumable_lock(db: Session):
    log = consumable_stat.upsert_consumable_log(
        db,
        workshop_id=1,
        business_date=date(2026, 5, 27),
        payload={
            'electricity_daily': 12000,
            'gas_compare': '↓',
            'liquefied_gas_per_ton': 12.3,
        },
        workshop_type='casting',
    )
    assert log.payload == {
        'electricity_daily': 12000.0,
        'gas_compare': '↓',
        'liquefied_gas_per_ton': 12.3,
    }

    log2 = consumable_stat.upsert_consumable_log(
        db,
        workshop_id=1,
        business_date=date(2026, 5, 27),
        payload={'electricity_daily': 13000},
        workshop_type='casting',
    )
    assert log2.id == log.id  # upsert
    assert log2.payload == {'electricity_daily': 13000.0}


def test_consumable_stat_attendance_payload(db: Session):
    shift_report_id = _seed_shift_report(db)
    row = consumable_stat.write_attendance(
        db,
        shift_report_id=shift_report_id,
        attendance_payload={'machine_lines': [{'code': 'ZR2-1', 'count': 4}]},
        attendance_count=4,
    )
    assert row.attendance_count == 4
    assert row.attendance_payload == {'machine_lines': [{'code': 'ZR2-1', 'count': 4}]}


def test_quality_yield_and_issue(db: Session):
    yld = quality.upsert_yield(
        db,
        business_date=date(2026, 5, 27),
        workshop_code='casting',
        yield_daily=0.92,
        yield_monthly=0.91,
        yield_target_p_casting=0.91,
        variance_arrow='↑',
    )
    assert float(yld.yield_daily) == pytest.approx(0.92)

    yld2 = quality.upsert_yield(
        db,
        business_date=date(2026, 5, 27),
        workshop_code='casting',
        yield_daily=0.93,
    )
    assert yld2.id == yld.id

    issue = quality.add_issue(
        db,
        business_date=date(2026, 5, 27),
        tracking_card_no='ZR2-1-20260527-0001',
        quality_issue_type='surface_scratch',
        quality_issue_desc='划伤',
    )
    assert issue.id is not None
    assert issue.quality_issue_type == 'surface_scratch'


def test_planning_plan_and_breakdown(db: Session):
    plan = planning.upsert_plan(
        db,
        business_date=date(2026, 5, 27),
        workshop_code='casting',
        input_daily=120.5,
        input_monthly=2890.0,
        contract_today=80.0,
        contract_total_remaining=1500.0,
        billet_total=300.0,
    )
    assert float(plan.input_daily) == pytest.approx(120.5)

    rows = planning.replace_alloy_breakdown(
        db,
        business_date=date(2026, 5, 27),
        workshop_code='casting',
        rows=[
            {'alloy_grade': '1060', 'spec_text': '7.5x1450', 'weight_tons': 60.0},
            {'alloy_grade': '3003', 'spec_text': '7.5x1280', 'weight_tons': 40.0},
        ],
    )
    assert len(rows) == 2

    rows2 = planning.replace_alloy_breakdown(
        db,
        business_date=date(2026, 5, 27),
        workshop_code='casting',
        rows=[{'alloy_grade': '5052', 'weight_tons': 30.0}],
    )
    assert len(rows2) == 1
    total = db.query(AlloySpecBreakdown).filter(
        AlloySpecBreakdown.business_date == date(2026, 5, 27),
        AlloySpecBreakdown.workshop_code == 'casting',
    ).count()
    assert total == 1  # replace, not append


def test_storage_four_scalars(db: Session):
    shift_report_id = _seed_shift_report(db)
    row = storage.write_storage_four(
        db,
        shift_report_id=shift_report_id,
        storage_prepared=100.0,
        storage_finished=80.0,
        shipment_weight=60.0,
        contract_received=120.0,
    )
    assert float(row.storage_prepared) == pytest.approx(100.0)
    assert float(row.contract_received) == pytest.approx(120.0)


def test_shipment_outflow_append_and_replace(db: Session):
    one = shipment_outflow.add_record(
        db,
        business_date=date(2026, 5, 27),
        customer_name='张三铝业',
        batch_no='B-001',
        coil_weight=2.5,
        net_weight=2.4,
        source_workshop_code='JQ',
    )
    assert one.id is not None
    assert one.batch_no == 'B-001'

    rows = shipment_outflow.replace_for_date(
        db,
        business_date=date(2026, 5, 27),
        rows=[
            {'customer_name': '李四', 'batch_no': 'B-100', 'coil_weight': 3.0, 'net_weight': 2.9},
            {'customer_name': '王五', 'batch_no': 'B-101', 'coil_weight': 2.0, 'net_weight': 1.95},
        ],
    )
    assert len(rows) == 2
    total = db.query(ShipmentOutflowRecord).filter(
        ShipmentOutflowRecord.business_date == date(2026, 5, 27)
    ).count()
    assert total == 2  # original B-001 was replaced


def test_recovery_upsert(db: Session):
    r1 = recovery.upsert_daily(
        db,
        business_date=date(2026, 5, 27),
        recovery_output_tons=18.5,
        note='今日回收正常',
    )
    assert float(r1.recovery_output_tons) == pytest.approx(18.5)

    r2 = recovery.upsert_daily(
        db,
        business_date=date(2026, 5, 27),
        recovery_output_tons=20.0,
        note=None,
    )
    assert r2.id == r1.id
    assert float(r2.recovery_output_tons) == pytest.approx(20.0)


def test_overhaul_upsert(db: Session):
    o1 = overhaul.upsert_daily(
        db,
        business_date=date(2026, 5, 27),
        roller_grind_count=3,
        energy_kwh=850.0,
        gas_m3=120.0,
        note=None,
    )
    assert o1.roller_grind_count == 3

    o2 = overhaul.upsert_daily(
        db,
        business_date=date(2026, 5, 27),
        roller_grind_count=5,
        energy_kwh=900.0,
        gas_m3=125.0,
        note='额外两根',
    )
    assert o2.id == o1.id
    assert o2.roller_grind_count == 5
