from __future__ import annotations

from types import SimpleNamespace

from app.services.report.daily_overview_builder import _process_row_pass_count
from app.services.report.dashboard_builder import _workshop_output_totals


def test_workshop_without_any_source_is_unknown_not_zero() -> None:
    assert _workshop_output_totals([{}], legacy_shift_output=0.0) == (None, None, None)
    assert _workshop_output_totals([], legacy_shift_output=0.0) == (None, None, None)


def test_real_zero_from_a_source_stays_zero() -> None:
    payload = {'output': 0.0, 'process_output': 0.0, 'pass_count_total': 0, 'source_basis': 'mes'}

    assert _workshop_output_totals([payload], legacy_shift_output=0.0) == (0.0, 0.0, None)


def test_workshop_with_output_keeps_its_values() -> None:
    payload = {'output': 12.5, 'process_output': 30.0, 'pass_count_total': 4}

    assert _workshop_output_totals([payload], legacy_shift_output=0.0) == (12.5, 30.0, 4)


def test_legacy_shift_output_still_fills_a_missing_source() -> None:
    assert _workshop_output_totals([{}], legacy_shift_output=8.0) == (8.0, 8.0, None)


def test_cold_roll_without_stage_marks_has_process_output_but_unknown_output() -> None:
    payload = {
        'output': 0.0,
        'process_output': 377.54,
        'pass_count_total': 0,
        'process_stage_outputs': {'unmarked': 377.54},
        'source_basis': 'mes_workshop_process_records',
    }

    assert _workshop_output_totals([payload], legacy_shift_output=0.0) == (None, 377.54, None)


def test_mes_row_without_pass_field_is_not_counted_as_a_pass() -> None:
    assert _process_row_pass_count(SimpleNamespace(source_payload={})) == 0
    assert _process_row_pass_count(SimpleNamespace(source_payload={'pass_count': 11})) == 11
