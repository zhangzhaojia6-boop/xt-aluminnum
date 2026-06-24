from __future__ import annotations

from datetime import date

from app.models.reports import OperationPeriodSnapshot
from app.services.report.operation_analysis import analyze_operation_period


def test_analyze_monthly_operation_situation_returns_business_sections() -> None:
    snapshot = OperationPeriodSnapshot(
        period_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 19),
        cumulative_metrics={
            "total_output": {"value": 5971.0, "unit": "吨"},
            "verified_cost_total": {"value": 4880207.0, "unit": "元"},
            "electricity_fee": {"value": 117200.0, "unit": "元"},
            "gas_fee": {"value": 182100.0, "unit": "元"},
        },
        source_daily_report_ids=[1, 2, 3],
        source_snapshot_ids=[10, 11, 12],
        missing_dates=[],
        analysis_payload={},
        payload_hash="b" * 64,
    )

    analysis = analyze_operation_period(snapshot)

    assert analysis["period_label"] == "2026-06-01 至 2026-06-19"
    assert analysis["sections"]["production"]["total_output"] == "5971.0吨"
    assert analysis["sections"]["cost"]["cost_per_ton"] == "817.31元/吨"
    assert analysis["sections"]["trace"]["daily_report_count"] == 3
    assert analysis["risks"] == []
