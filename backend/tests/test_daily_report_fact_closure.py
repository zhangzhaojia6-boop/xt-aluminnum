from __future__ import annotations

from typing import Any

import pytest

from app.services.report.daily_report_fact_closure import (
    CRITICAL_DAILY_FACT_FIELDS,
    build_daily_report_fact_closure,
)


def _confirmed_bundle() -> dict[str, Any]:
    sources = {
        "total_output_daily": "mes_packaging_output",
        "finished_inbound_daily": "mes_stock_header_records",
        "wip_total": "mes_daily_wip_snapshot",
        "total_electricity_kwh": "root_owner_correction",
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
                "unit": {
                    "total_output_daily": "吨",
                    "finished_inbound_daily": "吨",
                    "wip_total": "吨",
                    "total_electricity_kwh": "kWh",
                    "daily_yield_rate": "%",
                }[field],
                "source": source,
                "source_type": source,
                "trace_id": f"trace-{field}",
                "source_detail": {
                    "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
                },
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


def test_weak_source_type_with_mes_in_free_text_still_needs_evidence() -> None:
    bundle = _confirmed_bundle()
    bundle["facts"]["total_output_daily"]["source"] = "manual_workbook"
    bundle["facts"]["total_output_daily"]["source_type"] = "manual_workbook"
    bundle["facts"]["total_output_daily"]["source_detail"] = {
        "note": "人工表备注里写了 MES 包装量，但这不是标准来源类型"
    }
    bundle["facts"]["total_output_daily"]["source_ref"] = {
        "recognized_text": "MES packaging output"
    }
    bundle["sources"]["total_output_daily"] = {
        "source_type": "manual_workbook",
        "source_detail": {"note": "MES packaging output"},
        "source_ref": {"recognized_text": "MES"},
    }

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "total_output_daily") == "needs_evidence"


def test_pseudo_mes_or_wms_source_strings_need_evidence() -> None:
    for source in (
        "MES screenshot from chat",
        "WMS screenshot in chat",
        "mes_random_note",
        "wms_unverified_text",
    ):
        bundle = _confirmed_bundle()
        _set_source(bundle, "total_output_daily", source)

        closure = build_daily_report_fact_closure(bundle)

        assert closure["status"] == "blocked"
        assert _field_status(closure, "total_output_daily") == "needs_evidence"


@pytest.mark.parametrize(
    ("field_name", "source_type"),
    [
        ("total_output_daily", "mes_verified"),
        ("finished_inbound_daily", "finished_inbound_output"),
        ("finished_inbound_daily", "wms_direct"),
        ("wip_total", "mes_wip_distribution"),
        ("total_electricity_kwh", "data_hub_manual"),
        ("total_electricity_kwh", "iot_energy"),
        ("total_electricity_kwh", "owner_daily"),
        ("total_electricity_kwh", "owner_or_energy_summary"),
        ("daily_yield_rate", "computed_same_basis"),
        ("daily_yield_rate", "owner_daily"),
        ("daily_yield_rate", "quality_yield_daily"),
    ],
)
def test_unanchored_source_type_needs_evidence(
    field_name: str,
    source_type: str,
) -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, field_name, source_type)

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, field_name) == "needs_evidence"


def test_mes_stock_header_records_only_confirms_finished_inbound() -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, "total_output_daily", "mes_stock_header_records")
    _set_source(bundle, "finished_inbound_daily", "mes_stock_header_records")

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "total_output_daily") == "needs_evidence"
    assert _field_status(closure, "finished_inbound_daily") == "confirmed"


@pytest.mark.parametrize(
    ("field_name", "source_type"),
    [
        ("finished_inbound_daily", "mes_stock_records"),
        ("wip_total", "mes_coil_snapshot_business_date"),
        ("wip_total", "mes_daily_wip_snapshot"),
    ],
)
def test_verified_projection_sources_confirm_their_matching_critical_field(
    field_name: str,
    source_type: str,
) -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, field_name, source_type)

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "pass"
    assert _field_status(closure, field_name) == "confirmed"


def test_daily_yield_rate_plain_computed_source_needs_evidence() -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, "daily_yield_rate", "computed")

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "daily_yield_rate") == "needs_evidence"


def test_derived_and_reference_sources_block_even_with_allowed_source_present() -> None:
    for source in ("official_daily_report", "datahub_final_daily_report", "daily_fact_bundle"):
        bundle = _confirmed_bundle()
        bundle["sources"]["total_output_daily"] = {
            "source_type": "mes_packaging_output",
            "source": source,
            "trace_id": "trace-total-output",
        }

        closure = build_daily_report_fact_closure(bundle)

        assert closure["status"] == "blocked"
        assert _field_status(closure, "total_output_daily") == "needs_evidence"


def test_derived_source_hidden_in_source_detail_still_blocks() -> None:
    bundle = _confirmed_bundle()
    bundle["facts"]["total_output_daily"]["source_detail"] = {
        "source_type": "official_daily_report"
    }

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "total_output_daily") == "needs_evidence"


def test_field_source_detail_trace_is_accepted() -> None:
    bundle = _confirmed_bundle()
    bundle["facts"]["wip_total"].pop("trace_id")
    bundle["facts"]["wip_total"]["source_detail"]["trace_id"] = "trace-wip-detail"

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "pass"
    wip = next(item for item in closure["critical_fields"] if item["field"] == "wip_total")
    assert wip["trace_id"] == "trace-wip-detail"


def test_bundle_level_trace_does_not_replace_missing_field_trace() -> None:
    bundle = _confirmed_bundle()
    bundle["facts"]["wip_total"].pop("trace_id")
    bundle["sources"]["wip_total"].pop("trace_id", None)

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "wip_total") == "needs_evidence"
    wip = next(item for item in closure["critical_fields"] if item["field"] == "wip_total")
    assert wip["trace_id"] is None


def test_historical_report_for_daily_yield_rate_needs_evidence() -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, "daily_yield_rate", "historical_report")

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "daily_yield_rate") == "needs_evidence"


def test_yield_projection_for_daily_yield_rate_needs_evidence() -> None:
    bundle = _confirmed_bundle()
    _set_source(bundle, "daily_yield_rate", "yield_projection")

    closure = build_daily_report_fact_closure(bundle)

    assert closure["status"] == "blocked"
    assert _field_status(closure, "daily_yield_rate") == "needs_evidence"


def test_every_critical_field_has_required_keys() -> None:
    closure = build_daily_report_fact_closure(_confirmed_bundle())

    for item in closure["critical_fields"]:
        assert {
            "field",
            "value",
            "unit",
            "status",
            "source",
            "business_window",
            "trace_id",
            "action",
        } <= set(item)
        assert item["field"] in CRITICAL_DAILY_FACT_FIELDS
        assert item["action"]


@pytest.mark.parametrize(
    ("field_name", "missing_key"),
    [
        ("total_output_daily", "unit"),
        ("finished_inbound_daily", "business_window"),
        ("wip_total", "trace_id"),
    ],
)
def test_missing_fact_contract_metadata_cannot_be_confirmed(
    field_name: str,
    missing_key: str,
) -> None:
    bundle = _confirmed_bundle()
    if missing_key == "business_window":
        bundle["facts"][field_name]["source_detail"].pop(missing_key)
    else:
        bundle["facts"][field_name].pop(missing_key)

    closure = build_daily_report_fact_closure(bundle)
    fact = next(item for item in closure["critical_fields"] if item["field"] == field_name)

    assert fact[missing_key] is None
    assert fact["status"] == "needs_evidence"
