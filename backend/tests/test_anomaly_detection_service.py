from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.anomaly_detection_service import (
    detect_attendance_anomalies,
    detect_cross_shift_jump_anomalies,
    detect_energy_spike_anomalies,
    detect_output_gt_input_anomalies,
    detect_shift_missing_report_anomalies,
    summarize_anomalies,
)


def test_detect_output_gt_input_anomalies() -> None:
    rows = [
        SimpleNamespace(
            id=1,
            workshop_id=1,
            shift_config_id=1,
            team_id=None,
            input_weight=100.0,
            output_weight=120.0,
        )
    ]
    result = detect_output_gt_input_anomalies(rows)
    assert len(result) == 1
    assert result[0]["anomaly_type"] == "output_gt_input"


def test_detect_shift_missing_report_anomalies() -> None:
    expected = [
        SimpleNamespace(business_date=date(2026, 4, 6), shift_config_id=1, workshop_id=1, team_id=None),
        SimpleNamespace(business_date=date(2026, 4, 6), shift_config_id=2, workshop_id=1, team_id=None),
    ]
    reports = [
        SimpleNamespace(
            business_date=date(2026, 4, 6),
            shift_config_id=1,
            workshop_id=1,
            team_id=None,
            report_status="approved",
        )
    ]
    result = detect_shift_missing_report_anomalies(expected, reports)
    assert len(result) == 1
    assert result[0]["anomaly_type"] == "shift_missing_report"


def test_detect_shift_missing_report_anomalies_treats_auto_confirmed_as_ready() -> None:
    expected = [
        SimpleNamespace(business_date=date(2026, 4, 6), shift_config_id=1, workshop_id=1, team_id=None),
    ]
    reports = [
        SimpleNamespace(
            business_date=date(2026, 4, 6),
            shift_config_id=1,
            workshop_id=1,
            team_id=None,
            report_status="auto_confirmed",
        )
    ]

    result = detect_shift_missing_report_anomalies(expected, reports)

    assert result == []


def test_detect_energy_spike_anomalies() -> None:
    rows = [
        SimpleNamespace(
            id=2,
            workshop_id=1,
            shift_config_id=1,
            team_id=None,
            electricity_kwh=500.0,
        )
    ]
    history_avg_map = {(1, 1): 200.0}
    result = detect_energy_spike_anomalies(rows, history_avg_map)
    assert len(result) == 1
    assert result[0]["anomaly_type"] == "energy_spike"


def test_detect_attendance_anomalies() -> None:
    rows = [
        SimpleNamespace(
            id=3,
            workshop_id=1,
            shift_config_id=1,
            team_id=None,
            planned_headcount=10,
            actual_headcount=5,
        )
    ]
    result = detect_attendance_anomalies(rows)
    assert len(result) == 1
    assert result[0]["anomaly_type"] == "attendance_abnormal"


def test_detect_cross_shift_jump_anomalies() -> None:
    rows = [
        SimpleNamespace(id=10, workshop_id=1, shift_config_id=1, team_id=None, output_weight=100.0),
        SimpleNamespace(id=11, workshop_id=1, shift_config_id=2, team_id=None, output_weight=170.0),
    ]
    result = detect_cross_shift_jump_anomalies(rows, {1: 1, 2: 2})
    assert len(result) == 1
    assert result[0]["anomaly_type"] == "cross_shift_jump"


def test_summarize_anomalies() -> None:
    items = [
        {"anomaly_type": "shift_missing_report"},
        {"anomaly_type": "shift_missing_report"},
        {"anomaly_type": "attendance_abnormal"},
    ]
    summary = summarize_anomalies(items)
    assert summary["total"] == 3
    assert summary["by_type"]["shift_missing_report"] == 2
    assert "班次缺报" in summary["digest"]
