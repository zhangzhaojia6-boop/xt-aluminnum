from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import app.models  # noqa: F401
from app.database import Base
from app.services.hermes_fact_source_map_service import (
    find_fact_source,
    load_fact_source_map,
    source_summary_for_metric,
)
from scripts.hermes_fact_source_map_export import render_fact_source_map_markdown

EXPECTED_METRIC_KEYS = {
    "total_output_daily",
    "workshop_output_daily",
    "finished_inbound_daily",
    "daily_input_weight",
    "total_electricity_kwh",
    "total_gas_m3",
    "electricity_per_ton",
    "daily_yield_rate",
    "cost_per_ton",
    "wip_total",
    "remaining_contract_weight",
    "monthly_total_output",
    "annual_total_output",
    "anomaly_explanation_daily",
    "dingtalk_specialist_evidence",
}

DINGTALK_EVIDENCE_CONDITION_KEYS = {
    "authorized_group",
    "content_type",
    "time_range",
}

BAD_API_ROUTES = {
    "/api/v1/dashboard/live",
    "/api/v1/executive/*",
    "/api/v1/dashboard/alerts",
}


def test_fact_source_map_loads_core_daily_report_metrics() -> None:
    source_map = load_fact_source_map()

    keys = {item["metric_key"] for item in source_map}
    assert keys == EXPECTED_METRIC_KEYS


def test_fact_source_map_requires_dingtalk_evidence_conditions_for_group_content_priority_sources() -> None:
    source_map = load_fact_source_map()

    dingtalk_group_items = [item for item in source_map if "dingtalk_group_content" in item["priority_sources"]]

    assert {item["metric_key"] for item in dingtalk_group_items} == {
        "total_output_daily",
        "finished_inbound_daily",
        "total_electricity_kwh",
        "total_gas_m3",
        "anomaly_explanation_daily",
    }
    for item in dingtalk_group_items:
        conditions = item["dingtalk_evidence_conditions"]
        assert set(conditions) == DINGTALK_EVIDENCE_CONDITION_KEYS
        assert conditions["authorized_group"] == "required"
        assert conditions["content_type"] == ["text", "file", "image"]
        assert conditions["time_range"] == "business_day_window"


def test_fact_source_map_prioritizes_dingtalk_group_content_first() -> None:
    load_fact_source_map()

    for metric_key in {
        "total_output_daily",
        "finished_inbound_daily",
        "total_electricity_kwh",
        "total_gas_m3",
        "anomaly_explanation_daily",
    }:
        item = find_fact_source(metric_key)
        assert item["priority_sources"][0] == "dingtalk_group_content"


def test_production_domain_metrics_put_mes_before_data_hub_projection() -> None:
    item = find_fact_source("wip_total")

    assert item["priority_sources"].index("MES/WMS readonly") < item["priority_sources"].index("data_hub_projection")


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


def test_fact_source_map_uses_only_concrete_api_routes() -> None:
    source_map = load_fact_source_map()
    api_routes = {route for item in source_map for route in item["api_routes"]}

    assert "*" not in "".join(api_routes)
    assert BAD_API_ROUTES.isdisjoint(api_routes)


def test_fact_source_map_rejects_duplicate_metric_keys(tmp_path: Path) -> None:
    source_map = load_fact_source_map()
    duplicate_item = dict(source_map[0])
    duplicate_path = tmp_path / "duplicate_fact_source_map.json"
    duplicate_path.write_text(
        json.dumps([duplicate_item, dict(duplicate_item)], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    load_fact_source_map.cache_clear()
    try:
        with pytest.raises(ValueError, match=r"fact_source_map_duplicate_metric_key:"):
            load_fact_source_map(duplicate_path)
    finally:
        load_fact_source_map.cache_clear()


def test_fact_source_map_source_tables_exist_in_db_metadata() -> None:
    source_map = load_fact_source_map()

    existing_tables = Base.metadata.tables.keys()
    for item in source_map:
        for source_table in item["source_tables"]:
            assert (
                source_table in existing_tables
            ), f"{item['metric_key']} maps to missing table: {source_table}"


def test_fact_source_map_frontend_pages_are_routes_and_no_placeholders() -> None:
    source_map = load_fact_source_map()

    flattened_frontend_pages: list[str] = [page for item in source_map for page in item["frontend_pages"]]
    assert all(page.startswith("/") for page in flattened_frontend_pages)
    assert "Hermes only" not in flattened_frontend_pages
    assert "DingTalk" not in flattened_frontend_pages


def test_fact_source_map_export_contains_core_columns() -> None:
    markdown = render_fact_source_map_markdown()

    assert "| 指标 | 领域 | 来源优先级 | 涉及服务 | 保护级别 | 状态 |" in markdown
    assert "| 涉及表 | Hermes 工具 |" in markdown
    assert "车间总产量日合计" in markdown
    assert "protect" in markdown


def test_fact_source_map_export_matches_committed_markdown() -> None:
    docs_path = Path(__file__).resolve().parents[2] / "docs" / "hermes" / "fact-source-map.md"
    rendered = render_fact_source_map_markdown().replace("\\r\\n", "\n").strip()
    checked = docs_path.read_text(encoding="utf-8").replace("\\r\\n", "\n").strip()

    assert rendered == checked
