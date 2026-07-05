from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.services.report.output_skill_report_parser import parse_output_skill_daily_report

MAX_NUMERIC_TOLERANCE = 20.0


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized = re.sub(r"[ \t]+", "", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def _display(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 3)
    return value


def reconcile_rendered_daily_report(
    actual_text: str,
    expected_text: str,
    *,
    numeric_tolerance: float = MAX_NUMERIC_TOLERANCE,
) -> dict[str, Any]:
    tolerance = _normalise_numeric_tolerance(numeric_tolerance)
    actual_norm = _normalize_text(actual_text)
    expected_norm = _normalize_text(expected_text)
    actual_fields = parse_output_skill_daily_report(actual_text) if actual_text else {}
    expected_fields = parse_output_skill_daily_report(expected_text) if expected_text else {}

    differences: list[dict[str, Any]] = []
    matched = 0
    tolerance_matched = 0
    for field, expected_value in expected_fields.items():
        actual_value = actual_fields.get(field)
        if _display(actual_value) == _display(expected_value):
            matched += 1
            continue
        numeric_delta = _numeric_delta(actual_value, expected_value)
        if numeric_delta is not None and numeric_delta <= tolerance:
            matched += 1
            tolerance_matched += 1
            continue
        differences.append(
            {
                "field": field,
                "actual": actual_value,
                "expected": expected_value,
                "delta": _display(numeric_delta) if numeric_delta is not None else None,
            }
        )

    expected_count = len(expected_fields)
    field_match_rate = round(matched / expected_count * 100, 2) if expected_count else 0.0
    char_match_rate = (
        round(SequenceMatcher(None, actual_norm, expected_norm).ratio() * 100, 2)
        if actual_norm or expected_norm
        else 100.0
    )

    return {
        "exact_match": actual_norm == expected_norm and bool(expected_norm),
        "char_match_rate": char_match_rate,
        "field_match_rate": field_match_rate,
        "matched_fields": matched,
        "expected_fields": expected_count,
        "differences": differences,
        "numeric_tolerance": tolerance,
        "tolerance_matched_fields": tolerance_matched,
    }


def _normalise_numeric_tolerance(value: Any) -> float:
    try:
        tolerance = float(value)
    except (TypeError, ValueError):
        return MAX_NUMERIC_TOLERANCE
    if tolerance < 0:
        return 0.0
    return min(tolerance, MAX_NUMERIC_TOLERANCE)


def _numeric_delta(actual_value: Any, expected_value: Any) -> float | None:
    if actual_value in (None, "") or expected_value in (None, ""):
        return None
    if not isinstance(actual_value, (int, float)) or not isinstance(expected_value, (int, float)):
        return None
    return abs(float(actual_value) - float(expected_value))
