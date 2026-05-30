from datetime import date
from datetime import datetime

from app.agents.base import AgentAction, AgentDecision
from app.services import mobile_report_service
from app.services.mobile_report_service import (
    _build_agent_decision_snapshot,
    _required_submit_fields,
    calculate_mobile_report_metrics,
    summarize_mobile_reporting,
)


def _normalize_payload_for_test(payload: dict) -> dict:
    normalize = getattr(mobile_report_service, '_normalize_mobile_report_payload', None)
    assert callable(normalize), '_normalize_mobile_report_payload should be implemented'
    return normalize(payload)


def test_normalize_mobile_report_payload_flattens_unified_entry_data() -> None:
    payload = _normalize_payload_for_test(
        {
            'business_date': date(2026, 5, 1),
            'shift_id': 1,
            'data': {
                'attendance_count': 8,
                'input_weight': 120.5,
                'output_weight': 118.0,
                'scrap_weight': 2.5,
                'operator_notes': '本班正常',
            },
        }
    )

    assert payload['input_weight'] == 120.5
    assert payload['output_weight'] == 118.0
    assert payload['scrap_weight'] == 2.5
    assert payload['attendance_count'] == 8
    assert payload['note'] == '本班正常'


def test_normalize_mobile_report_payload_maps_energy_template_fields() -> None:
    payload = _normalize_payload_for_test(
        {
            'business_date': date(2026, 5, 1),
            'shift_id': 1,
            'data': {
                'energy_kwh': 1200.5,
                'gas_m3': 88.0,
                'energy_note': '电表已核对',
            },
        }
    )

    assert payload['electricity_daily'] == 1200.5
    assert payload['gas_daily'] == 88.0
    assert payload['note'] == '电表已核对'


def test_required_submit_fields_reads_normalized_payload() -> None:
    payload = _normalize_payload_for_test(
        {
            'business_date': date(2026, 5, 1),
            'shift_id': 1,
            'data': {
                'input_weight': 100,
                'output_weight': 96,
            },
        }
    )

    assert _required_submit_fields(payload) == []


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
    assert missing == ['投入重量', '产出重量']


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


def test_agent_decision_snapshot_prefers_latest_validator_decision() -> None:
    decision = AgentDecision(
        agent_name='validator',
        action=AgentAction.AUTO_REJECT,
        target_type='mobile_shift_report',
        target_id=7,
        reason='校验未通过：产出重量大于投入重量',
        details={'errors': ['产出重量大于投入重量']},
        timestamp=datetime(2026, 4, 21, 3, 0, 0),
    )
    report = type('Report', (), {'report_status': 'returned', 'returned_reason': '请修改后重提'})()

    snapshot = _build_agent_decision_snapshot(report=report, decisions=[decision])

    assert snapshot['agent_decision_status'] == 'returned'
    assert snapshot['agent_decision_action'] == 'auto_reject'
    assert snapshot['agent_decision_agent'] == 'validator'
    assert snapshot['agent_decision_reason'] == '校验未通过：产出重量大于投入重量'
    assert snapshot['agent_decision_errors'] == ['产出重量大于投入重量']
    assert snapshot['agent_decision_warnings'] == []
    assert snapshot['agent_decision_at'] == datetime(2026, 4, 21, 3, 0, 0)


def test_agent_decision_snapshot_derives_auto_confirmed_from_report_status() -> None:
    report = type('Report', (), {'report_status': 'approved', 'returned_reason': None})()

    snapshot = _build_agent_decision_snapshot(report=report, decisions=None)

    assert snapshot['agent_decision_status'] == 'auto_confirmed'
    assert snapshot['agent_decision_action'] == 'auto_confirm'
    assert snapshot['agent_decision_agent'] == 'validator'


def test_machine_production_records_in_allowed_data_keys() -> None:
    """G13: payload normalization must accept per-machine production rows."""
    from app.services.mobile_report.lifecycle import (
        MOBILE_REPORT_ALLOWED_DATA_KEYS,
        _sum_machine_production,
    )

    assert 'machine_production_records' in MOBILE_REPORT_ALLOWED_DATA_KEYS
    rows = [
        {'equipment_id': 1, 'input_weight': 10.0, 'output_weight': 9.5, 'scrap_weight': 0.3},
        {'equipment_id': 2, 'input_weight': 8.0, 'output_weight': 7.6, 'scrap_weight': 0.2},
    ]
    assert _sum_machine_production(rows) == (18.0, 17.1, 0.5)


def test_sum_machine_production_with_partial_values() -> None:
    """G13: missing values stay missing — don't fabricate zeros."""
    from app.services.mobile_report.lifecycle import _sum_machine_production

    rows = [
        {'equipment_id': 1, 'input_weight': 10.0, 'output_weight': None, 'scrap_weight': 0.3},
        {'equipment_id': 2, 'input_weight': None, 'output_weight': 7.6, 'scrap_weight': None},
    ]
    in_, out, scrap = _sum_machine_production(rows)
    assert in_ == 10.0
    assert out == 7.6
    assert scrap == 0.3


def test_sum_machine_production_empty_returns_none() -> None:
    from app.services.mobile_report.lifecycle import _sum_machine_production

    assert _sum_machine_production([]) == (None, None, None)
    assert _sum_machine_production([{'equipment_id': 1}]) == (None, None, None)
