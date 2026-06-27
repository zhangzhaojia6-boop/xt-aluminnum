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
    "wip_total": "wip_totals",
    "remaining_contract_weight": "stock_records",
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

    dingtalk_candidates = (
        dingtalk_reader(db=db, business_date=message_plan.business_date, trace_id=trace_id)
        if dingtalk_reader is not None
        else _read_dingtalk_candidates(db, business_date=message_plan.business_date)
    )
    if dingtalk_candidates:
        candidates.extend(dingtalk_candidates)
    else:
        missing_sources.append("dingtalk_group_content")

    if message_plan.domain in {"production", "factory_overview", "anomaly"}:
        if mes_reader is None:
            missing_sources.append("mes_readonly")
        else:
            mes_candidate = _read_mes_candidate(mes_reader, message_plan=message_plan)
            if mes_candidate is None:
                missing_sources.append("mes_readonly")
            else:
                candidates.append(mes_candidate)

    hub_payload = (
        hub_reader(db=db, business_date=message_plan.business_date)
        if hub_reader
        else _read_hub_payload(db, message_plan.business_date)
    )
    if hub_payload:
        candidates.append(
            EvidenceCandidate(
                source_key="data_hub_projection",
                source_type="data_hub",
                domain=message_plan.domain,
                priority=DATA_HUB_PRIORITY,
                status=str(hub_payload.get("status") or "ok"),
                value=filter_sensitive_mapping(dict(hub_payload)),
                summary="数据中枢投影已读取",
                trace_ref={"source": "template_daily_report"},
            )
        )
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
            "conflicts": list(decision.conflicts),
        },
    )


def choose_primary_evidence(candidates: list[EvidenceCandidate], *, domain: str) -> EvidenceDecision:
    usable = [candidate for candidate in candidates if candidate.status in {"ok", "confirmed", "candidate"}]
    sorted_candidates = tuple(sorted(usable, key=lambda item: item.priority))
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


def _read_dingtalk_candidates(db: Session | None, *, business_date) -> list[EvidenceCandidate]:
    if db is None:
        return []
    payload = HermesDataAuditService(db)._read_dingtalk_evidence(business_date=business_date)
    result: list[EvidenceCandidate] = []
    for source_name in ("dingtalk_file", "dingtalk_text"):
        source_payload = payload.get(source_name) or {}
        items = source_payload.get("items") or []
        if not items:
            continue
        source_key = "dingtalk_group_file" if source_name == "dingtalk_file" else "dingtalk_group_chat"
        result.append(
            EvidenceCandidate(
                source_key=source_key,
                source_type="dingtalk_group_content",
                domain="factory",
                priority=DINGTALK_PRIORITY,
                status=str(source_payload.get("status") or "ok"),
                value=filter_sensitive_mapping({"items": items}),
                summary=f"{source_key} 命中 {len(items)} 条",
                trace_ref={"source": source_name, "count": len(items)},
            )
        )
    return result


def _read_mes_candidate(mes_reader: HermesMesReadService, *, message_plan: Any) -> EvidenceCandidate | None:
    query_keys = sorted(
        {
            _PRODUCTION_QUERY_KEYS[metric_key]
            for metric_key in message_plan.metric_keys
            if metric_key in _PRODUCTION_QUERY_KEYS
        }
    )
    if not query_keys:
        query_keys = ["workshop_process_records", "finished_inbound_records"]
    payload = mes_reader.read_sources(business_date=message_plan.business_date, query_keys=query_keys)
    status = str((payload.get("source_status") or {}).get("mes") or "empty")
    if status not in {"ok", "partial_failed"}:
        return None
    return EvidenceCandidate(
        source_key="mes_readonly",
        source_type="external_readonly",
        domain="production",
        priority=EXTERNAL_READONLY_PRIORITY,
        status="ok" if status == "ok" else "candidate",
        value=filter_sensitive_mapping(payload.get("records") or {}),
        summary="MES 只读库已读取",
        trace_ref={
            "query_keys": query_keys,
            "source_status": filter_sensitive_mapping(payload.get("source_status") or {}),
            "source_errors": redact_secret_text(str(payload.get("source_errors") or {})),
        },
    )


def _read_hub_payload(db: Session | None, business_date) -> Mapping[str, Any] | None:
    if db is None:
        return None
    try:
        return template_daily_report.build_template_daily_report_payload(db, target_date=business_date)
    except Exception:
        return None


def _candidate_value_differs(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return (
        asdict(left) != asdict(right)
        if hasattr(left, "__dataclass_fields__") and hasattr(right, "__dataclass_fields__")
        else left != right
    )
