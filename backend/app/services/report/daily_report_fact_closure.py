from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import date
from typing import Any
from urllib.parse import quote, urlencode

from sqlalchemy import literal
from sqlalchemy.orm import Session

from app.domain.metric_contracts import daily_report_contract_for
from app.models.agent_communication import AgentEvent
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot
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
EXPLICIT_EVIDENCE_STATUS_SOURCE_TYPES = {"manual_workbook"}


def build_daily_report_fact_closure(bundle: Mapping[str, Any]) -> dict[str, Any]:
    reference_only = bool(bundle.get("reference_only"))
    facts = _mapping(bundle.get("facts"))
    sources = _mapping(bundle.get("sources"))
    alignment = _mapping(bundle.get("output_skill_alignment"))
    mismatch_fields = _alignment_difference_fields(alignment) | _mismatch_conflict_fields(bundle.get("conflicts"))
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
        source = _source_for_field(field, fact, sources.get(field))
        value = _value_for_field(bundle, fact, field)
        unit = fact.get("unit")
        business_window = _mapping(fact.get("source_detail")).get("business_window")
        trace_id = _trace_id_for_field(fact, sources.get(field))
        status = _field_status(
            field,
            value,
            source_types,
            unit,
            business_window,
            trace_id,
            missing_fields,
            mismatch_fields,
            evidence_status=fact.get("evidence_status"),
        )
        counts[status] += 1
        critical_fields.append(
            {
                "field": field,
                "value": value,
                "unit": unit,
                "status": status,
                "source": source,
                "business_window": business_window,
                "trace_id": trace_id,
                "action": action_by_field[field],
            }
        )

    return {
        "status": "blocked" if reference_only or any(item["status"] in BLOCKING_STATUSES for item in critical_fields) else "pass",
        "reference_only": reference_only,
        "critical_fields": critical_fields,
        "counts": {status: counts.get(status, 0) for status in ("confirmed", "mismatch", "missing", "needs_evidence")},
    }


def build_persisted_daily_fact_surface(
    db: Session | None,
    *,
    target_date: date,
) -> dict[str, Any]:
    snapshot = _latest_daily_fact_snapshot(db, target_date=target_date)
    facts = _mapping(snapshot.facts) if snapshot is not None else {}
    sources = _mapping(snapshot.sources) if snapshot is not None else {}
    conflicts = snapshot.conflicts if snapshot is not None and isinstance(snapshot.conflicts, list) else []

    closure_facts: dict[str, Any] = {}
    for field in CRITICAL_DAILY_FACT_FIELDS:
        raw_fact = facts.get(field)
        if isinstance(raw_fact, Mapping):
            closure_facts[field] = dict(raw_fact)
        else:
            closure_facts[field] = {
                "value": None,
                "unit": daily_report_contract_for(field).unit,
            }

    closure = build_daily_report_fact_closure(
        {
            "facts": closure_facts,
            "sources": sources,
            "conflicts": conflicts,
        }
    )
    capability = {
        "status": "available" if snapshot is not None else "missing",
        "agent_failure_audit": "unavailable",
    }
    fact_tasks = _daily_fact_gap_event_alerts(db, target_date=target_date)
    if snapshot is None:
        return {
            "fact_closure": closure,
            "fact_closure_available": False,
            "fact_closure_capability": capability,
            "fact_conflicts": [],
            "fact_missing": fact_tasks,
            "hermes_failures": [],
            "dingtalk_inbound_failures": [],
        }

    fact_conflicts = _fact_conflict_alerts(conflicts, target_date=target_date)
    fact_missing = fact_tasks or _fact_missing_alerts(closure, target_date=target_date)
    return {
        "fact_closure": closure,
        "fact_closure_available": True,
        "fact_closure_capability": capability,
        "fact_conflicts": fact_conflicts,
        "fact_missing": fact_missing,
        "hermes_failures": [],
        "dingtalk_inbound_failures": [],
    }


def _latest_daily_fact_snapshot(
    db: Session | None,
    *,
    target_date: date,
) -> DailyFactBundleSnapshot | None:
    if db is None:
        return None
    canonical_key = literal("scheduled_daily_closure:") + DailyFactBundleRun.run_key
    return (
        db.query(DailyFactBundleSnapshot)
        .join(DailyFactBundleRun, DailyFactBundleRun.id == DailyFactBundleSnapshot.run_id)
        .filter(
            DailyFactBundleSnapshot.business_date == target_date,
            DailyFactBundleRun.business_date == target_date,
            DailyFactBundleSnapshot.snapshot_reason == "scheduled_daily_closure",
            DailyFactBundleSnapshot.snapshot_key == canonical_key,
        )
        .order_by(DailyFactBundleSnapshot.created_at.desc(), DailyFactBundleSnapshot.id.desc())
        .first()
    )


def _fact_conflict_alerts(conflicts: Any, *, target_date: date) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if not isinstance(conflicts, list):
        return alerts
    for index, raw in enumerate(conflicts):
        if not isinstance(raw, Mapping):
            continue
        field = str(raw.get("field") or raw.get("field_name") or "unknown")
        item = _redact_untrusted_source_values(dict(raw), field=field)
        trace_id = _present_text(item.get("trace_id"))
        item.setdefault("id", f"{field}:{index}")
        item.setdefault("status", "mismatch")
        item["trace_id"] = trace_id
        item["target_date"] = target_date.isoformat()
        item.setdefault("summary", f"{field} 事实冲突")
        item["detail_route"] = _alerts_route(trace_id)
        alerts.append(item)
    return alerts


def _fact_missing_alerts(closure: Mapping[str, Any], *, target_date: date) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for raw in closure.get("critical_fields", []):
        if not isinstance(raw, Mapping) or raw.get("status") not in {"missing", "needs_evidence"}:
            continue
        field = str(raw.get("field") or "unknown")
        trace_id = _present_text(raw.get("trace_id"))
        gap_action = classify_daily_report_field_gap(field)
        alerts.append(
            {
                **dict(raw),
                "id": f"{field}:{raw.get('status')}",
                "trace_id": trace_id,
                "target_date": target_date.isoformat(),
                "summary": f"{field} 缺少可信事实",
                "entry_route": gap_action["entry_route"],
                "fill_strategy": gap_action["fill_strategy"],
                "owner_role": gap_action["owner_role"],
                "entry_fields": gap_action["entry_fields"],
                "next_step": gap_action["next_step"],
                "detail_route": _gap_detail_route(target_date, field, trace_id, gap_action),
            }
        )
    return alerts


def _daily_fact_gap_event_alerts(
    db: Session | None,
    *,
    target_date: date,
) -> list[dict[str, Any]]:
    if db is None:
        return []
    events = (
        db.query(AgentEvent)
        .filter(
            AgentEvent.event_type == "daily_fact_gap",
            AgentEvent.business_date == target_date,
            AgentEvent.status.in_(("new", "open", "pending", "resolved")),
        )
        .order_by(AgentEvent.occurred_at.desc(), AgentEvent.id.desc())
        .all()
    )
    alerts: list[dict[str, Any]] = []
    for event in events:
        payload = dict(event.payload) if isinstance(event.payload, Mapping) else {}
        field = str(payload.get("field") or "").strip()
        if not field:
            continue
        trace_id = _present_text(
            payload.get("last_checked_trace_id")
            or payload.get("trace_id")
            or payload.get("resolution_trace_id")
        )
        entry_route = str(payload.get("entry_route") or "/manage/alerts")
        entry_fields = [str(value) for value in payload.get("entry_fields") or [] if str(value).strip()]
        fill_strategy = str(payload.get("fill_strategy") or "source_recheck")
        owner_role = str(payload.get("owner_role") or "factory_dispatch")
        detail_route = (
            _alerts_route(trace_id)
            if event.status == "resolved"
            else _gap_detail_route(
                target_date,
                field,
                trace_id,
                {
                    "entry_route": entry_route,
                    "entry_fields": entry_fields,
                    "owner_role": owner_role,
                },
            )
        )
        alerts.append(
            {
                "id": event.id,
                "event_id": event.id,
                "field": field,
                "status": event.status,
                "fact_status": str(payload.get("fact_status") or "missing"),
                "source": None,
                "trace_id": trace_id,
                "target_date": target_date.isoformat(),
                "occurred_at": event.occurred_at.isoformat() if event.occurred_at is not None else None,
                "summary": str(payload.get("summary") or f"{field} 缺少可信事实"),
                "next_step": str(payload.get("next_step") or "请负责人补充可信事实并保留来源。"),
                "entry_route": entry_route,
                "fill_strategy": fill_strategy,
                "owner_role": owner_role,
                "entry_fields": entry_fields,
                "detail_route": detail_route,
                "delivery_status": payload.get("delivery_status"),
                "outbox_message_id": payload.get("outbox_message_id"),
            }
        )
    return alerts


def _alerts_route(trace_id: str | None) -> str:
    if trace_id is None:
        return "/manage/alerts"
    return f"/manage/alerts?trace_id={quote(trace_id, safe='')}"


def _gap_detail_route(
    target_date: date,
    field: str,
    trace_id: str | None,
    action: Mapping[str, Any],
) -> str:
    if str(action.get("entry_route") or "") != "/entry/fill":
        return _alerts_route(trace_id)
    entry_fields = [str(value) for value in action.get("entry_fields") or [] if str(value).strip()]
    return _entry_fill_route(
        target_date,
        field,
        trace_id,
        entry_field=entry_fields[0] if entry_fields else None,
        owner_role=_present_text(action.get("owner_role")),
    )


def _entry_fill_route(
    target_date: date,
    field: str,
    trace_id: str | None,
    *,
    entry_field: str | None = None,
    owner_role: str | None = None,
) -> str:
    params = {
        "business_date": target_date.isoformat(),
        "field": field,
    }
    if entry_field is not None:
        params["entry_field"] = entry_field
    if owner_role is not None:
        params["owner_role"] = owner_role
    if trace_id is not None:
        params["trace_id"] = trace_id
    return f"/entry/fill?{urlencode(params)}"


def _present_text(value: Any) -> str | None:
    if not _has_value(value):
        return None
    text = str(value).strip()
    return text or None


def _field_status(
    field: str,
    value: Any,
    source_types: list[str],
    unit: Any,
    business_window: Any,
    trace_id: Any,
    missing_fields: set[str],
    mismatch_fields: set[str],
    evidence_status: Any = None,
) -> str:
    if field in missing_fields:
        return "missing"
    if field in mismatch_fields:
        return "mismatch"
    if not _has_value(value) or not source_types:
        return "missing"
    if not _is_allowed_source(field, source_types):
        return "needs_evidence"
    if (
        any(source_type in EXPLICIT_EVIDENCE_STATUS_SOURCE_TYPES for source_type in source_types)
        and evidence_status != "confirmed"
    ):
        return "needs_evidence"
    if evidence_status == "needs_evidence":
        return "needs_evidence"
    if not _has_value(unit) or not _has_value(business_window) or not _has_value(trace_id):
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


def _mismatch_conflict_fields(raw_conflicts: Any) -> set[str]:
    if not isinstance(raw_conflicts, list):
        return set()
    fields: set[str] = set()
    for item in raw_conflicts:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status not in {"mismatch", "conflict"}:
            continue
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


def _source_for_field(field: str, fact: Mapping[str, Any], source_detail: Any) -> Any:
    source = _mapping(source_detail)
    fact_detail = _mapping(fact.get("source_detail"))
    nested_source = _mapping(source.get("source_detail"))
    for value in (
        fact.get("source"),
        fact.get("source_type"),
        fact_detail.get("source"),
        fact_detail.get("source_type"),
        source.get("source"),
        source.get("source_type"),
        nested_source.get("source"),
        nested_source.get("source_type"),
    ):
        if _source_value_is_allowed(field, value):
            return value
    return None


def _redact_untrusted_source_values(
    value: Any,
    *,
    field: str,
    source_context: bool = False,
) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _redact_untrusted_source_values(
                item,
                field=field,
                source_context=_is_source_value_key(key),
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_untrusted_source_values(
                item,
                field=field,
                source_context=source_context,
            )
            for item in value
        ]
    if source_context and not _source_value_is_allowed(field, value):
        return None
    return value


def _is_source_value_key(key: Any) -> bool:
    normalized = str(key).strip().lower()
    return (
        normalized in {"source", "source_type", "sources"}
        or normalized.endswith("_source")
        or normalized.endswith("_source_type")
        or (normalized.startswith("source_") and normalized != "source_detail")
    )


def _source_value_is_allowed(field: str, value: Any) -> bool:
    source_type = _normalize_source_type(value)
    if source_type is None:
        return False
    try:
        allowed = daily_report_contract_for(field).allowed_source_types
    except KeyError:
        return False
    return source_type in allowed


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
    allowed = daily_report_contract_for(field).allowed_source_types
    return bool(source_types) and all(source_type in allowed for source_type in source_types)
