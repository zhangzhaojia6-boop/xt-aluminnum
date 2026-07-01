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
WEAK_SOURCE_MARKERS = (
    "projection",
    "rag",
    "historical_report",
    "output_skill",
    "unknown",
    "missing",
)
ACCEPTED_SOURCE_MARKERS = (
    "dingtalk",
    "root_owner",
    "mes",
    "wms",
    "finished_inbound_output",
    "owner",
    "energy_summary",
)


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
        source = _source_for_field(fact, sources.get(field))
        source_text = _source_evidence_text(fact, sources.get(field))
        value = _value_for_field(bundle, fact, field)
        status = _field_status(field, value, source, source_text, missing_fields, mismatch_fields)
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
    source: str | None,
    source_text: str,
    missing_fields: set[str],
    mismatch_fields: set[str],
) -> str:
    if field in missing_fields:
        return "missing"
    if field in mismatch_fields:
        return "mismatch"
    if not _has_value(value) or not source:
        return "missing"
    if not _is_allowed_source(source_text):
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
    source = _source_for_field(fact, sources.get(field))
    return not _has_value(value) or not source


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


def _source_for_field(fact: Mapping[str, Any], source_detail: Any) -> str | None:
    source_values = _source_values(fact) + _source_values(source_detail)
    return source_values[0] if source_values else None


def _source_evidence_text(fact: Mapping[str, Any], source_detail: Any) -> str:
    return " ".join(_source_values(fact) + _source_values(source_detail)).lower()


def _source_values(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in ("source", "source_type", "source_detail", "source_ref"):
            raw = value.get(key)
            if _has_value(raw):
                values.append(str(raw))
        return values
    if _has_value(value):
        return [str(value)]
    return []


def _trace_id_for_field(
    bundle: Mapping[str, Any],
    fact: Mapping[str, Any],
    source_detail: Any,
) -> Any:
    source = _mapping(source_detail)
    return fact.get("trace_id") or source.get("trace_id") or bundle.get("trace_id")


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _is_allowed_source(source_text: str) -> bool:
    if any(marker in source_text for marker in WEAK_SOURCE_MARKERS):
        return False
    return any(marker in source_text for marker in ACCEPTED_SOURCE_MARKERS)
