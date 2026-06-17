from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.services.report.output_skill_report_parser import parse_output_skill_daily_report


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized = re.sub(r"[ \t]+", "", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def _display(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 3)
    return value


def reconcile_rendered_daily_report(actual_text: str, expected_text: str) -> dict[str, Any]:
    actual_norm = _normalize_text(actual_text)
    expected_norm = _normalize_text(expected_text)
    actual_fields = parse_output_skill_daily_report(actual_text) if actual_text else {}
    expected_fields = parse_output_skill_daily_report(expected_text) if expected_text else {}

    differences: list[dict[str, Any]] = []
    matched = 0
    for field, expected_value in expected_fields.items():
        actual_value = actual_fields.get(field)
        if _display(actual_value) == _display(expected_value):
            matched += 1
            continue
        differences.append(
            {
                "field": field,
                "actual": actual_value,
                "expected": expected_value,
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
    }
