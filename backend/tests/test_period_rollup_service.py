from __future__ import annotations

from datetime import date
from typing import Any, cast

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.reports import DailyReportHistoryRecord, OperationPeriodSnapshot
from app.services.report.period_rollup import build_operation_period_snapshot


_MISSING = object()


def _history_row(
    day: date,
    output: Any,
    cost: Any,
    *,
    electricity: float | None = None,
    gas: float | None = None,
    source_snapshot_id: int | None = None,
) -> DailyReportHistoryRecord:
    facts = {
        "total_output_daily": {"value": output, "unit": "吨"},
        "verified_cost_total": {"value": cost, "unit": "元"},
    }
    if electricity is not None:
        facts["electricity_fee"] = {"value": electricity, "unit": "元"}
    if gas is not None:
        facts["gas_fee"] = {"value": gas, "unit": "元"}
    return DailyReportHistoryRecord(
        report_type="daily",
        business_date=day,
        period_type="day",
        period_start=day,
        period_end=day,
        report_text=f"{day.isoformat()} 日报",
        report_payload={"facts": facts},
        source_summary={"source_status": {"mes": "ok"}},
        source_snapshot_id=source_snapshot_id,
        facts_hash=f"{day.strftime('%Y%m%d'):0<64}"[:64],
        text_hash=f"{day.strftime('%d%m%Y'):0<64}"[:64],
    )


def _history_row_from_facts(day: date, facts: dict[str, Any]) -> DailyReportHistoryRecord:
    return DailyReportHistoryRecord(
        report_type="daily",
        business_date=day,
        period_type="day",
        period_start=day,
        period_end=day,
        report_text=f"{day.isoformat()} 日报",
        report_payload={"facts": facts},
        source_summary={"source_status": {"mes": "ok"}},
        facts_hash=f"{day.strftime('%Y%m%d'):0<64}"[:64],
        text_hash=f"{day.strftime('%d%m%Y'):0<64}"[:64],
    )


def test_build_month_and_year_rollups_from_archived_daily_reports() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyReportHistoryRecord.__table__),
            cast(Table, OperationPeriodSnapshot.__table__),
        ],
    )
    db = Session(engine)
    db.add_all(
        [
            _history_row(
                date(2026, 6, 1),
                100.0,
                80000.0,
                electricity=1000.0,
                gas=2000.0,
                source_snapshot_id=10,
            ),
            _history_row(
                date(2026, 6, 19),
                366.0,
                299300.0,
                electricity=3000.0,
                gas=4000.0,
                source_snapshot_id=11,
            ),
            _history_row(date(2026, 1, 1), 50.0, 50000.0, source_snapshot_id=12),
        ]
    )
    db.commit()

    month_snapshot = build_operation_period_snapshot(
        db,
        period_type="month",
        target_date=date(2026, 6, 19),
        trace_id="trace-month",
    )
    year_snapshot = build_operation_period_snapshot(
        db,
        period_type="year",
        target_date=date(2026, 6, 19),
        trace_id="trace-year",
    )

    assert month_snapshot.period_start == date(2026, 6, 1)
    assert month_snapshot.period_end == date(2026, 6, 19)
    assert month_snapshot.cumulative_metrics["total_output"]["value"] == 466.0
    assert month_snapshot.cumulative_metrics["verified_cost_total"]["value"] == 379300.0
    assert year_snapshot.period_start == date(2026, 1, 1)
    assert year_snapshot.cumulative_metrics["total_output"]["value"] == 516.0
    assert year_snapshot.trace_id == "trace-year"
    db.commit()

    saved_month = db.get(OperationPeriodSnapshot, month_snapshot.id)
    assert saved_month is not None
    assert saved_month.analysis_payload["period_label"] == "2026-06-01 至 2026-06-19"
    assert saved_month.analysis_payload["sections"]["cost"]["cost_per_ton"] == "813.95元/吨"
    assert saved_month.analysis_payload["sections"]["cost"]["electricity_fee"] == "4000.0元"
    assert saved_month.analysis_payload["sections"]["cost"]["gas_fee"] == "6000.0元"
    assert saved_month.analysis_payload["sections"]["trace"]["daily_report_count"] == 2
    assert saved_month.analysis_payload["sections"]["trace"]["snapshot_count"] == 2


def test_month_rollup_converts_template_total_cost_10k_to_verified_cost_total_yuan() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyReportHistoryRecord.__table__),
            cast(Table, OperationPeriodSnapshot.__table__),
        ],
    )
    db = Session(engine)
    db.add(
        _history_row_from_facts(
            date(2026, 6, 19),
            {
                "total_output_daily": {"value": 366.0, "unit": "吨"},
                "total_cost_10k": {"value": 29.93, "unit": "万元"},
            },
        )
    )
    db.commit()

    month_snapshot = build_operation_period_snapshot(
        db,
        period_type="month",
        target_date=date(2026, 6, 19),
        trace_id="trace-month-cost-10k",
    )

    assert month_snapshot.cumulative_metrics["verified_cost_total"]["value"] == 299300.0
    assert month_snapshot.cumulative_metrics["verified_cost_total"]["unit"] == "元"
    assert "total_cost_10k" in month_snapshot.cumulative_metrics["verified_cost_total"]["source_fields"]
    assert not [
        item
        for item in month_snapshot.analysis_payload["sections"]["trace"]["invalid_metrics"]
        if item["field"] == "verified_cost_total"
    ]


def test_month_rollup_uses_latest_daily_report_version_per_business_date() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyReportHistoryRecord.__table__),
            cast(Table, OperationPeriodSnapshot.__table__),
        ],
    )
    db = Session(engine)
    june_first = _history_row(date(2026, 6, 1), 100.0, 80000.0)
    old_june_nineteenth = _history_row(date(2026, 6, 19), 100.0, 80000.0)
    latest_june_nineteenth = _history_row(date(2026, 6, 19), 366.0, 299300.0)
    db.add_all([june_first, old_june_nineteenth, latest_june_nineteenth])
    db.commit()

    month_snapshot = build_operation_period_snapshot(
        db,
        period_type="month",
        target_date=date(2026, 6, 19),
        trace_id="trace-month-dedupe",
    )

    assert month_snapshot.cumulative_metrics["total_output"]["value"] == 466.0
    assert month_snapshot.source_daily_report_ids == [june_first.id, latest_june_nineteenth.id]
    assert old_june_nineteenth.id not in month_snapshot.source_daily_report_ids
    assert month_snapshot.analysis_payload["sections"]["trace"]["daily_report_count"] == 2


def test_build_month_rollup_updates_existing_snapshot_for_same_period() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyReportHistoryRecord.__table__),
            cast(Table, OperationPeriodSnapshot.__table__),
        ],
    )
    db = Session(engine)
    june_first = _history_row(date(2026, 6, 1), 100.0, 80000.0)
    db.add(june_first)
    db.commit()

    first_snapshot = build_operation_period_snapshot(
        db,
        period_type="month",
        target_date=date(2026, 6, 2),
        trace_id="trace-first",
    )
    first_snapshot_id = first_snapshot.id
    assert first_snapshot.missing_dates == ["2026-06-02"]
    db.commit()

    june_second = _history_row(date(2026, 6, 2), 200.0, 120000.0)
    db.add(june_second)
    db.commit()

    second_snapshot = build_operation_period_snapshot(
        db,
        period_type="month",
        target_date=date(2026, 6, 2),
        trace_id="trace-second",
    )

    assert second_snapshot.id == first_snapshot_id
    assert second_snapshot.cumulative_metrics["total_output"]["value"] == 300.0
    assert second_snapshot.cumulative_metrics["verified_cost_total"]["value"] == 200000.0
    assert second_snapshot.missing_dates == []
    assert second_snapshot.trace_id == "trace-second"
    assert db.query(OperationPeriodSnapshot).count() == 1


def test_build_year_rollup_updates_existing_snapshot_for_same_period() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyReportHistoryRecord.__table__),
            cast(Table, OperationPeriodSnapshot.__table__),
        ],
    )
    db = Session(engine)
    january_first = _history_row(date(2026, 1, 1), 50.0, 50000.0)
    old_june_nineteenth = _history_row(date(2026, 6, 19), 100.0, 80000.0)
    db.add_all([january_first, old_june_nineteenth])
    db.commit()

    first_snapshot = build_operation_period_snapshot(
        db,
        period_type="year",
        target_date=date(2026, 6, 19),
        trace_id="trace-year-first",
    )
    first_snapshot_id = first_snapshot.id
    assert first_snapshot.cumulative_metrics["total_output"]["value"] == 150.0
    db.commit()

    latest_june_nineteenth = _history_row(date(2026, 6, 19), 366.0, 299300.0)
    db.add(latest_june_nineteenth)
    db.commit()

    second_snapshot = build_operation_period_snapshot(
        db,
        period_type="year",
        target_date=date(2026, 6, 19),
        trace_id="trace-year-second",
    )

    assert second_snapshot.id == first_snapshot_id
    assert second_snapshot.trace_id == "trace-year-second"
    assert second_snapshot.cumulative_metrics["total_output"]["value"] == 416.0
    assert second_snapshot.cumulative_metrics["verified_cost_total"]["value"] == 349300.0
    assert latest_june_nineteenth.id in second_snapshot.source_daily_report_ids
    assert old_june_nineteenth.id not in second_snapshot.source_daily_report_ids
    assert (
        db.query(OperationPeriodSnapshot)
        .filter(OperationPeriodSnapshot.period_type == "year")
        .filter(OperationPeriodSnapshot.period_start == date(2026, 1, 1))
        .filter(OperationPeriodSnapshot.period_end == date(2026, 6, 19))
        .count()
        == 1
    )


def test_month_rollup_traces_invalid_critical_metrics_as_risk() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyReportHistoryRecord.__table__),
            cast(Table, OperationPeriodSnapshot.__table__),
        ],
    )
    db = Session(engine)
    db.add_all(
        [
            _history_row(date(2026, 6, 1), 100.0, None),
            _history_row(date(2026, 6, 2), 200.0, True),
        ]
    )
    db.commit()

    snapshot = build_operation_period_snapshot(
        db,
        period_type="month",
        target_date=date(2026, 6, 2),
        trace_id="trace-invalid",
    )

    invalid_metrics = snapshot.analysis_payload["sections"]["trace"]["invalid_metrics"]
    assert {item["business_date"] for item in invalid_metrics} == {"2026-06-01", "2026-06-02"}
    assert {item["field"] for item in invalid_metrics} == {"verified_cost_total"}
    assert all(item["reason"] for item in invalid_metrics)
    assert any("无效关键指标" in risk for risk in snapshot.analysis_payload["risks"])


@pytest.mark.parametrize(
    ("field", "bad_payload", "expected_reason"),
    [
        ("total_output_daily", _MISSING, "missing"),
        ("total_output_daily", {"value": None, "unit": "吨"}, "missing_value"),
        ("total_output_daily", {"value": True, "unit": "吨"}, "invalid_value"),
        ("total_output_daily", "bad-structure", "invalid_structure"),
        ("verified_cost_total", _MISSING, "missing"),
        ("verified_cost_total", {"value": None, "unit": "元"}, "missing_value"),
        ("verified_cost_total", {"value": True, "unit": "元"}, "invalid_value"),
        ("verified_cost_total", "bad-structure", "invalid_structure"),
    ],
)
def test_period_rollup_traces_invalid_critical_metric_variants(
    field: str,
    bad_payload: Any,
    expected_reason: str,
) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyReportHistoryRecord.__table__),
            cast(Table, OperationPeriodSnapshot.__table__),
        ],
    )
    db = Session(engine)
    facts: dict[str, Any] = {
        "total_output_daily": {"value": 100.0, "unit": "吨"},
        "verified_cost_total": {"value": 1000.0, "unit": "元"},
    }
    if bad_payload is _MISSING:
        facts.pop(field)
    else:
        facts[field] = bad_payload
    db.add(_history_row_from_facts(date(2026, 6, 19), facts))
    db.commit()

    snapshot = build_operation_period_snapshot(
        db,
        period_type="month",
        target_date=date(2026, 6, 19),
        trace_id=f"trace-invalid-{field}",
    )

    invalid_metrics = snapshot.analysis_payload["sections"]["trace"]["invalid_metrics"]
    assert {
        "business_date": "2026-06-19",
        "field": field,
        "reason": expected_reason,
    } in invalid_metrics
    assert any("无效关键指标" in risk for risk in snapshot.analysis_payload["risks"])
