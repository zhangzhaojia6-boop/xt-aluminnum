from __future__ import annotations

from app.services.report.daily_overview_builder import _counted_output


def test_workshop_without_any_source_is_unknown_not_zero() -> None:
    assert _counted_output({'output': 0.0, 'source_basis': None, 'process_stage_outputs': {}}) is None


def test_workshop_with_a_source_keeps_a_real_zero() -> None:
    payload = {'output': 0.0, 'source_basis': 'mes_workshop_process_records', 'process_stage_outputs': {}}
    assert _counted_output(payload) == 0.0


def test_cold_roll_records_without_stage_marks_stay_uncounted() -> None:
    payload = {'output': 377.54, 'source_basis': 'mes_workshop_process_records', 'process_stage_outputs': {'unmarked': 377.54}}
    assert _counted_output(payload) is None
