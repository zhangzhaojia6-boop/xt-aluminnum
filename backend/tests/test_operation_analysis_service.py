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
    assert analysis["sections"]["cost"]["verified_cost_total"] == "4880207.0元"
    assert analysis["sections"]["cost"]["electricity_fee"] == "117200.0元"
    assert analysis["sections"]["cost"]["gas_fee"] == "182100.0元"
    assert analysis["sections"]["cost"]["cost_per_ton"] == "817.32元/吨"
    assert analysis["sections"]["energy"]["electricity_fee"] == "117200.0元"
    assert analysis["sections"]["energy"]["gas_fee"] == "182100.0元"
    assert analysis["sections"]["trace"]["daily_report_count"] == 3
    assert analysis["sections"]["trace"]["snapshot_count"] == 3
    assert analysis["risks"] == []


def test_analyze_operation_period_rounds_cost_per_ton_half_up() -> None:
    snapshot = OperationPeriodSnapshot(
        period_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 1),
        cumulative_metrics={
            "total_output": {"value": 6.0, "unit": "吨"},
            "verified_cost_total": {"value": 10.0, "unit": "元"},
        },
        source_daily_report_ids=[1],
        source_snapshot_ids=[],
        missing_dates=[],
        analysis_payload={},
        payload_hash="f" * 64,
    )

    analysis = analyze_operation_period(snapshot)

    assert analysis["sections"]["cost"]["cost_per_ton"] == "1.67元/吨"


def test_analyze_operation_period_reports_missing_dates_as_risk() -> None:
    snapshot = OperationPeriodSnapshot(
        period_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 2),
        cumulative_metrics={
            "total_output": {"value": 100.0, "unit": "吨"},
            "verified_cost_total": {"value": 1000.0, "unit": "元"},
        },
        source_daily_report_ids=[1],
        source_snapshot_ids=[10],
        missing_dates=["2026-06-02"],
        analysis_payload={},
        payload_hash="c" * 64,
    )

    analysis = analyze_operation_period(snapshot)

    assert analysis["sections"]["trace"]["missing_dates"] == ["2026-06-02"]
    assert analysis["risks"]


def test_analyze_operation_period_flags_nonzero_cost_without_output() -> None:
    snapshot = OperationPeriodSnapshot(
        period_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 1),
        cumulative_metrics={
            "total_output": {"value": 0.0, "unit": "吨"},
            "verified_cost_total": {"value": 1000.0, "unit": "元"},
        },
        source_daily_report_ids=[1],
        source_snapshot_ids=[],
        missing_dates=[],
        analysis_payload={},
        payload_hash="d" * 64,
    )

    analysis = analyze_operation_period(snapshot)

    assert analysis["sections"]["cost"]["cost_per_ton"] is None
    assert analysis["risks"]


def test_analyze_operation_period_allows_zero_output_when_cost_is_zero() -> None:
    snapshot = OperationPeriodSnapshot(
        period_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 1),
        cumulative_metrics={
            "total_output": {"value": 0.0, "unit": "吨"},
            "verified_cost_total": {"value": 0.0, "unit": "元"},
        },
        source_daily_report_ids=[],
        source_snapshot_ids=[],
        missing_dates=[],
        analysis_payload={},
        payload_hash="e" * 64,
    )

    analysis = analyze_operation_period(snapshot)

    assert analysis["sections"]["cost"]["cost_per_ton"] is None
    assert analysis["risks"] == []


def test_analyze_operation_period_keeps_invalid_metrics_in_trace_and_risks() -> None:
    invalid_metrics = [
        {
            "business_date": "2026-06-01",
            "field": "verified_cost_total",
            "reason": "missing_value",
        }
    ]
    snapshot = OperationPeriodSnapshot(
        period_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 1),
        cumulative_metrics={
            "total_output": {"value": 100.0, "unit": "吨"},
        },
        source_daily_report_ids=[1],
        source_snapshot_ids=[],
        missing_dates=[],
        analysis_payload={"invalid_metrics": invalid_metrics},
        payload_hash="g" * 64,
    )

    analysis = analyze_operation_period(snapshot)

    assert analysis["sections"]["trace"]["invalid_metrics"] == invalid_metrics
    assert any("无效关键指标" in risk for risk in analysis["risks"])
