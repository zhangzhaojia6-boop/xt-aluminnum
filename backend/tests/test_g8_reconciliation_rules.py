"""TDD: G8 三类 reconciliation 规则注册.

新增三类规则：
- cumulative_diff: 累计读数 vs 班次累加（容差判 ok/open）
- alloy_spec_vs_input: AlloySpecBreakdown.weight_tons SUM vs ProductionPlanDaily.input_daily
- attendance_detail_vs_total: MobileShiftReport.attendance_payload jsonb SUM vs attendance_count
"""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.master import Workshop
from app.models.production import (
    AlloySpecBreakdown,
    MobileShiftReport,
    ProductionPlanDaily,
)
from app.models.reconciliation import DataReconciliationItem
from app.models.shift import ShiftConfig
from app.services.reconciliation_service import (
    RECON_TYPES,
    generate_alloy_spec_vs_input,
    generate_attendance_detail_vs_total,
    generate_cumulative_diff,
)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def test_recon_types_includes_three_new_rules():
    assert 'cumulative_diff' in RECON_TYPES
    assert 'alloy_spec_vs_input' in RECON_TYPES
    assert 'attendance_detail_vs_total' in RECON_TYPES


def test_cumulative_diff_marks_ok_within_tolerance(db):
    bd = date(2026, 5, 24)
    item = generate_cumulative_diff(
        db, business_date=bd,
        dimension_key='ZR2', field_name='gas_m3',
        cumulative=300.0, sum_shifts=300.005,
        tolerance=0.01,
    )
    db.commit()
    assert item.status == 'ok'
    assert item.reconciliation_type == 'cumulative_diff'


def test_cumulative_diff_marks_open_outside_tolerance(db):
    bd = date(2026, 5, 24)
    item = generate_cumulative_diff(
        db, business_date=bd,
        dimension_key='ZR2', field_name='gas_m3',
        cumulative=300.0, sum_shifts=290.0,
        tolerance=0.5,
    )
    db.commit()
    assert item.status == 'open'
    assert float(item.diff_value) == pytest.approx(10.0)


def test_alloy_spec_vs_input_creates_open_when_mismatch(db):
    bd = date(2026, 5, 24)
    db.add(ProductionPlanDaily(
        business_date=bd, workshop_code='ZR2', input_daily=100.0,
    ))
    db.add_all([
        AlloySpecBreakdown(business_date=bd, workshop_code='ZR2',
                           alloy_grade='1060', weight_tons=40.0),
        AlloySpecBreakdown(business_date=bd, workshop_code='ZR2',
                           alloy_grade='3003', weight_tons=55.0),
    ])
    db.commit()

    created = generate_alloy_spec_vs_input(db, business_date=bd)
    db.commit()

    assert len(created) == 1
    item = created[0]
    assert item.reconciliation_type == 'alloy_spec_vs_input'
    assert item.status == 'open'
    assert 'workshop:ZR2' in item.dimension_key
    assert float(item.source_a_value) == 95.0
    assert float(item.source_b_value) == 100.0


def test_alloy_spec_vs_input_skips_when_balanced(db):
    bd = date(2026, 5, 24)
    db.add(ProductionPlanDaily(
        business_date=bd, workshop_code='ZR2', input_daily=100.0,
    ))
    db.add(AlloySpecBreakdown(
        business_date=bd, workshop_code='ZR2',
        alloy_grade='1060', weight_tons=100.0,
    ))
    db.commit()

    created = generate_alloy_spec_vs_input(db, business_date=bd)
    db.commit()
    assert created == []


def test_attendance_detail_vs_total_creates_open_when_mismatch(db):
    bd = date(2026, 5, 24)
    ws = Workshop(code='ZR2', name='铸轧二', is_active=True)
    sc = ShiftConfig(
        code='LONG', name='长白班', shift_type='day',
        start_time=time(7, 30), end_time=time(15, 30),
    )
    db.add_all([ws, sc])
    db.commit()
    rpt = MobileShiftReport(
        business_date=bd, shift_config_id=sc.id, workshop_id=ws.id,
        attendance_count=10,
        attendance_payload={
            'machine_lines': {'ZR2-1': 4, 'ZR2-2': 3},
            'quench': 2,
            'department': {'qc': 1, 'admin': 2},
        },
    )
    db.add(rpt)
    db.commit()

    created = generate_attendance_detail_vs_total(db, business_date=bd)
    db.commit()

    assert len(created) == 1
    item = created[0]
    assert item.reconciliation_type == 'attendance_detail_vs_total'
    assert item.status == 'open'
    assert float(item.source_a_value) == 12.0
    assert float(item.source_b_value) == 10.0


def test_attendance_detail_vs_total_skips_when_balanced(db):
    bd = date(2026, 5, 24)
    ws = Workshop(code='ZR2', name='铸轧二', is_active=True)
    sc = ShiftConfig(
        code='LONG', name='长白班', shift_type='day',
        start_time=time(7, 30), end_time=time(15, 30),
    )
    db.add_all([ws, sc])
    db.commit()
    rpt = MobileShiftReport(
        business_date=bd, shift_config_id=sc.id, workshop_id=ws.id,
        attendance_count=7,
        attendance_payload={
            'machine_lines': {'ZR2-1': 4, 'ZR2-2': 3},
        },
    )
    db.add(rpt)
    db.commit()

    created = generate_attendance_detail_vs_total(db, business_date=bd)
    db.commit()
    assert created == []


def test_attendance_detail_vs_total_skips_when_payload_missing(db):
    bd = date(2026, 5, 24)
    ws = Workshop(code='ZR2', name='铸轧二', is_active=True)
    sc = ShiftConfig(
        code='LONG', name='长白班', shift_type='day',
        start_time=time(7, 30), end_time=time(15, 30),
    )
    db.add_all([ws, sc])
    db.commit()
    rpt = MobileShiftReport(
        business_date=bd, shift_config_id=sc.id, workshop_id=ws.id,
        attendance_count=10, attendance_payload=None,
    )
    db.add(rpt)
    db.commit()

    created = generate_attendance_detail_vs_total(db, business_date=bd)
    db.commit()
    assert created == []


def test_cumulative_diff_zero_tolerance_treats_diff_as_open(db):
    bd = date(2026, 5, 24)
    item = generate_cumulative_diff(
        db, business_date=bd,
        dimension_key='ZR2', field_name='electricity_kwh',
        cumulative=1000.0, sum_shifts=1000.05,
        tolerance=0.0,
    )
    db.commit()
    assert item.status == 'open'
    assert float(item.diff_value) == pytest.approx(-0.05)


def test_orchestrator_dispatches_alloy_spec_and_attendance_detail(db, monkeypatch):
    """generate_reconciliation must invoke G8 rules when called without a type."""
    from types import SimpleNamespace
    from app.services import reconciliation_service

    bd = date(2026, 5, 24)
    db.add(ProductionPlanDaily(
        business_date=bd, workshop_code='ZR2', input_daily=100.0,
    ))
    db.add(AlloySpecBreakdown(
        business_date=bd, workshop_code='ZR2',
        alloy_grade='1060', weight_tons=80.0,
    ))
    ws = Workshop(code='ZR2', name='铸轧二', is_active=True)
    sc = ShiftConfig(
        code='LONG', name='长白班', shift_type='day',
        start_time=time(7, 30), end_time=time(15, 30),
    )
    db.add_all([ws, sc])
    db.commit()
    db.add(MobileShiftReport(
        business_date=bd, shift_config_id=sc.id, workshop_id=ws.id,
        attendance_count=8,
        attendance_payload={'machine_lines': {'ZR2-1': 5}},
    ))
    db.commit()

    monkeypatch.setattr(reconciliation_service, 'record_audit', lambda *_a, **_kw: None)

    items = reconciliation_service.generate_reconciliation(
        db,
        business_date=bd,
        reconciliation_type=None,
        operator=SimpleNamespace(id=1),
    )
    types_seen = {it.reconciliation_type for it in items}
    assert 'alloy_spec_vs_input' in types_seen
    assert 'attendance_detail_vs_total' in types_seen
