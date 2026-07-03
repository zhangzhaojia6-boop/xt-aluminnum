from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.system import User
from app.services import agent_communication_service
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.hermes_root_owner_evidence_service import (
    EvidenceDecision,
    collect_root_owner_evidence,
)
from app.services.hermes_root_owner_message_service import (
    RootOwnerMessagePlan,
    understand_root_owner_message,
)
from app.services.hermes_root_owner_reply_channel_service import ensure_root_owner_private_reply_channel


_CONTEXT_DOMAINS = {"production", "inventory", "energy", "anomaly"}
_HERMES_PUBLIC_NAME = "鑫泰铝业智能大脑"


@dataclass(frozen=True, slots=True)
class RootOwnerProductionTurnResult:
    trace_id: str
    status: str
    answer: str
    chat_inbox_id: int
    agent_run_id: int
    outbox_message_id: int
    dispatch_status: str
    dispatch_detail: str


def should_route_root_owner_production_turn(
    text: str,
    *,
    default_business_date: date | None = None,
) -> bool:
    plan = understand_root_owner_message(text, default_business_date=default_business_date)
    return plan.domain != "general" or plan.needs_clarification


def run_root_owner_production_turn(
    db: Session,
    *,
    text: str,
    current_user: User,
    sender_external_id: str | None,
    trace_id: str | None,
    source_payload: dict[str, Any] | None,
    default_business_date: date | None = None,
    mes_reader: HermesMesReadService | None = None,
) -> RootOwnerProductionTurnResult:
    clean_trace_id = str(trace_id or "").strip() or uuid4().hex
    clean_text = str(text or "").strip()
    sender_id = str(sender_external_id or getattr(current_user, "dingtalk_user_id", "") or "").strip()
    previous_domain = _previous_root_owner_private_domain(
        db,
        sender_id=sender_id,
        current_trace_id=clean_trace_id,
        current_text=clean_text,
    )
    plan = understand_root_owner_message(
        clean_text,
        default_business_date=default_business_date,
        previous_domain=previous_domain,
    )
    source = _source_payload_block(plan=plan, source_payload=source_payload)

    inbox = ChatInboxMessage(
        channel="dingtalk_private",
        group_id=None,
        sender_external_id=sender_id or None,
        text=clean_text,
        agent_code="factory_dispatch",
        trace_id=clean_trace_id,
        source_payload=filter_sensitive_mapping(
            {
                **(source_payload or {}),
                "source": "dingtalk_inbound",
                "root_owner_private_loop": True,
                "recognition_reason": plan.recognition_reason,
            }
        ),
    )
    db.add(inbox)
    db.flush()

    if plan.needs_clarification:
        decision = EvidenceDecision(primary=None, candidates=(), conflicts=(), missing_sources=[], trace={})
        question = plan.clarification_question or "你想看生产、库存、能耗还是异常？"
        answer = f"{_HERMES_PUBLIC_NAME}需要先确认：{question}"
        status = "clarifying"
    else:
        decision = collect_root_owner_evidence(
            db,
            message_plan=plan,
            trace_id=clean_trace_id,
            mes_reader=mes_reader,
        )
        answer = _build_natural_answer(plan=plan, decision=decision)
        status = "answered"

    run = AgentRun(
        trace_id=clean_trace_id,
        agent_code="factory_dispatch",
        chat_inbox_id=inbox.id,
        status=status,
        status_color=_status_color(decision),
        answer=answer,
        rag_citation_count=0,
        result_payload={
            "source": source,
            "recognition": _message_plan_payload(plan),
            "evidence": _evidence_payload(decision),
            "source_payload": source["source_payload"],
        },
    )
    db.add(run)
    db.flush()

    channel = ensure_root_owner_private_reply_channel(
        db,
        agent_code="factory_dispatch",
        dingtalk_user_id=sender_id,
        owner_name=str(getattr(current_user, "name", None) or "root_owner"),
    )
    message = agent_communication_service.queue_bound_message(
        db,
        agent_code="factory_dispatch",
        channel_key=channel["channel_key"],
        channel_type=channel["channel_type"],
        title=f"{_HERMES_PUBLIC_NAME}私聊回复",
        content=answer,
        business_date=plan.business_date,
        source_summary=(decision.primary.source_key if decision.primary else "clarification"),
        trace_id=clean_trace_id,
        payload={
            "chat_inbox_id": inbox.id,
            "agent_run_id": run.id,
            "recognition": _message_plan_payload(plan),
            "evidence": _evidence_payload(decision),
        },
        dedupe_key=f"root-owner-private:{clean_trace_id}",
    )
    dispatch = agent_communication_service.dispatch_outbox_message(db, message.id, sender=None)
    run.result_payload = {
        **(run.result_payload or {}),
        "source": source,
        "outbox_message_id": message.id,
        "dispatch_status": dispatch.status,
        "dispatch_detail": dispatch.detail,
        "dispatch": {
            "outbox_message_id": message.id,
            "status": dispatch.status,
            "detail": dispatch.detail,
        },
    }
    db.add(run)
    db.commit()
    db.refresh(run)
    db.refresh(message)

    return RootOwnerProductionTurnResult(
        trace_id=clean_trace_id,
        status=status,
        answer=answer,
        chat_inbox_id=inbox.id,
        agent_run_id=run.id,
        outbox_message_id=message.id,
        dispatch_status=dispatch.status,
        dispatch_detail=dispatch.detail,
    )


def _previous_root_owner_private_domain(
    db: Session,
    *,
    sender_id: str,
    current_trace_id: str,
    current_text: str,
) -> str | None:
    if not sender_id:
        return None
    rows = (
        db.query(AgentRun, ChatInboxMessage)
        .join(ChatInboxMessage, AgentRun.chat_inbox_id == ChatInboxMessage.id)
        .filter(ChatInboxMessage.channel == "dingtalk_private")
        .filter(ChatInboxMessage.sender_external_id == sender_id)
        .filter(AgentRun.agent_code == "factory_dispatch")
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        .limit(20)
        .all()
    )
    for run, inbox in rows:
        if inbox.trace_id == current_trace_id or inbox.text == current_text:
            continue
        source_payload = inbox.source_payload
        if isinstance(source_payload, Mapping) and source_payload.get("root_owner_private_loop") is not True:
            continue
        domain = _recognition_domain_from_run(run)
        if domain:
            return domain
    return None


def _recognition_domain_from_run(run: AgentRun) -> str | None:
    payload = run.result_payload
    if not isinstance(payload, Mapping):
        return None
    recognition = payload.get("recognition")
    if not isinstance(recognition, Mapping):
        return None
    domain = str(recognition.get("domain") or "").strip()
    return domain if domain in _CONTEXT_DOMAINS else None


def _build_natural_answer(*, plan: RootOwnerMessagePlan, decision: EvidenceDecision) -> str:
    trace_id = str(decision.trace.get("trace_id") or "").strip()
    if decision.primary is None:
        missing = "、".join(decision.missing_sources) or "事实源"
        checked_sources = _checked_source_labels(decision)
        return (
            f"{_HERMES_PUBLIC_NAME}回答：{plan.business_date.isoformat()} 暂时没有查到可用正式事实，"
            f"缺少 {missing}，建议先补齐对应来源。"
            f"来源：{checked_sources}。状态：missing。追踪编号：{trace_id}。"
        )
    source_label = _source_label(decision.primary.source_key)
    conflict_text = "；来源有冲突，我已按最高优先级来源采用当前口径" if decision.conflicts else ""
    status = "conflict" if decision.conflicts else str(decision.primary.status or "confirmed")
    return (
        f"{_HERMES_PUBLIC_NAME}回答：按{source_label}读取 {plan.business_date.isoformat()}，"
        f"{decision.primary.summary}{conflict_text}；"
        f"来源：{_source_labels(decision)}。状态：{status}。追踪编号：{trace_id}。"
    )


def _source_label(source_key: str) -> str:
    labels = {
        "dingtalk_group_chat": "钉钉群聊天内容",
        "dingtalk_group_file": "钉钉群文件",
        "mes_readonly": "MES 只读库",
        "data_hub_projection": "数据中枢投影",
    }
    return labels.get(source_key, source_key)


def _source_labels(decision: EvidenceDecision) -> str:
    labels = [_source_label(candidate.source_key) for candidate in decision.candidates]
    return "、".join(dict.fromkeys(label for label in labels if label)) or "未形成可用来源"


def _checked_source_labels(decision: EvidenceDecision) -> str:
    trace = decision.trace if isinstance(decision.trace, Mapping) else {}
    source_status = trace.get("source_status") if isinstance(trace.get("source_status"), Mapping) else {}
    labels = [_source_label(str(source_key)) for source_key in source_status]
    return "已检查" + "、".join(labels) if labels else "未形成可用来源"


def _status_color(decision: EvidenceDecision) -> str:
    if decision.primary is None:
        return "yellow"
    if decision.conflicts:
        return "orange"
    return "green"


def _message_plan_payload(plan: RootOwnerMessagePlan) -> dict[str, Any]:
    return {
        "raw_text": plan.raw_text,
        "normalized_text": plan.normalized_text,
        "business_date": plan.business_date.isoformat(),
        "domain": plan.domain,
        "intent": plan.intent,
        "metric_keys": list(plan.metric_keys),
        "confidence": plan.confidence,
        "needs_clarification": plan.needs_clarification,
        "clarification_question": plan.clarification_question,
        "recognition_reason": plan.recognition_reason,
    }


def _source_payload_block(
    *,
    plan: RootOwnerMessagePlan,
    source_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "source": "dingtalk_inbound",
        "root_owner_private_loop": True,
        "recognition_reason": plan.recognition_reason,
        "source_payload": filter_sensitive_mapping(source_payload or {}),
    }


def _evidence_payload(decision: EvidenceDecision) -> dict[str, Any]:
    return {
        "primary_source": decision.primary.source_key if decision.primary else None,
        "candidate_sources": [candidate.source_key for candidate in decision.candidates],
        "conflicts": list(decision.conflicts),
        "missing_sources": list(decision.missing_sources),
        "trace": filter_sensitive_mapping(decision.trace),
    }
