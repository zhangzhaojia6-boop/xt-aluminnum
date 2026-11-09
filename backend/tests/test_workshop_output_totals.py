from __future__ import annotations

from app.services.report.dashboard_builder import _workshop_output_totals


def test_workshop_without_any_source_is_unknown_not_zero() -> None:
    assert _workshop_output_totals([{}], legacy_shift_output=0.0) == (None, None, None)
    assert _workshop_output_totals([], legacy_shift_output=0.0) == (None, None, None)


def test_real_zero_from_a_source_stays_zero() -> None:
    payload = {'output': 0.0, 'process_output': 0.0, 'pass_count_total': 0, 'source_basis': 'mes'}

    assert _workshop_output_totals([payload], legacy_shift_output=0.0) == (0.0, 0.0, 0)


def test_workshop_with_output_keeps_its_values() -> None:
    payload = {'output': 12.5, 'process_output': 30.0, 'pass_count_total': 4}

    assert _workshop_output_totals([payload], legacy_shift_output=0.0) == (12.5, 30.0, 4)


def test_legacy_shift_output_still_fills_a_missing_source() -> None:
    assert _workshop_output_totals([{}], legacy_shift_output=8.0) == (8.0, 8.0, 0)
