from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.agents.reconciler import ReconcilerAgent


class _FakeQuery:
    def __init__(self, *, rows=None):
        self._rows = rows or []

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, *, production_rows, report_rows):
        self._production_rows = production_rows
        self._report_rows = report_rows
        self._query_calls = 0

    def query(self, *args, **kwargs):
        self._query_calls += 1
        if self._query_calls == 1:
            return _FakeQuery(rows=self._production_rows)
        return _FakeQuery(rows=self._report_rows)


def test_reconciler_flags_when_missing_mobile_report() -> None:
    spd = SimpleNamespace(
        id=1,
        input_weight=100.0,
        output_weight=90.0,
        actual_headcount=10,
        data_status="confirmed",
        notes=None,
    )
    db = _FakeDB(production_rows=[spd], report_rows=[])
    agent = ReconcilerAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 6))

    assert len(decisions) == 1
    assert decisions[0].action.value == "auto_flag"
    assert spd.data_status == "flagged"
    assert "[自动核对] 无移动端报告关联" in spd.notes


def test_reconciler_flags_when_weight_diff_exceeds_tolerance() -> None:
    spd = SimpleNamespace(
        id=2,
        input_weight=100.0,
        output_weight=80.0,
        actual_headcount=10,
        data_status="confirmed",
        notes="已有备注",
    )
    report = SimpleNamespace(
        linked_production_data_id=2,
        input_weight=90.0,
        output_weight=100.0,
        attendance_count=10,
    )
    db = _FakeDB(production_rows=[spd], report_rows=[report])
    agent = ReconcilerAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 6))

    assert len(decisions) == 1
    assert decisions[0].action.value == "auto_flag"
    assert "投入重量差异" in decisions[0].reason
    assert "产出重量差异" in decisions[0].reason
    assert spd.data_status == "flagged"
    assert "已有备注" in spd.notes
    assert "[自动核对]" in spd.notes


def test_reconciler_flags_when_headcount_mismatch() -> None:
    spd = SimpleNamespace(
        id=3,
        input_weight=100.0,
        output_weight=95.0,
        actual_headcount=12,
        data_status="confirmed",
        notes=None,
    )
    report = SimpleNamespace(
        linked_production_data_id=3,
        input_weight=100.0,
        output_weight=95.0,
        attendance_count=10,
    )
    db = _FakeDB(production_rows=[spd], report_rows=[report])
    agent = ReconcilerAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 6))

    assert len(decisions) == 1
    assert decisions[0].action.value == "auto_flag"
    assert "出勤人数不一致" in decisions[0].reason
    assert spd.data_status == "flagged"


def test_reconciler_passes_when_within_tolerance() -> None:
    spd = SimpleNamespace(
        id=4,
        input_weight=100.0,
        output_weight=95.0,
        actual_headcount=10,
        data_status="confirmed",
        notes=None,
    )
    report = SimpleNamespace(
        linked_production_data_id=4,
        input_weight=97.0,
        output_weight=96.0,
        attendance_count=10,
    )
    db = _FakeDB(production_rows=[spd], report_rows=[report])
    agent = ReconcilerAgent()

    decisions = agent.execute(db=db, target_date=date(2026, 4, 6))

    assert len(decisions) == 1
    assert decisions[0].action.value == "auto_reconcile"
    assert spd.data_status == "confirmed"
    assert spd.notes is None
