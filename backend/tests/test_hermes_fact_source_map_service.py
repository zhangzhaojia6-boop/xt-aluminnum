from __future__ import annotations

from app.services.hermes_fact_source_map_service import (
    find_fact_source,
    load_fact_source_map,
    source_summary_for_metric,
)


def test_fact_source_map_loads_core_daily_report_metrics() -> None:
    source_map = load_fact_source_map()

    keys = {item["metric_key"] for item in source_map}
    assert "total_output_daily" in keys
    assert "finished_inbound_daily" in keys
    assert "cost_per_ton" in keys
    assert len(source_map) >= 12


def test_fact_source_map_protects_raw_evidence_and_audit_paths() -> None:
    item = find_fact_source("total_output_daily")

    assert item["delete_protection"] == "protect"
    assert "DailyFactBundle" in item["source_services"]
    assert "Hermes" in source_summary_for_metric("total_output_daily")


def test_fact_source_map_contains_no_sensitive_keys() -> None:
    source_map = load_fact_source_map()
    text = str(source_map).lower()

    assert "password" not in text
    assert "token" not in text
    assert "secret" not in text
    assert "连接串" not in text
