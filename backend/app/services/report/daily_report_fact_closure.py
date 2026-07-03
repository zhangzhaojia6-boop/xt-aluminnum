from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from app.services.report.daily_report_gap_analysis import (
    build_daily_report_gap_plan,
    classify_daily_report_field_gap,
)


CRITICAL_DAILY_FACT_FIELDS = (
    "total_output_daily",
    "finished_inbound_daily",
    "wip_total",
    "total_electricity_kwh",
    "daily_yield_rate",
)

BLOCKING_STATUSES = {"missing", "mismatch", "needs_evidence"}
WEAK_SOURCE_TYPES = {
    "data_hub_projection",
    "yield_projection",
    "contract_projection",
    "rag",
    "historical_report",
    "output_skill",
    "unknown",
    "missing",
}
FIELD_ALLOWED_SOURCE_TYPES: dict[str, set[str]] = {
    "total_output_daily": {
        "dingtalk_supplement",
        "root_owner_correction",
        "daily_fact_bundle",
        "mes_packaging_output",
    },
    "finished_inbound_daily": {
        "dingtalk_supplement",
        "root_owner_correction",
        "daily_fact_bundle",
        "finished_inbound_output",
        "wms_direct",
    },
    "wip_total": {
        "dingtalk_supplement",
        "root_owner_correction",
        "daily_fact_bundle",
        "mes_wip_distribution",
        "mes_wip_total_snapshot",
    },
    "total_electricity_kwh": {
        "dingtalk_supplement",
        "root_owner_correction",
        "daily_fact_bundle",
        "data_hub_manual",
        "owner_daily",
        "owner_or_energy_summary",
        "manual_mobile_coil",
        "energy_cost",
    },
    "daily_yield_rate": {
        "dingtalk_supplement",
        "root_owner_correction",
        "daily_fact_bundle",
        "computed",
        "quality_yield_daily",
    },
}
def build_daily_report_fact_closure(bundle: Mapping[str, Any]) -> dict[str, Any]:
    facts = _mapping(bundle.get("facts"))
    sources = _mapping(bundle.get("sources"))
    alignment = _mapping(bundle.get("output_skill_alignment"))
    mismatch_fields = _alignment_difference_fields(alignment)
    missing_fields = {
        field
        for field in CRITICAL_DAILY_FACT_FIELDS
        if _is_missing_field(bundle, facts, sources, field)
    }
    action_by_field = _action_by_field(missing_fields, alignment, sources)

    critical_fields = []
    counts: Counter[str] = Counter()
    for field in CRITICAL_DAILY_FACT_FIELDS:
        fact = _mapping(facts.get(field))
        source_types = _source_types(fact, sources.get(field))
        source = source_types[0] if source_types else None
        value = _value_for_field(bundle, fact, field)
        status = _field_status(field, value, source_types, missing_fields, mismatch_fields)
        counts[status] += 1
        critical_fields.append(
            {
                "field": field,
                "status": status,
                "source": source,
                "trace_id": _trace_id_for_field(bundle, fact, sources.get(field)),
                "value": value,
                "action": action_by_field[field],
            }
        )

    return {
        "status": "blocked" if any(item["status"] in BLOCKING_STATUSES for item in critical_fields) else "pass",
        "critical_fields": critical_fields,
        "counts": {status: counts.get(status, 0) for status in ("confirmed", "mismatch", "missing", "needs_evidence")},
    }


def _field_status(
    field: str,
    value: Any,
    source_types: list[str],
    missing_fields: set[str],
    mismatch_fields: set[str],
) -> str:
    if field in missing_fields:
        return "missing"
    if field in mismatch_fields:
        return "mismatch"
    if not _has_value(value) or not source_types:
        return "missing"
    if not _is_allowed_source(field, source_types):
        return "needs_evidence"
    return "confirmed"


def _action_by_field(
    missing_fields: set[str],
    alignment: Mapping[str, Any],
    sources: Mapping[str, Any],
) -> dict[str, str]:
    plan = build_daily_report_gap_plan(
        missing_fields=sorted(missing_fields),
        alignment=alignment,
        sources=sources,
    )
    actions = {
        str(item["field"]): str(item["next_step"])
        for item in plan.get("items", [])
        if isinstance(item, Mapping) and item.get("field") and item.get("next_step")
    }
    for field in CRITICAL_DAILY_FACT_FIELDS:
        actions.setdefault(field, classify_daily_report_field_gap(field)["next_step"])
    return actions


def _is_missing_field(
    bundle: Mapping[str, Any],
    facts: Mapping[str, Any],
    sources: Mapping[str, Any],
    field: str,
) -> bool:
    if _is_marked_missing(bundle.get("missing_fields"), field) or _is_marked_missing(bundle.get("missing"), field):
        return True
    fact = _mapping(facts.get(field))
    value = _value_for_field(bundle, fact, field)
    return not _has_value(value) or not _source_types(fact, sources.get(field))


def _is_marked_missing(raw_missing: Any, field: str) -> bool:
    if isinstance(raw_missing, Mapping):
        return bool(raw_missing.get(field))
    if isinstance(raw_missing, (str, bytes)):
        return raw_missing == field
    try:
        return field in raw_missing
    except TypeError:
        return False


def _alignment_difference_fields(alignment: Mapping[str, Any]) -> set[str]:
    raw = alignment.get("differences")
    if not isinstance(raw, list):
        return set()
    fields: set[str] = set()
    for item in raw:
        if isinstance(item, Mapping):
            field = item.get("field") or item.get("field_name")
            if field:
                fields.add(str(field))
    return fields


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _value_for_field(bundle: Mapping[str, Any], fact: Mapping[str, Any], field: str) -> Any:
    if "value" in fact:
        return fact.get("value")
    return bundle.get(field)


def _source_types(fact: Mapping[str, Any], source_detail: Any) -> list[str]:
    source = _mapping(source_detail)
    values = (
        fact.get("source_type"),
        fact.get("source"),
        source.get("source_type"),
        source.get("source"),
    )
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        source_type = _normalize_source_type(value)
        if source_type and source_type not in seen:
            normalized.append(source_type)
            seen.add(source_type)
    return normalized


def _trace_id_for_field(
    bundle: Mapping[str, Any],
    fact: Mapping[str, Any],
    source_detail: Any,
) -> Any:
    source = _mapping(source_detail)
    return fact.get("trace_id") or source.get("trace_id") or bundle.get("trace_id")


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _normalize_source_type(value: Any) -> str | None:
    if not _has_value(value):
        return None
    source_type = str(value).strip().lower()
    for char in (" ", "/", "-"):
        source_type = source_type.replace(char, "_")
    while "__" in source_type:
        source_type = source_type.replace("__", "_")
    source_type = source_type.strip("_")
    if source_type == "dailyfactbundle":
        return "daily_fact_bundle"
    return source_type or None


def _is_allowed_source(field: str, source_types: list[str]) -> bool:
    if any(source_type in WEAK_SOURCE_TYPES for source_type in source_types):
        return False
    allowed = FIELD_ALLOWED_SOURCE_TYPES[field]
    return any(source_type in allowed for source_type in source_types)
