from __future__ import annotations

from pathlib import Path

from app.domain.daily_report_field_contract import normative_daily_report_fields
from app.services.report import output_skill_reconciliation
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
    assert result["numeric_tolerance"] is None
    assert result["field_tolerances"]["total_output_daily"] == 20
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
    assert result["differences"][0]["tolerance"] == 20


def test_reconciliation_uses_yield_percentage_point_tolerance() -> None:
    far = output_skill_reconciliation.reconcile_field_values(
        {"daily_yield_rate": 70.0},
        {"daily_yield_rate": 85.0},
    )
    close = output_skill_reconciliation.reconcile_field_values(
        {"daily_yield_rate": 84.8},
        {"daily_yield_rate": 85.0},
    )

    assert far["field_match_rate"] == 0
    assert far["differences"] == [
        {
            "field": "daily_yield_rate",
            "actual": 70.0,
            "expected": 85.0,
            "delta": 15.0,
            "tolerance": 0.2,
        }
    ]
    assert close["field_match_rate"] == 100
    assert close["tolerance_matched_fields"] == 1


def test_reconciliation_unknown_numeric_field_is_strict() -> None:
    result = output_skill_reconciliation.reconcile_field_values(
        {"unknown_numeric": 10}, {"unknown_numeric": 11}
    )

    assert result["field_match_rate"] == 0
    assert result["field_tolerances"] == {"unknown_numeric": 0.0}
    assert result["differences"][0]["tolerance"] == 0.0


def test_reconciliation_allows_explicit_per_field_override() -> None:
    result = output_skill_reconciliation.reconcile_field_values(
        {"daily_yield_rate": 80.0},
        {"daily_yield_rate": 85.0},
        field_tolerances={"daily_yield_rate": 5.0},
    )

    assert result["field_match_rate"] == 100
    assert result["field_tolerances"] == {"daily_yield_rate": 5.0}


def test_legacy_numeric_tolerance_is_accepted_but_ignored() -> None:
    result = reconcile_rendered_daily_report(
        "6月16日，车间总产量日合计119吨。日成品率84.7%。",
        "6月16日，车间总产量日合计100吨。日成品率85%。",
        numeric_tolerance=5,
    )

    assert result["legacy_numeric_tolerance_ignored"] == 5.0
    assert result["numeric_tolerance"] is None
    assert result["field_tolerances"]["total_output_daily"] == 20.0
    assert result["field_tolerances"]["daily_yield_rate"] == 0.2
    assert result["matched_fields"] == 2  # report_date and total output
    assert result["differences"][0]["field"] == "daily_yield_rate"
    assert result["differences"][0]["tolerance"] == 0.2


def test_normative_denominator_does_not_shrink_for_undeclared_reference_gaps() -> None:
    normative_fields = normative_daily_report_fields()
    reference_fields = normative_fields[:124]
    absent_fields = list(normative_fields[124:])
    values = {field_name: index for index, field_name in enumerate(reference_fields)}

    result = output_skill_reconciliation.reconcile_field_values(
        values,
        values,
        normative_fields=normative_fields,
    )

    assert result["reference_present_fields"] == 124
    assert result["declared_na_fields"] == []
    assert result["invalid_na_fields"] == []
    assert result["reference_absent_fields"] == absent_fields
    assert result["reference_absent_count"] == 3
    assert result["normative_fields"] == 127
    assert result["normative_denominator"] == 127
    assert result["normative_matched_fields"] == 124
    assert result["normative_coverage_rate"] == 97.64


def test_valid_explicit_na_reduces_normative_denominator() -> None:
    normative_fields = normative_daily_report_fields()
    reference_fields = normative_fields[:124]
    declared_na = list(normative_fields[124:])
    values = {field_name: index for index, field_name in enumerate(reference_fields)}

    result = output_skill_reconciliation.reconcile_field_values(
        values,
        values,
        normative_fields=normative_fields,
        declared_na_fields=declared_na,
    )

    assert result["reference_present_fields"] == 124
    assert result["declared_na_fields"] == declared_na
    assert result["invalid_na_fields"] == []
    assert result["reference_absent_fields"] == []
    assert result["reference_absent_count"] == 0
    assert result["normative_fields"] == 127
    assert result["normative_denominator"] == 124
    assert result["normative_matched_fields"] == 124
    assert result["normative_coverage_rate"] == 100.0


def test_unknown_or_duplicate_na_field_is_invalid_and_does_not_reduce_denominator() -> None:
    normative_fields = normative_daily_report_fields()
    reference_fields = normative_fields[:124]
    duplicate = normative_fields[124]
    values = {field_name: index for index, field_name in enumerate(reference_fields)}

    result = output_skill_reconciliation.reconcile_field_values(
        values,
        values,
        normative_fields=normative_fields,
        declared_na_fields=[duplicate, duplicate, "not_a_daily_report_field"],
    )

    assert result["declared_na_fields"] == []
    assert result["invalid_na_fields"] == [duplicate, "not_a_daily_report_field"]
    assert result["reference_absent_fields"] == list(normative_fields[124:])
    assert result["normative_denominator"] == 127
    assert result["normative_coverage_rate"] == 97.64
