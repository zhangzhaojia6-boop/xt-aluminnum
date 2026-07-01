from __future__ import annotations

from typing import Any

from app.services.report.daily_report_fact_closure import (
    CRITICAL_DAILY_FACT_FIELDS,
    build_daily_report_fact_closure,
)


def _confirmed_bundle() -> dict[str, Any]:
    sources = {
        "total_output_daily": "dingtalk_supplement",
        "finished_inbound_daily": "wms_finished_inbound_output",
        "wip_total": "mes_wms_readonly",
        "total_electricity_kwh": "owner_energy_summary",
        "daily_yield_rate": "root_owner_correction",
    }
    values = {
        "total_output_daily": 384.0,
        "finished_inbound_daily": 126.4,
        "wip_total": 1136.0,
        "total_electricity_kwh": 133201.0,
        "daily_yield_rate": 0.88,
    }
    return {
        "trace_id": "daily-fact-test",
        "facts": {
            field: {
                "value": values[field],
                "source": source,
                "source_type": source,
                "trace_id": f"trace-{field}",
            }
            for field, source in sources.items()
        },
        "sources": {
            field: {"source_type": source}
            for field, source in sources.items()
        },
        "missing_fields": [],
        "output_skill_alignment": {"differences": []},
    }


def _field_status(closure: dict[str, Any], field_name: str) -> str:
    return next(
        item["status"]
        for item in closure["critical_fields"]
        if item["field"] == field_name
    )


def _set_source(bundle: dict[str, Any], field_name: str, source: str) -> None:
    bundle["facts"][field_name]["source"] = source
    bundle["facts"][field_name]["source_type"] = source
    bundle["sources"][field_name] = {"source_type": source}


def test_all_critical_fields_confirmed_returns_pass() -> None:
    closure = build_daily_report_fact_closure(_confirmed_bundle())

    assert closure["status"] == "pass"
    assert closure["counts"]["confirmed"] == len(CRITICAL_DAILY_FACT_FIELDS)


def test_missing_total_electricity_blocks_closure() -> None:
    bundle = _confirmed_bundle()
    bundle["facts"].pop("total_electricity_kwh")
    bundle["missing_fields"] = ["total_electricity_kwh"]

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "total_electricity_kwh") == "missing"


def test_output_skill_mismatch_blocks_total_output() -> None:
    bundle = _confirmed_bundle()
    bundle["output_skill_alignment"] = {
        "differences": [
            {"field": "total_output_daily", "actual": 384.0, "expected": 390.0}
        ]
    }

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "total_output_daily") == "mismatch"


def test_projection_only_source_needs_evidence() -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, "wip_total", "data_hub_projection")

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "wip_total") == "needs_evidence"


def test_daily_yield_rate_computed_source_is_confirmed() -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, "daily_yield_rate", "computed")

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "pass"
    assert _field_status(closure, "daily_yield_rate") == "confirmed"


def test_daily_fact_bundle_source_passes_for_all_critical_fields() -> None:
    bundle = _confirmed_bundle()
    for field in CRITICAL_DAILY_FACT_FIELDS:
        _set_source(bundle, field, "DailyFactBundle")

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "pass"
    assert closure["counts"]["confirmed"] == len(CRITICAL_DAILY_FACT_FIELDS)


def test_historical_report_for_daily_yield_rate_needs_evidence() -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, "daily_yield_rate", "historical_report")

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "daily_yield_rate") == "needs_evidence"


def test_total_electricity_allows_data_hub_manual_source() -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, "total_electricity_kwh", "data_hub_manual")

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "pass"
    assert _field_status(closure, "total_electricity_kwh") == "confirmed"


def test_every_critical_field_has_required_keys() -> None:
    closure = build_daily_report_fact_closure(_confirmed_bundle())

    for item in closure["critical_fields"]:
        assert {"field", "status", "source", "trace_id", "value", "action"} <= set(item)
        assert item["field"] in CRITICAL_DAILY_FACT_FIELDS
        assert item["action"]
