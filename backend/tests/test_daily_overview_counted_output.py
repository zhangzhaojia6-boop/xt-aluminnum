from __future__ import annotations

from datetime import date

from app.services.report import daily_overview_builder as builder
from app.services.report.daily_overview_builder import _counted_output


def test_workshop_without_any_source_is_unknown_not_zero() -> None:
    assert _counted_output({'output': 0.0, 'source_basis': None, 'process_stage_outputs': {}}) is None


def test_workshop_with_a_source_keeps_a_real_zero() -> None:
    payload = {'output': 0.0, 'source_basis': 'mes_workshop_process_records', 'process_stage_outputs': {}}
    assert _counted_output(payload) == 0.0


def test_cold_roll_records_without_stage_marks_stay_uncounted() -> None:
    payload = {'output': 377.54, 'source_basis': 'mes_workshop_process_records', 'process_stage_outputs': {'unmarked': 377.54}}
    assert _counted_output(payload) is None


def test_workshop_absent_from_a_period_is_unknown_not_zero(monkeypatch) -> None:
    def scope(_db, start, end):
        if start == date(2026, 11, 1):
            return {1: {'output': 500.0, 'source_basis': 'mes', 'process_stage_outputs': {'unmarked': 500.0}}}
        return {}

    monkeypatch.setattr(builder, '_mixed_workshop_output_scope_by_workshop', scope)

    rows = builder._build_workshop_output(None, date(2026, 11, 8), {1: '1650冷轧'})

    assert rows[0]['daily_output'] is None
    assert rows[0]['monthly_output'] is None
    assert rows[0]['yesterday_output'] is None
    assert rows[0]['delta'] is None


def test_workshop_with_output_keeps_values_and_delta(monkeypatch) -> None:
    def scope(_db, start, end):
        output = 10.0 if start == date(2026, 11, 8) else 4.0
        return {1: {'output': output, 'source_basis': 'mes', 'process_stage_outputs': {}}}

    monkeypatch.setattr(builder, '_mixed_workshop_output_scope_by_workshop', scope)

    row = builder._build_workshop_output(None, date(2026, 11, 8), {1: '精整'})[0]

    assert (row['daily_output'], row['yesterday_output'], row['delta']) == (10.0, 4.0, 6.0)
