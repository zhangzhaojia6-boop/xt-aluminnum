from __future__ import annotations

from app.services.report.daily_report_gap_analysis import (
    build_daily_report_gap_plan,
    classify_daily_report_field_gap,
)


def test_classifies_energy_gap_as_dingtalk_or_scan_fill() -> None:
    item = classify_daily_report_field_gap("total_electricity_kwh")

    assert item["group"] == "energy"
    assert item["source_lane"] == "dingtalk_or_scan_fill_energy"
    assert item["entry_route"] == "/entry/fill"
    assert item["fill_strategy"] == "owner_daily"
    assert item["owner_role"] == "energy_chief"
    assert item["entry_fields"] == ["total_electricity_kwh"]


def test_classifies_finished_inbound_as_two_existing_storage_fields() -> None:
    item = classify_daily_report_field_gap("finished_inbound_daily")

    assert item["entry_route"] == "/entry/fill"
    assert item["fill_strategy"] == "owner_daily"
    assert item["owner_role"] == "storage_owner"
    assert item["entry_fields"] == ["park_inbound_daily", "new_plant_inbound_daily"]


def test_classifies_computed_cost_as_dependency_fill_not_direct_entry() -> None:
    item = classify_daily_report_field_gap("total_cost_10k")

    assert item["entry_route"] == "/manage/alerts"
    assert item["fill_strategy"] == "dependency_fill"
    assert item["owner_role"] == "factory_dispatch"
    assert item["entry_fields"] == []


def test_classifies_wip_total_gap_as_mes_wip_or_dingtalk() -> None:
    item = classify_daily_report_field_gap("wip_total")

    assert item["group"] == "wip"
    assert item["source_lane"] == "mes_wip_snapshot_or_dingtalk"
    assert item["entry_route"] == "/manage/alerts"
    assert item["fill_strategy"] == "source_recheck"
    assert "在制" in item["next_step"]


def test_gap_plan_combines_missing_fields_and_alignment_differences() -> None:
    plan = build_daily_report_gap_plan(
        missing_fields=["total_electricity_kwh"],
        alignment={
            "status": "review_needed",
            "differences": [
                {"field": "wip_total", "actual": 1.321, "expected": 1136},
                {"field": "total_electricity_kwh", "actual": None, "expected": 133201},
            ],
        },
        sources={"wip_total": {"source_type": "mes_wip_distribution"}},
    )

    assert plan["status"] == "needs_action"
    assert plan["item_count"] == 2
    assert plan["summary"]["by_group"] == {"energy": 1, "wip": 1}
    assert plan["items"][0]["problem_type"] == "missing_field"
    assert plan["items"][1]["field"] == "wip_total"
    assert plan["items"][1]["current_source"] == "mes_wip_distribution"


def test_gap_plan_is_ready_when_no_missing_or_difference() -> None:
    plan = build_daily_report_gap_plan(missing_fields=[], alignment={"differences": []})

    assert plan == {
        "status": "ready",
        "item_count": 0,
        "summary": {"by_group": {}, "by_source_lane": {}},
        "items": [],
    }
