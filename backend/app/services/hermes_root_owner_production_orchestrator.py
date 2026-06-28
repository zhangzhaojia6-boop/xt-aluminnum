from __future__ import annotations

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
    plan = understand_root_owner_message(clean_text, default_business_date=default_business_date)
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
        answer = plan.clarification_question or "你想看生产、库存、能耗还是异常？"
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
        title="Hermes root_owner 私聊回复",
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


def _build_natural_answer(*, plan: RootOwnerMessagePlan, decision: EvidenceDecision) -> str:
    if decision.primary is None:
        missing = "、".join(decision.missing_sources) or "事实源"
        return (
            f"{plan.business_date.isoformat()} 这条问题我没有查到可用事实，缺少 {missing}；"
            "我已记录 trace，建议先补齐对应来源。"
        )
    source_label = _source_label(decision.primary.source_key)
    conflict_text = "；来源有冲突，我已按最高优先级来源采用当前口径" if decision.conflicts else ""
    return (
        f"{plan.business_date.isoformat()} 我按{source_label}回答：{decision.primary.summary}"
        f"{conflict_text}；trace_id 会记录本次采用来源、未采用来源和缺失来源。"
    )


def _source_label(source_key: str) -> str:
    labels = {
        "dingtalk_group_chat": "钉钉群聊天内容",
        "dingtalk_group_file": "钉钉群文件",
        "mes_readonly": "MES 只读库",
        "data_hub_projection": "数据中枢投影",
    }
    return labels.get(source_key, source_key)


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
