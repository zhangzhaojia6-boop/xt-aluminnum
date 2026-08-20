from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.core.business_time import (
    BILLET_PRODUCTION_BUSINESS_DAY_START,
    OWNER_DAILY_BUSINESS_DAY_START,
    OWNER_DAILY_LATE_CUTOFF,
    PRODUCTION_BUSINESS_DAY_START,
)
from app.domain import daily_report_field_contract as contract_module
from app.domain import metric_contracts
from app.services.report import template_daily_field_contract


def test_normative_contract_keeps_the_approved_127_field_denominator() -> None:
    template_fields = template_daily_field_contract.all_contract_fields()
    normative_fields = contract_module.normative_daily_report_fields()

    assert len(template_fields) == 130
    assert contract_module.DAILY_REPORT_NORMATIVE_FIELD_COUNT == 127
    assert len(normative_fields) == contract_module.DAILY_REPORT_NORMATIVE_FIELD_COUNT
    assert len(normative_fields) == len(set(normative_fields))
    assert set(normative_fields).issubset(template_fields)
    assert set(template_fields) - set(normative_fields) == set(
        contract_module.TEMPLATE_ONLY_FIELD_REASONS
    )
    assert contract_module.TEMPLATE_ONLY_FIELD_REASONS == {
        "recovery_daily": "legacy_template_unit_not_frozen",
        "recovery_month": "legacy_template_unit_not_frozen",
        "remaining_contract_delta": "derived_display_field_outside_normative_denominator",
    }


def test_every_normative_field_has_an_immutable_complete_contract() -> None:
    contracts = contract_module.DAILY_REPORT_FIELD_CONTRACTS

    assert set(contracts) == set(contract_module.normative_daily_report_fields())
    for field_name, contract in contracts.items():
        assert contract.field_name == field_name
        assert contract.group == template_daily_field_contract.field_group(field_name)
        assert contract.unit
        assert contract.business_time_scope in {
            contract_module.BUSINESS_TIME_STANDARD,
            contract_module.BUSINESS_TIME_BILLET,
        }
        assert contract.reference_role == contract_module.REFERENCE_ROLE_COMPARE_ONLY
        assert contract.source_lanes
        assert contract.source_lanes[-1] == contract_module.SOURCE_LANE_RAG_EXPLANATION_ONLY
        assert 0 <= contract.tolerance <= 20
        if contract.unit in {"%", "kWh/吨", "m³/吨"}:
            assert contract.tolerance <= 0.2

    with pytest.raises(FrozenInstanceError):
        contracts["total_output_daily"].tolerance = 99


def test_business_time_contract_reuses_runtime_constants() -> None:
    assert contract_module.BUSINESS_TIME_STARTS == {
        contract_module.BUSINESS_TIME_STANDARD: PRODUCTION_BUSINESS_DAY_START.strftime("%H:%M"),
        contract_module.BUSINESS_TIME_BILLET: BILLET_PRODUCTION_BUSINESS_DAY_START.strftime("%H:%M"),
    }
    assert contract_module.OWNER_DAILY_SUBMISSION_TIME == OWNER_DAILY_BUSINESS_DAY_START.strftime("%H:%M")
    assert contract_module.OWNER_DAILY_LATE_TIME == OWNER_DAILY_LATE_CUTOFF.strftime("%H:%M")

    assert contract_module.daily_report_field_contract_for("total_output_daily").business_time_scope == (
        contract_module.BUSINESS_TIME_STANDARD
    )
    for field_name in (
        "hot_roll_daily",
        "hot_roll_month",
        "hot_roll_furnace_gas_m3",
        "hot_roll_yield_rate",
        "cast_2_gas_m3",
        "cast_3_gas_m3",
    ):
        assert contract_module.daily_report_field_contract_for(field_name).business_time_scope == (
            contract_module.BUSINESS_TIME_BILLET
        )


def test_contract_units_and_tolerances_cover_representative_field_kinds() -> None:
    expected = {
        "report_date": ("日期", 0.0),
        "cold_1650_pass_daily": ("道", 0.0),
        "roller_grind_daily": ("根", 0.0),
        "total_output_daily": ("吨", 20.0),
        "finished_inbound_daily": ("吨", 20.0),
        "wip_total": ("吨", 20.0),
        "total_electricity_kwh": ("kWh", 20.0),
        "cast_roll_gas_m3": ("m³", 0.0),
        "cast_roll_electricity_per_ton_daily": ("kWh/吨", 0.2),
        "cast_roll_gas_per_ton_daily": ("m³/吨", 0.2),
        "daily_yield_rate": ("%", 0.2),
        "electricity_cost_10k": ("万元", 0.0),
        "cost_per_ton": ("元/吨", 0.0),
    }

    for field_name, (unit, tolerance) in expected.items():
        contract = contract_module.daily_report_field_contract_for(field_name)
        assert (contract.unit, contract.tolerance) == (unit, tolerance)

    assert contract_module.daily_report_field_contract_for("cast_roll_active_lines").unit == "条"
    assert contract_module.daily_report_field_contract_for("finished_inbound_month").unit == "吨"


def test_finished_inbound_daily_contract_exposes_fill_schema() -> None:
    contract = contract_module.daily_report_field_contract_for("finished_inbound_daily")

    assert contract.owner_role == "storage_owner"
    assert contract.entry_route == "/entry/fill"
    assert contract.entry_fields == ("park_inbound_daily", "new_plant_inbound_daily")
    assert contract.deadline


@pytest.mark.parametrize(
    ("field_name", "expected"),
    (
        (
            "total_output_daily",
            {
                "source_lane": "dingtalk_or_final_daily_report",
                "entry_route": "/manage/alerts",
                "fill_strategy": "dependency_fill",
                "owner_role": "factory_dispatch",
                "entry_fields": (),
                "deadline": "10:00",
            },
        ),
        (
            "finished_inbound_daily",
            {
                "source_lane": "dingtalk_or_wms_final",
                "entry_route": "/entry/fill",
                "fill_strategy": "owner_daily",
                "owner_role": "storage_owner",
                "entry_fields": ("park_inbound_daily", "new_plant_inbound_daily"),
                "deadline": contract_module.OWNER_DAILY_LATE_TIME,
            },
        ),
        (
            "wip_total",
            {
                "source_lane": "mes_wip_snapshot_or_dingtalk",
                "entry_route": "/entry/fill",
                "fill_strategy": "owner_daily",
                "owner_role": "planning_owner",
                "entry_fields": ("wip_total",),
                "deadline": contract_module.OWNER_DAILY_LATE_TIME,
            },
        ),
        (
            "total_electricity_kwh",
            {
                "source_lane": "dingtalk_or_scan_fill_energy",
                "entry_route": "/entry/fill",
                "fill_strategy": "owner_daily",
                "owner_role": "energy_chief",
                "entry_fields": ("total_electricity_kwh",),
                "deadline": contract_module.OWNER_DAILY_LATE_TIME,
            },
        ),
        (
            "daily_yield_rate",
            {
                "source_lane": "computed_or_quality_confirmation",
                "entry_route": "/entry/fill",
                "fill_strategy": "owner_confirmation",
                "owner_role": "quality_owner",
                "entry_fields": ("plant_wide_yield_rate",),
                "deadline": contract_module.OWNER_DAILY_LATE_TIME,
            },
        ),
    ),
)
def test_high_value_gap_action_projection_comes_from_domain_contract(
    field_name: str,
    expected: dict[str, object],
) -> None:
    action = contract_module.daily_report_gap_action_for(field_name)

    assert isinstance(action, contract_module.DailyReportGapAction)
    assert action.field == field_name
    assert action.group == contract_module.daily_report_field_contract_for(field_name).group
    assert action.source_lane == expected["source_lane"]
    assert action.entry_route == expected["entry_route"]
    assert action.fill_strategy == expected["fill_strategy"]
    assert action.owner_role == expected["owner_role"]
    assert action.entry_fields == expected["entry_fields"]
    assert action.deadline == expected["deadline"]
    assert action.next_step

    contract = contract_module.daily_report_field_contract_for(field_name)
    assert contract.gap_source_lane == action.source_lane
    assert action.source_lane != contract.source_lanes[0]


def test_existing_metric_tolerance_lookup_reuses_normative_contract() -> None:
    for field_name, contract in contract_module.DAILY_REPORT_FIELD_CONTRACTS.items():
        assert metric_contracts.daily_report_tolerance_for(field_name) == contract.tolerance


@pytest.mark.parametrize(
    ("field_name", "expected"),
    (
        (
            "remaining_contract_delta",
            {
                "group": "contract_input",
                "entry_route": "/entry/fill",
                "fill_strategy": "owner_daily",
                "owner_role": "planning_owner",
                "entry_fields": ("remaining_contract_delta_weight",),
            },
        ),
        (
            "recovery_daily",
            {
                "group": "manual_supplement",
                "entry_route": "/entry/fill",
                "fill_strategy": "owner_daily",
                "owner_role": "recovery_owner",
                "entry_fields": ("recovery_weight",),
            },
        ),
    ),
)
def test_template_only_fields_still_expose_gap_actions(
    field_name: str,
    expected: dict[str, object],
) -> None:
    action = contract_module.daily_report_gap_action_for(field_name)

    assert action.field == field_name
    assert action.group == expected["group"]
    assert action.entry_route == expected["entry_route"]
    assert action.fill_strategy == expected["fill_strategy"]
    assert action.owner_role == expected["owner_role"]
    assert action.entry_fields == expected["entry_fields"]
    assert action.deadline == contract_module.OWNER_DAILY_LATE_TIME
    assert action.next_step
    assert field_name not in contract_module.DAILY_REPORT_FIELD_CONTRACTS


def test_source_lane_order_is_single_and_answer_key_is_not_a_fact_source() -> None:
    assert contract_module.FACT_SOURCE_LANE_ORDER == (
        contract_module.SOURCE_LANE_DINGTALK,
        contract_module.SOURCE_LANE_AUTHORIZED_CORRECTION,
        contract_module.SOURCE_LANE_MES_WMS_READONLY,
        contract_module.SOURCE_LANE_SCAN_SUPPLEMENT,
        contract_module.SOURCE_LANE_DATA_HUB_PROJECTION,
        contract_module.SOURCE_LANE_HISTORICAL_RECORD,
        contract_module.SOURCE_LANE_RAG_EXPLANATION_ONLY,
    )
    assert contract_module.SOURCE_LANE_OUTPUT_SKILL_REFERENCE not in (
        contract_module.FACT_SOURCE_LANE_ORDER
    )
    assert contract_module.source_lane_for("output_skill") == (
        contract_module.SOURCE_LANE_OUTPUT_SKILL_REFERENCE
    )
    assert contract_module.source_lane_priority("output_skill") < 0

    priorities = [
        contract_module.source_lane_priority(lane)
        for lane in contract_module.FACT_SOURCE_LANE_ORDER
    ]
    assert priorities == [100, 90, 80, 70, 60, 40, 30]
    assert priorities == sorted(priorities, reverse=True)


@pytest.mark.parametrize(
    ("source_type", "expected_lane"),
    (
        ("dingtalk_supplement", contract_module.SOURCE_LANE_DINGTALK),
        ("root_owner_correction", contract_module.SOURCE_LANE_AUTHORIZED_CORRECTION),
        ("root_owner", contract_module.SOURCE_LANE_AUTHORIZED_CORRECTION),
        ("mes_packaging_output", contract_module.SOURCE_LANE_MES_WMS_READONLY),
        ("wms_direct", contract_module.SOURCE_LANE_MES_WMS_READONLY),
        ("owner_daily", contract_module.SOURCE_LANE_SCAN_SUPPLEMENT),
        ("verified_owner_daily", contract_module.SOURCE_LANE_SCAN_SUPPLEMENT),
        ("contract_projection", contract_module.SOURCE_LANE_DATA_HUB_PROJECTION),
        ("history_report", contract_module.SOURCE_LANE_HISTORICAL_RECORD),
        ("previous_final_report", contract_module.SOURCE_LANE_HISTORICAL_RECORD),
        ("rag", contract_module.SOURCE_LANE_RAG_EXPLANATION_ONLY),
        ("official_daily_report", contract_module.SOURCE_LANE_OUTPUT_SKILL_REFERENCE),
    ),
)
def test_runtime_source_types_resolve_to_the_canonical_lane(
    source_type: str,
    expected_lane: str,
) -> None:
    assert contract_module.source_lane_for(source_type) == expected_lane


def test_unknown_normative_field_is_rejected() -> None:
    with pytest.raises(KeyError):
        contract_module.daily_report_field_contract_for("not_a_daily_report_field")
