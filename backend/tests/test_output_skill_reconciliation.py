from __future__ import annotations

from pathlib import Path

from app.services.report.output_skill_reconciliation import reconcile_rendered_daily_report


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "output_skill_daily_reports"


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_reconciliation_reports_exact_text_match() -> None:
    expected = fixture_text("2026-6-16_日报正文.txt")

    result = reconcile_rendered_daily_report(expected, expected)

    assert result["exact_match"] is True
    assert result["char_match_rate"] == 100
    assert result["field_match_rate"] == 100
    assert result["differences"] == []


def test_reconciliation_accepts_numeric_difference_within_tolerance() -> None:
    expected = "6月16日，车间总产量日合计328吨。"
    actual = "6月16日，车间总产量日合计309吨。"

    result = reconcile_rendered_daily_report(actual, expected)

    assert result["field_match_rate"] == 100
    assert result["tolerance_matched_fields"] == 1
    assert result["numeric_tolerance"] == 20
    assert result["differences"] == []


def test_reconciliation_reports_first_difference_above_tolerance() -> None:
    expected = "6月16日，车间总产量日合计328吨。"
    actual = "6月16日，车间总产量日合计307吨。"

    result = reconcile_rendered_daily_report(actual, expected)

    assert result["exact_match"] is False
    assert result["differences"][0]["field"] == "total_output_daily"
    assert result["differences"][0]["actual"] == 307
    assert result["differences"][0]["expected"] == 328
    assert result["differences"][0]["delta"] == 21
