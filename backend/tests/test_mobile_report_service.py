from datetime import date

from app.services.mobile_report_service import (
    _required_submit_fields,
    calculate_mobile_report_metrics,
    summarize_mobile_reporting,
)


def test_calculate_mobile_report_metrics_from_raw_values() -> None:
    metrics = calculate_mobile_report_metrics(
        {
            'output_weight': 120.0,
            'scrap_weight': 6.0,
            'electricity_daily': 360.0,
            'gas_daily': 54.0,
        },
        monthly_output=1320.0,
        monthly_electricity=4420.0,
        monthly_gas=730.0,
    )

    assert metrics['energy_per_ton'] == 3.0
    assert metrics['monthly_yield_rate'] == 95.0
    assert metrics['monthly_output'] == 1320.0
    assert metrics['monthly_electricity'] == 4420.0
    assert metrics['monthly_gas'] == 730.0


def test_required_submit_fields_only_include_core_fields() -> None:
    missing = _required_submit_fields(
        {
            'attendance_count': 10,
            'input_weight': 100.0,
            'output_weight': 90.0,
            'electricity_daily': None,
            'gas_daily': None,
        }
    )
    assert missing == []


def test_required_submit_fields_returns_readable_labels() -> None:
    missing = _required_submit_fields(
        {
            'attendance_count': None,
            'input_weight': '',
            'output_weight': None,
        }
    )
    assert missing == ['出勤人数', '投入重量', '产出重量']


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, schedule_rows, report_rows):
        self._schedule_rows = schedule_rows
        self._report_rows = report_rows
        self._count = 0

    def query(self, *args, **kwargs):
        self._count += 1
        if self._count == 1:
            return _FakeQuery(self._schedule_rows)
        return _FakeQuery(self._report_rows)


def test_summarize_mobile_reporting_warns_when_schedule_empty() -> None:
    db = _FakeDB(schedule_rows=[], report_rows=[])
    summary = summarize_mobile_reporting(db, target_date=date(2026, 4, 6))
    assert summary["expected_count"] == 0
    assert summary["reporting_rate"] == 0.0
    assert summary["config_warnings"]
