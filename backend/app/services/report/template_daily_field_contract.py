from __future__ import annotations

from collections.abc import Iterable

from app.domain.daily_report_field_names import TEMPLATE_FIELD_GROUPS


FIELD_GROUPS = TEMPLATE_FIELD_GROUPS

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
