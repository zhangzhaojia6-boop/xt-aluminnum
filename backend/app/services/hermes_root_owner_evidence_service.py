from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from sqlalchemy.orm import Session

from app.core.business_time import production_business_window
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.domain.metric_contracts import DAILY_REPORT_METRIC_CONTRACTS
from app.services.hermes_daily_fact_update_service import extract_daily_fact_update_candidates
from app.services.hermes_dingtalk_evidence_service import (
    DingTalkEvidenceItem,
    query_dingtalk_evidence,
)
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.report import daily_fact_bundle


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    source_key: str
    source_type: str
    domain: str
    priority: int
    status: str
    value: Mapping[str, Any] | list[Any] | None
    summary: str
    trace_ref: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    primary: EvidenceCandidate | None
    candidates: tuple[EvidenceCandidate, ...]
    conflicts: tuple[dict[str, Any], ...]
    missing_sources: list[str]
    trace: dict[str, Any]


DINGTALK_PRIORITY = 10
EXTERNAL_READONLY_PRIORITY = 20
DATA_HUB_PRIORITY = 40

_PRODUCTION_QUERY_KEYS = {
    "total_output_daily": "workshop_process_records",
    "workshop_output_daily": "workshop_process_records",
    "finished_inbound_daily": "finished_inbound_records",
    "daily_input_weight": "material_records",
    "daily_yield_rate": "yield_records",
    "wip_total": "wip_totals",
    "remaining_contract_weight": "stock_records",
}
_MES_DOMAINS = {"production", "factory_overview", "anomaly", "inventory", "quality", "operations", "energy"}
_MES_METRIC_FIELD_ALIASES = {
    "total_output_daily": ("total_output_daily", "net_weight", "weight", "output_weight", "quantity"),
    "workshop_output_daily": ("workshop_output_daily", "net_weight", "weight", "output_weight", "quantity"),
    "finished_inbound_daily": ("finished_inbound_daily", "net_weight", "weight", "output_weight", "quantity"),
    "daily_input_weight": ("daily_input_weight", "net_weight", "weight", "input_weight", "quantity"),
    "daily_yield_rate": ("daily_yield_rate", "yield_rate", "plant_wide_yield_rate", "YieldRate", "Yield", "CraftYield", "value"),
    "wip_total": ("wip_total", "total_weight", "doing_weight", "DoingWeight", "weight", "quantity"),
    "remaining_contract_weight": (
        "remaining_contract_weight",
        "remaining_weight",
        "weight",
        "quantity",
    ),
}


DingTalkReader = Callable[..., list[EvidenceCandidate]]
HubReader = Callable[..., Mapping[str, Any] | None]


def collect_root_owner_evidence(
    db: Session | None,
    *,
    message_plan: Any,
    trace_id: str,
    dingtalk_reader: DingTalkReader | None = None,
    mes_reader: HermesMesReadService | None = None,
    hub_reader: HubReader | None = None,
) -> EvidenceDecision:
    candidates: list[EvidenceCandidate] = []
    missing_sources: list[str] = []
    source_status: dict[str, dict[str, Any]] = {}
    supporting_evidence: list[dict[str, Any]] = []

    if dingtalk_reader is not None:
        dingtalk_candidates = dingtalk_reader(
            db=db,
            business_date=message_plan.business_date,
            trace_id=trace_id,
        )
        dingtalk_read_status: dict[str, Any] = {}
    else:
        dingtalk_candidates, dingtalk_read_status = _read_dingtalk_candidates_with_status(
            db,
            business_date=message_plan.business_date,
            metric_keys=tuple(message_plan.metric_keys),
        )
    if dingtalk_candidates:
        primary_dingtalk_candidates = [
            candidate
            for candidate in dingtalk_candidates
            if _is_current_dingtalk_metric_fact(candidate, message_plan.metric_keys)
        ]
        supporting_dingtalk_candidates = [
            candidate for candidate in dingtalk_candidates if candidate not in primary_dingtalk_candidates
        ]
        candidates.extend(primary_dingtalk_candidates)
        supporting_evidence.extend(
            _candidate_trace_detail(candidate, status="supporting_only", reason="no_current_metric_fact")
            for candidate in supporting_dingtalk_candidates
        )
        dingtalk_status = dingtalk_read_status.get("status")
        if dingtalk_status not in {"failed", "partial_failed"}:
            dingtalk_status = "ok" if primary_dingtalk_candidates else "supporting_only"
        source_status["dingtalk_group_content"] = {
            **dingtalk_read_status,
            "status": dingtalk_status,
            "candidate_count": len(primary_dingtalk_candidates),
            "supporting_count": len(supporting_dingtalk_candidates),
        }
        if not primary_dingtalk_candidates:
            source_status["dingtalk_group_content"].setdefault("reason", "no_current_metric_fact")
    else:
        missing_sources.append("dingtalk_group_content")
        source_status["dingtalk_group_content"] = {
            **dingtalk_read_status,
            "status": dingtalk_read_status.get("status") or "missing",
            "candidate_count": 0,
            "supporting_count": 0,
            "reason": dingtalk_read_status.get("reason") or "no_candidates",
        }

    mes_query_keys = _planned_mes_query_keys(message_plan)
    if message_plan.domain in _MES_DOMAINS:
        if mes_reader is None:
            missing_sources.append("mes_readonly")
            source_status["mes_readonly"] = {
                "status": "missing",
                "reason": "reader_unavailable",
                "query_keys": mes_query_keys,
            }
        else:
            mes_candidate, mes_status = _read_mes_candidate(
                mes_reader,
                message_plan=message_plan,
                query_keys=mes_query_keys,
            )
            source_status["mes_readonly"] = mes_status
            if mes_candidate is None:
                missing_sources.append("mes_readonly")
            elif mes_candidate.status == "supporting_only":
                supporting_evidence.append(
                    _candidate_trace_detail(
                        mes_candidate,
                        status="supporting_only",
                        reason="metric_fact_without_contract",
                    )
                )
            else:
                candidates.append(mes_candidate)

    hub_payload, hub_status = _read_hub_payload(
        db,
        message_plan.business_date,
        hub_reader=hub_reader,
    )
    source_status["data_hub_projection"] = hub_status
    if hub_payload:
        raw_hub_status = str(hub_payload.get("status") or "ok")
        hub_fact = _extract_hub_metric_fact(hub_payload, tuple(message_plan.metric_keys))
        if hub_fact:
            hub_candidate_status = _hub_candidate_status(raw_hub_status, hub_fact)
            candidates.append(
                EvidenceCandidate(
                    source_key="data_hub_projection",
                    source_type="data_hub",
                    domain=message_plan.domain,
                    priority=DATA_HUB_PRIORITY,
                    status=hub_candidate_status,
                    value=filter_sensitive_mapping(hub_fact),
                    summary="数据中枢投影已读取当前指标",
                    trace_ref={"source": "daily_fact_bundle", "status": raw_hub_status},
                )
            )
            source_status["data_hub_projection"]["candidate_status"] = hub_candidate_status
        else:
            missing_sources.append("data_hub_projection")
            source_status["data_hub_projection"]["reason"] = "no_current_metric_fact"
    else:
        missing_sources.append("data_hub_projection")

    decision = choose_primary_evidence(candidates, domain=message_plan.domain)
    trace = {
        "trace_id": trace_id,
        "business_date": message_plan.business_date.isoformat(),
        "domain": message_plan.domain,
        "intent": message_plan.intent,
        "source_order": [candidate.source_key for candidate in decision.candidates],
        "missing_sources": missing_sources,
        "source_status": source_status,
        "supporting_evidence": supporting_evidence,
        "conflicts": list(decision.conflicts),
    }
    hub_gap_plan = _trace_gap_plan(hub_payload)
    if hub_gap_plan:
        trace["gap_plan"] = hub_gap_plan
    return EvidenceDecision(
        primary=decision.primary,
        candidates=decision.candidates,
        conflicts=decision.conflicts,
        missing_sources=missing_sources,
        trace=trace,
    )


def choose_primary_evidence(candidates: list[EvidenceCandidate], *, domain: str) -> EvidenceDecision:
    usable = [candidate for candidate in candidates if candidate.status in {"ok", "confirmed", "candidate"}]
    sorted_candidates = tuple(sorted(usable, key=_evidence_sort_key))
    primary = sorted_candidates[0] if sorted_candidates else None
    conflicts: list[dict[str, Any]] = []
    if primary is not None:
        for candidate in sorted_candidates[1:]:
            for field_name in _conflicting_candidate_fields(primary.value, candidate.value):
                conflicts.append(
                    {
                        "domain": domain,
                        "field": field_name,
                        "chosen_source": primary.source_key,
                        "lower_source": candidate.source_key,
                        "chosen_priority": primary.priority,
                        "lower_priority": candidate.priority,
                        "reason": "higher_priority_fact_source",
                    }
                )
    return EvidenceDecision(
        primary=primary,
        candidates=sorted_candidates,
        conflicts=tuple(conflicts),
        missing_sources=[],
        trace={"domain": domain},
    )


def _evidence_sort_key(candidate: EvidenceCandidate) -> tuple[int, int]:
    return (candidate.priority, _dingtalk_content_rank(candidate))


def _dingtalk_content_rank(candidate: EvidenceCandidate) -> int:
    if candidate.source_type != "dingtalk_group_content":
        return 0
    source_key = candidate.source_key.lower()
    source = str(candidate.trace_ref.get("source") or "").lower()
    content_type = str(candidate.trace_ref.get("content_type") or "").lower()
    haystack = f"{source_key} {source} {content_type}"
    if "text" in haystack or "chat" in haystack:
        return 0
    if "file" in haystack:
        return 1
    if "image" in haystack:
        return 2
    return 3


def _read_dingtalk_candidates(db: Session | None, *, business_date) -> list[EvidenceCandidate]:
    candidates, _status = _read_dingtalk_candidates_with_status(db, business_date=business_date, metric_keys=())
    return candidates


def _read_dingtalk_candidates_with_status(
    db: Session | None,
    *,
    business_date,
    metric_keys: tuple[str, ...],
) -> tuple[list[EvidenceCandidate], dict[str, Any]]:
    if db is None:
        return [], {"status": "missing", "reason": "db_unavailable", "sources": {}}
    result: list[EvidenceCandidate] = []
    sources: dict[str, dict[str, Any]] = {}
    try:
        items = query_dingtalk_evidence(db, business_date=business_date)
    except Exception as exc:
        error = redact_secret_text(str(exc))
        sources = {
            "dingtalk_text": {"status": "failed", "count": 0, "error": error},
            "dingtalk_file": {"status": "failed", "count": 0, "error": error},
        }
        return [], _dingtalk_source_status(sources, [], metric_keys)
    grouped_items = {
        "dingtalk_text": [item for item in items if item.source_key == "dingtalk_group_content"],
        "dingtalk_file": [item for item in items if item.source_key == "dingtalk_group_file"],
    }
    for source_name, source_items in grouped_items.items():
        source_status = "ok" if source_items else "empty"
        sources[source_name] = {
            "status": source_status,
            "count": len(source_items),
        }
        for index, item in enumerate(source_items):
            fact_value = _extract_dingtalk_item_metric_fact(item, set(metric_keys))
            source_key = "dingtalk_group_file" if source_name == "dingtalk_file" else "dingtalk_group_chat"
            if fact_value:
                result.append(
                    EvidenceCandidate(
                        source_key=source_key,
                        source_type="dingtalk_group_content",
                        domain="factory",
                        priority=DINGTALK_PRIORITY,
                        status="ok",
                        value=filter_sensitive_mapping(fact_value),
                        summary=f"{source_key} 解析到指标事实",
                        trace_ref={
                            "source": source_name,
                            "item_index": index,
                            "count": len(source_items),
                            "trace_id": item.trace_id,
                            "content_kind": item.content_kind,
                            "adoptable_as_fact": item.adoptable_as_fact,
                        },
                    )
                )
                continue
            if not item.visible_to_hermes:
                continue
            result.append(
                EvidenceCandidate(
                    source_key=source_key,
                    source_type="dingtalk_group_content",
                    domain="factory",
                    priority=DINGTALK_PRIORITY,
                    status="supporting_only",
                    value=filter_sensitive_mapping(
                        {
                            "evidence_id": item.evidence_id,
                            "trace_id": item.trace_id,
                            "content_kind": item.content_kind,
                            "text": item.text,
                            "confirmation_status": item.confirmation_status,
                            "parse_status": item.parse_status,
                            "adoptable_as_fact": item.adoptable_as_fact,
                        }
                    ),
                    summary=f"{source_key} 命中辅助证据",
                    trace_ref={
                        "source": source_name,
                        "item_index": index,
                        "count": len(source_items),
                        "trace_id": item.trace_id,
                        "content_kind": item.content_kind,
                        "adoptable_as_fact": item.adoptable_as_fact,
                    },
                )
            )
    return result, _dingtalk_source_status(sources, result, metric_keys)


def _dingtalk_source_status(
    sources: Mapping[str, Mapping[str, Any]],
    candidates: list[EvidenceCandidate],
    metric_keys: tuple[str, ...],
) -> dict[str, Any]:
    statuses = [str(source.get("status") or "missing") for source in sources.values()]
    candidate_count = sum(1 for candidate in candidates if _is_current_dingtalk_metric_fact(candidate, metric_keys))
    supporting_count = len(candidates) - candidate_count
    if any(status == "failed" for status in statuses):
        status = "failed" if all(status == "failed" for status in statuses) else "partial_failed"
        reason = "source_failed"
    elif any(status == "partial_failed" for status in statuses):
        status = "partial_failed"
        reason = "source_partial_failed"
    elif candidate_count:
        status = "ok"
        reason = None
    elif supporting_count:
        status = "supporting_only"
        reason = "no_current_metric_fact"
    else:
        status = "missing"
        reason = "no_candidates"
    detail: dict[str, Any] = {
        "status": status,
        "candidate_count": candidate_count,
        "supporting_count": supporting_count,
        "sources": dict(sources),
    }
    if reason:
        detail["reason"] = reason
    return detail


def _read_mes_candidate(
    mes_reader: HermesMesReadService,
    *,
    message_plan: Any,
    query_keys: list[str],
) -> tuple[EvidenceCandidate | None, dict[str, Any]]:
    try:
        payload = mes_reader.read_sources(business_date=message_plan.business_date, query_keys=query_keys)
    except Exception as exc:
        return None, {
            "status": "failed",
            "query_keys": query_keys,
            "error": redact_secret_text(f"{type(exc).__name__}: {exc}"),
        }
    if not payload:
        return None, {"status": "missing", "reason": "empty_payload", "query_keys": query_keys}
    status = str((payload.get("source_status") or {}).get("mes") or "empty")
    status_detail = {
        "status": status,
        "query_keys": query_keys,
        "source_status": filter_sensitive_mapping(payload.get("source_status") or {}),
        "source_errors": redact_secret_text(str(payload.get("source_errors") or {})),
    }
    if status not in {"ok", "partial_failed"}:
        status_detail["reason"] = "source_status_not_ok"
        return None, status_detail
    metric_fact = _extract_mes_metric_fact(payload.get("records") or {}, tuple(message_plan.metric_keys))
    if not metric_fact:
        status_detail["reason"] = "no_current_metric_fact"
        return None, status_detail
    candidate_status = "ok" if status == "ok" else "candidate"
    if not _has_structured_metric_fact(metric_fact):
        candidate_status = "supporting_only"
        status_detail["upstream_status"] = status
        status_detail["status"] = "supporting_only"
        status_detail["reason"] = "metric_fact_without_contract"
    return (
        EvidenceCandidate(
            source_key="mes_readonly",
            source_type="external_readonly",
            domain=message_plan.domain,
            priority=EXTERNAL_READONLY_PRIORITY,
            status=candidate_status,
            value=filter_sensitive_mapping(metric_fact),
            summary="MES 只读库已读取当前指标",
            trace_ref=status_detail,
        ),
        status_detail,
    )


def _read_hub_payload(
    db: Session | None,
    business_date,
    *,
    hub_reader: HubReader | None,
) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
    try:
        if hub_reader:
            payload = hub_reader(db=db, business_date=business_date)
        elif db is None:
            return None, {"status": "missing", "reason": "db_unavailable"}
        else:
            payload = daily_fact_bundle.build_daily_fact_bundle(
                db,
                business_date=business_date,
                allow_output_skill_reference_adoption=False,
            )
    except Exception as exc:
        return None, {"status": "failed", "error": redact_secret_text(f"{type(exc).__name__}: {exc}")}
    if payload:
        return payload, {"status": str(payload.get("status") or "ok")}
    return None, {"status": "missing", "reason": "empty_payload"}


def _planned_mes_query_keys(message_plan: Any) -> list[str]:
    query_keys = sorted(
        {
            _PRODUCTION_QUERY_KEYS[metric_key]
            for metric_key in message_plan.metric_keys
            if metric_key in _PRODUCTION_QUERY_KEYS
        }
    )
    if query_keys:
        return query_keys
    return ["workshop_process_records", "finished_inbound_records"]


def _is_current_dingtalk_metric_fact(candidate: EvidenceCandidate, metric_keys: tuple[str, ...]) -> bool:
    return (
        candidate.source_type == "dingtalk_group_content"
        and candidate.status in {"ok", "confirmed", "candidate"}
        and _extract_direct_metric_fact(candidate.value, set(metric_keys)) is not None
    )


def _extract_dingtalk_item_metric_fact(item: DingTalkEvidenceItem, metric_keys: set[str]) -> dict[str, Any] | None:
    if not item.adoptable_as_fact or not metric_keys:
        return None
    candidates = extract_daily_fact_update_candidates(
        {
            "id": item.evidence_id,
            "trace_id": item.trace_id,
            "recognized_text": item.text,
            "payload": dict(item.payload),
        }
    )
    result: dict[str, Any] = {}
    for candidate in candidates:
        field_name = str(candidate.get("field") or "").strip()
        if field_name in metric_keys and _has_metric_value(candidate.get("value")):
            contract = DAILY_REPORT_METRIC_CONTRACTS.get(field_name)
            if contract is None or item.business_date is None:
                continue
            window_start, window_end = production_business_window(item.business_date)
            business_date = item.business_date.isoformat()
            business_window = f"{window_start.isoformat()}/{window_end.isoformat()}"
            source_key = str(item.source_key or "dingtalk_group_content")
            source_ref = {
                "source_key": source_key,
                "evidence_id": item.evidence_id,
                "trace_id": item.trace_id,
                "business_date": business_date,
                "business_window": business_window,
                "unit": contract.unit,
                "metric_contract_version": contract.metric_contract_version,
            }
            for key in (
                "numerator_field",
                "numerator_evidence_id",
                "denominator_field",
                "denominator_evidence_id",
            ):
                if candidate.get(key) not in (None, ""):
                    source_ref[key] = candidate[key]
            result[field_name] = {
                "value": candidate.get("value"),
                "status": "confirmed",
                "source_key": source_key,
                "source_type": "dingtalk_supplement",
                "source_ref": source_ref,
                "business_date": business_date,
                "business_window": business_window,
                "unit": contract.unit,
                "metric_contract_version": contract.metric_contract_version,
                "trace_id": item.trace_id,
                "source_trace_id": item.trace_id,
            }
    return result or None


def _extract_hub_metric_fact(payload: Mapping[str, Any], metric_keys: tuple[str, ...]) -> dict[str, Any] | None:
    metric_key_set = set(metric_keys)
    if not metric_key_set:
        return None
    result: dict[str, Any] = {}
    facts = payload.get("facts")
    if isinstance(facts, Mapping):
        values = facts.get("values")
        extracted = _extract_direct_metric_fact(values, metric_key_set)
        if extracted:
            result.update(extracted)
        extracted = _extract_direct_metric_fact(facts, metric_key_set)
        if extracted:
            result.update(extracted)
    direct = _extract_direct_metric_fact(payload, metric_key_set)
    if direct:
        result.update(direct)
    return result or None


def _extract_mes_metric_fact(records: Any, metric_keys: tuple[str, ...]) -> dict[str, Any] | None:
    metric_key_set = set(metric_keys)
    if not metric_key_set:
        return None
    direct = _extract_direct_metric_fact(records, metric_key_set) or {}
    result = dict(direct)
    if not isinstance(records, Mapping):
        return result or None
    for metric_key in metric_keys:
        if metric_key in result:
            continue
        query_key = _PRODUCTION_QUERY_KEYS.get(metric_key)
        if query_key is None:
            continue
        metric_value = _aggregate_mes_metric_value(records.get(query_key), metric_key)
        if metric_value is not None:
            result[metric_key] = metric_value
    return result or None


def _extract_direct_metric_fact(value: Any, metric_keys: set[str]) -> dict[str, Any] | None:
    if not metric_keys or not isinstance(value, Mapping):
        return None
    result: dict[str, Any] = {}
    metric_key = value.get("metric_key")
    if metric_key in metric_keys and _has_metric_value(value.get("value")):
        result[str(metric_key)] = value.get("value")
    for item in metric_keys:
        if _has_metric_value(value.get(item)):
            result[item] = value[item]
    return result or None


def _aggregate_mes_metric_value(value: Any, metric_key: str) -> float | None:
    if isinstance(value, Mapping):
        records = [value]
    elif isinstance(value, list):
        records = value
    else:
        records = []
    total = 0.0
    matched = False
    for record in records:
        number = _mes_record_metric_number(record, metric_key)
        if number is None:
            continue
        total += number
        matched = True
    return round(total, 3) if matched else None


def _mes_record_metric_number(record: Any, metric_key: str) -> float | None:
    if not isinstance(record, Mapping):
        return None
    direct = _extract_direct_metric_fact(record, {metric_key})
    if direct:
        return _metric_number_or_none(direct.get(metric_key))
    for field in _MES_METRIC_FIELD_ALIASES.get(metric_key, ()):
        value = _mapping_value(record, field)
        if _has_metric_value(value):
            number = _metric_number_or_none(value)
            if number is not None:
                return number
    return None


def _has_metric_value(value: Any) -> bool:
    return value is not None and value != ""


def _mapping_value(value: Mapping[str, Any], field: str) -> Any:
    if field in value:
        return value[field]
    field_lower = field.lower()
    for key, item in value.items():
        if str(key).lower() == field_lower:
            return item
    metadata = value.get("metadata")
    if isinstance(metadata, Mapping):
        if field in metadata:
            return metadata[field]
        for key, item in metadata.items():
            if str(key).lower() == field_lower:
                return item
    return None


def _metric_number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _candidate_status(status: str) -> str:
    if status == "ready":
        return "ok"
    if status == "partial_failed":
        return "candidate"
    return status or "ok"


def _hub_candidate_status(status: str, metric_fact: Mapping[str, Any]) -> str:
    if _has_structured_metric_fact(metric_fact):
        return "ok"
    return _candidate_status(status)


def _has_structured_metric_fact(metric_fact: Mapping[str, Any]) -> bool:
    return any(
        isinstance(field_fact, Mapping) and _has_metric_value(field_fact.get("value"))
        for field_fact in metric_fact.values()
    )


def _trace_gap_plan(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    gap_plan = payload.get("gap_plan")
    if not isinstance(gap_plan, Mapping):
        return None
    safe_items: list[dict[str, Any]] = []
    items = gap_plan.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, Mapping):
                continue
            safe_item = {
                key: item[key]
                for key in ("field", "metric_key", "action", "next_step")
                if item.get(key) not in (None, "")
            }
            if safe_item:
                safe_items.append(filter_sensitive_mapping(safe_item))
    return {
        "status": str(gap_plan.get("status") or ""),
        "items": safe_items,
    }


def _candidate_trace_detail(
    candidate: EvidenceCandidate,
    *,
    status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "source_key": candidate.source_key,
        "source_type": candidate.source_type,
        "status": status,
        "reason": reason,
        "summary": candidate.summary,
        "trace_ref": filter_sensitive_mapping(dict(candidate.trace_ref)),
    }


def _candidate_value_differs(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return _comparable_candidate_value(left) != _comparable_candidate_value(right)


def _conflicting_candidate_fields(left: Any, right: Any) -> tuple[str, ...]:
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return ()
    shared_fields = set(left).intersection(right)
    return tuple(
        str(field_name)
        for field_name in sorted(shared_fields, key=str)
        if _candidate_value_differs(
            {field_name: left[field_name]},
            {field_name: right[field_name]},
        )
    )


def _comparable_candidate_value(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if not isinstance(value, Mapping):
        return value
    return {
        key: item.get("value") if isinstance(item, Mapping) and "value" in item else item
        for key, item in value.items()
    }
