from __future__ import annotations

from collections.abc import Iterable


FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "opening": (
        "report_date",
        "total_output_daily",
        "outsourced_daily",
        "total_output_delta",
        "total_output_month",
        "outsourced_month",
    ),
    "workshop_output": (
        "cast_roll_active_lines",
        "cast_roll_daily",
        "cast_roll_month",
        "foundry_daily",
        "foundry_month",
        "hot_roll_daily",
        "hot_roll_month",
        "cold_1650_daily",
        "cold_1650_month",
        "cold_1650_pass_daily",
        "cold_1650_pass_month",
        "cold_1850_daily",
        "cold_1850_month",
        "cold_1850_pass_daily",
        "cold_1850_pass_month",
        "cold_2050_daily",
        "cold_2050_month",
        "cold_2050_pass_daily",
        "cold_2050_pass_month",
        "rolling_daily",
        "rolling_month",
        "rolling_pass_daily",
        "rolling_pass_month",
        "online_anneal_daily",
        "online_anneal_month",
        "straightening_daily",
        "straightening_month",
        "finishing_daily",
        "finishing_month",
        "shearing_daily",
        "shearing_month",
        "coating_daily",
        "coating_month",
    ),
    "manual_supplement": (
        "recovery_daily",
        "recovery_month",
        "roller_grind_daily",
        "roller_grind_month",
    ),
    "wip": (
        "wip_total",
        "wip_1650_2050_cold",
        "wip_1850_cold",
        "wip_milling",
        "wip_anneal_total",
        "wip_new_north",
        "wip_new_south",
        "wip_park_anneal",
        "wip_finishing_total",
        "wip_straightening",
        "wip_finishing",
        "wip_park_finishing",
        "wip_hot_plate_shearing",
        "wip_coating",
    ),
    "energy": (
        "total_electricity_kwh",
        "subitem_electricity_kwh",
        "cast_roll_gas_m3",
        "cast_2_gas_m3",
        "cast_3_gas_m3",
        "smelting_gas_m3",
        "recovery_gas_m3",
        "hot_roll_furnace_gas_m3",
        "east_furnace_gas_m3",
        "west_furnace_gas_m3",
        "hot_roll_boiler_gas_m3",
        "anneal_gas_m3",
        "straightening_boiler_gas_m3",
        "new_north_gas_m3",
        "new_south_gas_m3",
        "coating_gas_m3",
        "canteen_gas_m3",
        "total_gas_m3",
        "cast_roll_electricity_per_ton_daily",
        "cast_roll_electricity_per_ton_month",
        "cast_roll_gas_per_ton_daily",
        "cast_roll_gas_per_ton_month",
        "foundry_electricity_per_ton_daily",
        "foundry_electricity_per_ton_month",
        "foundry_gas_per_ton_daily",
        "foundry_gas_per_ton_month",
        "hot_roll_electricity_per_ton_daily",
        "hot_roll_electricity_per_ton_month",
        "hot_roll_gas_per_ton_daily",
        "hot_roll_gas_per_ton_month",
        "cold_1650_electricity_per_ton_daily",
        "cold_1650_electricity_per_ton_month",
        "cold_1850_electricity_per_ton_daily",
        "cold_1850_electricity_per_ton_month",
        "cold_2050_electricity_per_ton_daily",
        "cold_2050_electricity_per_ton_month",
        "online_anneal_electricity_per_ton_daily",
        "online_anneal_electricity_per_ton_month",
        "straightening_electricity_per_ton_daily",
        "straightening_electricity_per_ton_month",
        "finishing_electricity_per_ton_daily",
        "finishing_electricity_per_ton_month",
        "shearing_electricity_per_ton_daily",
        "shearing_electricity_per_ton_month",
        "coating_electricity_per_ton_daily",
        "coating_electricity_per_ton_month",
        "coating_gas_per_ton_daily",
        "coating_gas_per_ton_month",
    ),
    "contract_input": (
        "finished_inbound_daily",
        "consignment_weight",
        "finished_inbound_month",
        "daily_contract_weight",
        "daily_hot_roll_contract_weight",
        "cold_roll_input_daily",
        "cold_2050_input_daily",
        "cold_1850_input_daily",
        "outsourced_input_daily",
        "medium_plate_input_daily",
        "remaining_contract_weight",
        "remaining_contract_delta",
    ),
    "yield": (
        "daily_yield_rate",
        "daily_yield_delta",
        "hot_roll_yield_rate",
        "hot_roll_yield_delta",
        "monthly_yield_rate",
        "cast_roll_yield_rate",
        "plate_coil_yield_rate",
        "hot_roll_monthly_yield_rate",
    ),
    "cost": (
        "electricity_cost_10k",
        "gas_cost_10k",
        "total_cost_10k",
        "cost_basis_weight",
        "cost_per_ton",
    ),
}

FIELD_SOURCE_POLICY: dict[str, tuple[str, ...]] = {
    "hot_roll_daily": ("owner_daily", "manual_mobile_coil"),
    "foundry_daily": ("owner_daily", "manual_mobile_coil"),
    "cast_roll_active_lines": ("owner_daily",),
    "recovery_daily": ("owner_daily", "recovery_daily"),
    "roller_grind_daily": ("owner_daily", "overhaul_daily"),
    "daily_contract_weight": ("contract_projection", "owner_daily"),
    "remaining_contract_weight": ("contract_projection", "owner_daily"),
}


def field_group(field_name: str) -> str:
    for group, fields in FIELD_GROUPS.items():
        if field_name in fields:
            return group
    return "unclassified"


def fields_for_group(group: str) -> tuple[str, ...]:
    return FIELD_GROUPS.get(group, ())


def all_contract_fields() -> set[str]:
    fields: set[str] = set()
    for group_fields in FIELD_GROUPS.values():
        fields.update(group_fields)
    return fields


def group_missing_fields(fields: Iterable[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for field in fields:
        grouped.setdefault(field_group(field), []).append(field)
    return grouped
