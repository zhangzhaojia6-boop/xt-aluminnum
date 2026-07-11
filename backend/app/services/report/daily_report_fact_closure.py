from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from app.domain.metric_contracts import daily_report_contract_for
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
DERIVED_REFERENCE_SOURCE_TYPES = {
    "official_daily_report",
    "datahub_final_daily_report",
    "daily_fact_bundle",
    "historical_report",
    "output_skill",
    "rag",
    "data_hub_projection",
    "yield_projection",
    "contract_projection",
    "computed",
    "unknown",
    "missing",
}


def build_daily_report_fact_closure(bundle: Mapping[str, Any]) -> dict[str, Any]:
    reference_only = bool(bundle.get("reference_only"))
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
        trace_id = _trace_id_for_field(fact, sources.get(field))
        status = _field_status(field, value, source_types, trace_id, missing_fields, mismatch_fields)
        counts[status] += 1
        critical_fields.append(
            {
                "field": field,
                "status": status,
                "source": source,
                "trace_id": trace_id,
                "value": value,
                "action": action_by_field[field],
            }
        )

    return {
        "status": "blocked" if reference_only or any(item["status"] in BLOCKING_STATUSES for item in critical_fields) else "pass",
        "reference_only": reference_only,
        "critical_fields": critical_fields,
        "counts": {status: counts.get(status, 0) for status in ("confirmed", "mismatch", "missing", "needs_evidence")},
    }


def _field_status(
    field: str,
    value: Any,
    source_types: list[str],
    trace_id: Any,
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
    if not _has_value(trace_id):
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
    fact_detail = _mapping(fact.get("source_detail"))
    nested_source = _mapping(source.get("source_detail"))
    values = (
        fact.get("source_type"),
        fact.get("source"),
        fact_detail.get("source_type"),
        fact_detail.get("source"),
        source.get("source_type"),
        source.get("source"),
        nested_source.get("source_type"),
        nested_source.get("source"),
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
    fact: Mapping[str, Any],
    source_detail: Any,
) -> Any:
    source = _mapping(source_detail)
    nested_source = _mapping(fact.get("source_detail"))
    return fact.get("trace_id") or nested_source.get("trace_id") or source.get("trace_id")


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
    if any(source_type in DERIVED_REFERENCE_SOURCE_TYPES for source_type in source_types):
        return False
    allowed = daily_report_contract_for(field).allowed_source_types
    return bool(source_types) and all(source_type in allowed for source_type in source_types)
