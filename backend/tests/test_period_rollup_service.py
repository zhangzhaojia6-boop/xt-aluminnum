from __future__ import annotations

from datetime import date
from typing import cast

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.reports import DailyReportHistoryRecord, OperationPeriodSnapshot
from app.services.report.period_rollup import build_operation_period_snapshot


def _history_row(day: date, output: float, cost: float) -> DailyReportHistoryRecord:
    return DailyReportHistoryRecord(
        report_type="daily",
        business_date=day,
        period_type="day",
        period_start=day,
        period_end=day,
        report_text=f"{day.isoformat()} 日报",
        report_payload={
            "facts": {
                "total_output_daily": {"value": output, "unit": "吨"},
                "verified_cost_total": {"value": cost, "unit": "元"},
            }
        },
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
            _history_row(date(2026, 6, 1), 100.0, 80000.0),
            _history_row(date(2026, 6, 19), 366.0, 299300.0),
            _history_row(date(2026, 1, 1), 50.0, 50000.0),
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
