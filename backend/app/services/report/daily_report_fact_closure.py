from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import date
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.business_time import production_business_window
from app.domain.metric_contracts import daily_report_contract_for
from app.models.agent_communication import AgentRun, ChatInboxMessage
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
        source = _source_for_field(fact, sources.get(field))
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
    fact_conflicts = _fact_conflict_alerts(conflicts, target_date=target_date)
    fact_missing = _fact_missing_alerts(closure, target_date=target_date)
    hermes_failures, dingtalk_failures = _failed_agent_alerts(db, target_date=target_date)
    return {
        "fact_closure": closure,
        "fact_conflicts": fact_conflicts,
        "fact_missing": fact_missing,
        "hermes_failures": hermes_failures,
        "dingtalk_inbound_failures": dingtalk_failures,
    }


def _latest_daily_fact_snapshot(
    db: Session | None,
    *,
    target_date: date,
) -> DailyFactBundleSnapshot | None:
    if db is None:
        return None

    def latest_for(reason: str) -> DailyFactBundleSnapshot | None:
        return (
            db.query(DailyFactBundleSnapshot)
            .join(DailyFactBundleRun, DailyFactBundleRun.id == DailyFactBundleSnapshot.run_id)
            .filter(
                DailyFactBundleSnapshot.business_date == target_date,
                DailyFactBundleRun.business_date == target_date,
                DailyFactBundleSnapshot.snapshot_reason == reason,
            )
            .order_by(DailyFactBundleSnapshot.created_at.desc(), DailyFactBundleSnapshot.id.desc())
            .first()
        )

    return latest_for("scheduled_daily_closure") or latest_for("formal_daily_report")


def _fact_conflict_alerts(conflicts: Any, *, target_date: date) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if not isinstance(conflicts, list):
        return alerts
    for index, raw in enumerate(conflicts):
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        field = str(item.get("field") or item.get("field_name") or "unknown")
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
        alerts.append(
            {
                **dict(raw),
                "id": f"{field}:{raw.get('status')}",
                "trace_id": trace_id,
                "target_date": target_date.isoformat(),
                "summary": f"{field} 缺少可信事实",
                "detail_route": _alerts_route(trace_id),
            }
        )
    return alerts


def _failed_agent_alerts(
    db: Session | None,
    *,
    target_date: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if db is None:
        return [], []
    start_at, end_at = production_business_window(target_date)
    rows = (
        db.query(AgentRun, ChatInboxMessage)
        .join(ChatInboxMessage, ChatInboxMessage.id == AgentRun.chat_inbox_id)
        .filter(
            AgentRun.created_at >= start_at,
            AgentRun.created_at < end_at,
            AgentRun.status == "failed",
        )
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        .limit(200)
        .all()
    )
    hermes: list[dict[str, Any]] = []
    dingtalk: list[dict[str, Any]] = []
    seen_traces: set[str] = set()
    for run, inbox in rows:
        trace_id = _present_text(run.trace_id)
        if trace_id is None or trace_id in seen_traces:
            continue
        seen_traces.add(trace_id)
        channel = _present_text(getattr(inbox, "channel", None))
        alert = {
            "id": run.id,
            "target_date": target_date.isoformat(),
            "occurred_at": run.created_at.isoformat(),
            "trace_id": trace_id,
            "agent_code": run.agent_code,
            "status": run.status,
            "channel": channel,
            "summary": f"{run.agent_code} 运行失败",
            "detail_route": _alerts_route(trace_id),
        }
        if channel and channel.lower().startswith("dingtalk"):
            dingtalk.append(alert)
        else:
            hermes.append(alert)
    return hermes, dingtalk


def _alerts_route(trace_id: str | None) -> str:
    if trace_id is None:
        return "/manage/alerts"
    return f"/manage/alerts?trace_id={quote(trace_id, safe='')}"


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


def _source_for_field(fact: Mapping[str, Any], source_detail: Any) -> Any:
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
        if _has_value(value):
            return value
    return None


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
