from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.services.hermes_data_audit_service import HermesDataAuditService
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.report import template_daily_report


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
_DINGTALK_FACT_FIELDS = ("facts", "parsed_facts", "metrics", "payload")
_VALIDATION_CONTAINER_FIELDS = ("metadata", "validation", "fact_validation", "evidence_conditions")
_VALIDATION_TRUE_TEXT = {
    "1",
    "true",
    "yes",
    "y",
    "ok",
    "matched",
    "verified",
    "valid",
    "passed",
    "confirmed",
    "authorized",
}
_DINGTALK_CONTENT_TYPES = {"text", "file", "image"}
_DINGTALK_AUTHORIZED_GROUP_FIELDS = ("authorized_group", "group_authorized", "authorized")
_DINGTALK_SENDER_FIELDS = (
    "specialist_sender",
    "authorized_sender",
    "sender_verified",
    "responsible_sender",
)
_DINGTALK_TIME_FIELDS = ("time_range", "business_day_window", "time_range_matched")
_DINGTALK_SPECIALIST_METRIC_KEYS = {"dingtalk_specialist_evidence"}
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
        hub_candidate_status = _candidate_status(raw_hub_status)
        hub_fact = _extract_hub_metric_fact(hub_payload, tuple(message_plan.metric_keys))
        if hub_fact:
            candidates.append(
                EvidenceCandidate(
                    source_key="data_hub_projection",
                    source_type="data_hub",
                    domain=message_plan.domain,
                    priority=DATA_HUB_PRIORITY,
                    status=hub_candidate_status,
                    value=filter_sensitive_mapping(hub_fact),
                    summary="数据中枢投影已读取当前指标",
                    trace_ref={"source": "template_daily_report", "status": raw_hub_status},
                )
            )
            source_status["data_hub_projection"]["candidate_status"] = hub_candidate_status
        else:
            missing_sources.append("data_hub_projection")
            source_status["data_hub_projection"]["reason"] = "no_current_metric_fact"
    else:
        missing_sources.append("data_hub_projection")

    decision = choose_primary_evidence(candidates, domain=message_plan.domain)
    return EvidenceDecision(
        primary=decision.primary,
        candidates=decision.candidates,
        conflicts=decision.conflicts,
        missing_sources=missing_sources,
        trace={
            "trace_id": trace_id,
            "business_date": message_plan.business_date.isoformat(),
            "domain": message_plan.domain,
            "intent": message_plan.intent,
            "source_order": [candidate.source_key for candidate in decision.candidates],
            "missing_sources": missing_sources,
            "source_status": source_status,
            "supporting_evidence": supporting_evidence,
            "conflicts": list(decision.conflicts),
        },
    )


def choose_primary_evidence(candidates: list[EvidenceCandidate], *, domain: str) -> EvidenceDecision:
    usable = [candidate for candidate in candidates if candidate.status in {"ok", "confirmed", "candidate"}]
    sorted_candidates = tuple(sorted(usable, key=_evidence_sort_key))
    primary = sorted_candidates[0] if sorted_candidates else None
    conflicts: list[dict[str, Any]] = []
    if primary is not None:
        for candidate in sorted_candidates[1:]:
            if _candidate_value_differs(primary.value, candidate.value):
                conflicts.append(
                    {
                        "domain": domain,
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
    payload = HermesDataAuditService(db)._read_dingtalk_evidence(business_date=business_date)
    result: list[EvidenceCandidate] = []
    sources: dict[str, dict[str, Any]] = {}
    for source_name in ("dingtalk_file", "dingtalk_text"):
        source_payload = payload.get(source_name) or {}
        source_status = str(source_payload.get("status") or "missing")
        items = source_payload.get("items") or []
        sources[source_name] = {
            "status": source_status,
            "count": int(source_payload.get("count") or len(items)),
        }
        if source_payload.get("error"):
            sources[source_name]["error"] = redact_secret_text(str(source_payload.get("error")))
        if not items:
            continue
        source_key = "dingtalk_group_file" if source_name == "dingtalk_file" else "dingtalk_group_chat"
        for index, item in enumerate(items):
            fact_value = _extract_dingtalk_metric_fact(item, set(metric_keys))
            if fact_value:
                result.append(
                    EvidenceCandidate(
                        source_key=source_key,
                        source_type="dingtalk_group_content",
                        domain="factory",
                        priority=DINGTALK_PRIORITY,
                        status=_candidate_status(source_status),
                        value=filter_sensitive_mapping(fact_value),
                        summary=f"{source_key} 解析到指标事实",
                        trace_ref={
                            "source": source_name,
                            "item_index": index,
                            "count": len(items),
                            "fact_validated": True,
                        },
                    )
                )
                continue
            result.append(
                EvidenceCandidate(
                    source_key=source_key,
                    source_type="dingtalk_group_content",
                    domain="factory",
                    priority=DINGTALK_PRIORITY,
                    status=_candidate_status(source_status),
                    value=filter_sensitive_mapping({"items": [item]}),
                    summary=f"{source_key} 命中辅助证据",
                    trace_ref={"source": source_name, "item_index": index, "count": len(items)},
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
    return (
        EvidenceCandidate(
            source_key="mes_readonly",
            source_type="external_readonly",
            domain=message_plan.domain,
            priority=EXTERNAL_READONLY_PRIORITY,
            status="ok" if status == "ok" else "candidate",
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
            payload = template_daily_report.build_template_daily_report_payload(db, target_date=business_date)
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


def _extract_dingtalk_metric_fact(
    value: Any,
    metric_keys: set[str],
    validation_context: tuple[Mapping[str, Any], ...] = (),
) -> dict[str, Any] | None:
    if not metric_keys:
        return None
    if isinstance(value, Mapping):
        direct = _extract_direct_metric_fact(value, metric_keys)
        if direct and _dingtalk_fact_is_verified(
            value,
            *validation_context,
            require_specialist_sender=_requires_dingtalk_specialist_sender(direct),
        ):
            return direct
        next_context = (value, *validation_context)
        for field in _DINGTALK_FACT_FIELDS:
            extracted = _extract_dingtalk_metric_fact(value.get(field), metric_keys, next_context)
            if extracted:
                return extracted
    if isinstance(value, list):
        for item in value:
            extracted = _extract_dingtalk_metric_fact(item, metric_keys, validation_context)
            if extracted:
                return extracted
    return None


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


def _dingtalk_fact_is_verified(
    *values: Mapping[str, Any],
    require_specialist_sender: bool = False,
) -> bool:
    scopes = [scope for value in values for scope in _iter_validation_scopes(value)]
    return (
        _validation_field_matches(scopes, _DINGTALK_AUTHORIZED_GROUP_FIELDS, _validation_truthy)
        and (
            not require_specialist_sender
            or _validation_field_matches(scopes, _DINGTALK_SENDER_FIELDS, _validation_truthy)
        )
        and _content_type_verified(scopes)
        and _validation_field_matches(scopes, _DINGTALK_TIME_FIELDS, _validation_truthy)
    )


def _requires_dingtalk_specialist_sender(fact: Mapping[str, Any]) -> bool:
    return any(metric_key in _DINGTALK_SPECIALIST_METRIC_KEYS for metric_key in fact)


def _iter_validation_scopes(value: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    scopes: list[Mapping[str, Any]] = [value]
    for field in _VALIDATION_CONTAINER_FIELDS:
        child = value.get(field)
        if isinstance(child, Mapping):
            scopes.extend(_iter_validation_scopes(child))
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, Mapping):
                    scopes.extend(_iter_validation_scopes(item))
    return scopes


def _validation_field_matches(
    scopes: list[Mapping[str, Any]],
    fields: tuple[str, ...],
    predicate: Callable[[Any], bool],
) -> bool:
    return any(field in scope and predicate(scope.get(field)) for scope in scopes for field in fields)


def _content_type_verified(scopes: list[Mapping[str, Any]]) -> bool:
    if _validation_field_matches(scopes, ("content_type_verified",), _validation_truthy):
        return True
    return _validation_field_matches(scopes, ("content_type",), _supported_dingtalk_content_type)


def _validation_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    text = str(value or "").strip().lower()
    return text in _VALIDATION_TRUE_TEXT


def _supported_dingtalk_content_type(value: Any) -> bool:
    return str(value or "").strip().lower() in _DINGTALK_CONTENT_TYPES


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
    return (
        asdict(left) != asdict(right)
        if hasattr(left, "__dataclass_fields__") and hasattr(right, "__dataclass_fields__")
        else left != right
    )
