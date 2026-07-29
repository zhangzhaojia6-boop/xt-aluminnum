from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.domain.metric_contracts import DAILY_REPORT_METRIC_CONTRACTS
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.system import User
from app.services import agent_communication_service
from app.services.agent_command_service import read_machine_facts
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.hermes_root_owner_evidence_service import (
    EvidenceCandidate,
    EvidenceDecision,
    collect_root_owner_evidence,
)
from app.services.hermes_root_owner_message_service import (
    RootOwnerMessagePlan,
    understand_root_owner_message,
)
from app.services.hermes_root_owner_reply_channel_service import ensure_root_owner_private_reply_channel
from app.services.machine_fact_gap_service import sync_machine_fact_gap_event


_HERMES_PUBLIC_NAME = "鑫泰铝业智能大脑"
_METRIC_LABELS = {
    "total_output_daily": "全厂总产量",
    "workshop_output_daily": "各车间产量",
    "finished_inbound_daily": "成品入库量",
    "daily_input_weight": "投料量",
    "total_electricity_kwh": "高压总用电量",
    "total_gas_m3": "全厂用气量",
    "electricity_per_ton": "吨电耗",
    "daily_yield_rate": "成品率",
    "cost_per_ton": "吨成本",
    "wip_total": "在制料",
    "remaining_contract_weight": "总余合同量",
    "monthly_total_output": "本月累计产量",
    "annual_total_output": "今年累计产量",
    "anomaly_explanation_daily": "异常说明",
    "dingtalk_specialist_evidence": "专项责任人钉钉证据",
    "source_status": "来源状态",
    "daily_report_readiness": "日报就绪状态",
}
_FACT_SOURCE_LABELS = {
    "manual_workbook": "导入原始工作簿",
    "dingtalk_supplement": "钉钉事实证据",
    "dingtalk_group_content": "钉钉群内容",
    "mes_packaging_output": "MES 只读包装产量",
    "mes_stock_records": "MES/WMS 只读入库记录",
    "mes_wip_total_snapshot": "MES 只读在制快照",
    "root_owner_correction": "负责人确认补录",
    "verified_owner_daily": "责任人扫码补录",
    "external_readonly": "外部只读库",
    "data_hub": "数据中枢投影",
}


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
    chat_inbox: ChatInboxMessage | None = None,
    context_scope_id: str | None = None,
) -> RootOwnerProductionTurnResult:
    clean_trace_id = str(trace_id or "").strip() or uuid4().hex
    clean_text = str(text or "").strip()
    sender_id = str(sender_external_id or getattr(current_user, "dingtalk_user_id", "") or "").strip()
    previous_domain, previous_metric_keys, previous_business_date = _previous_root_owner_private_context(
        db,
        sender_id=sender_id,
        current_trace_id=clean_trace_id,
        current_text=clean_text,
        context_scope_id=str(context_scope_id or "").strip() or None,
    )
    plan = understand_root_owner_message(
        clean_text,
        default_business_date=default_business_date,
        previous_domain=previous_domain,
        previous_metric_keys=previous_metric_keys,
        previous_business_date=previous_business_date,
    )
    source = _source_payload_block(plan=plan, source_payload=source_payload)

    inbox = chat_inbox
    if inbox is None:
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
                    "context_scope_id": str(context_scope_id or "").strip() or None,
                }
            ),
        )
        db.add(inbox)
        db.flush()
    else:
        inbox.source_payload = filter_sensitive_mapping(
            {
                **dict(inbox.source_payload or {}),
                **(source_payload or {}),
                "source": "dingtalk_inbound",
                "root_owner_private_loop": True,
                "recognition_reason": plan.recognition_reason,
                "context_scope_id": str(context_scope_id or "").strip() or None,
            }
        )
        db.add(inbox)

    if plan.needs_clarification:
        decision = EvidenceDecision(primary=None, candidates=(), conflicts=(), missing_sources=[], trace={})
        question = plan.clarification_question or "你想看生产、库存、能耗还是异常？"
        answer = f"{_HERMES_PUBLIC_NAME}需要先确认：{question}"
        status = "clarifying"
    elif plan.domain == "machine":
        machine_facts = read_machine_facts(
            db,
            intent=plan.intent,
            business_date=plan.business_date,
            command_text=plan.normalized_text,
            current_user=current_user,
            mes_reader=mes_reader,
        )
        gap_event = sync_machine_fact_gap_event(
            db,
            business_date=plan.business_date,
            intent=plan.intent,
            machine_filter=machine_facts.get("machine_filter"),
            facts=machine_facts,
            trace_id=clean_trace_id,
        )
        decision = _machine_evidence_decision(
            plan=plan,
            facts=machine_facts,
            gap_event=gap_event,
            trace_id=clean_trace_id,
        )
        answer = _build_machine_answer(
            plan=plan,
            facts=machine_facts,
            gap_event=gap_event,
            trace_id=clean_trace_id,
        )
        status = "answered"
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
        source_summary=(
            decision.primary.source_key
            if decision.primary
            else ("machine_fact_gap" if plan.domain == "machine" else "clarification")
        ),
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


def _previous_root_owner_private_context(
    db: Session,
    *,
    sender_id: str,
    current_trace_id: str,
    current_text: str,
    context_scope_id: str | None,
) -> tuple[str | None, tuple[str, ...], date | None]:
    if not sender_id:
        return None, (), None
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
        if context_scope_id is not None and (
            not isinstance(source_payload, Mapping)
            or str(source_payload.get("context_scope_id") or "").strip() != context_scope_id
        ):
            continue
        context = _recognition_context_from_run(run)
        if context is not None:
            return context
    return None, (), None


def _recognition_context_from_run(run: AgentRun) -> tuple[str, tuple[str, ...], date | None] | None:
    payload = run.result_payload
    if not isinstance(payload, Mapping):
        return None
    recognition = payload.get("recognition")
    if not isinstance(recognition, Mapping):
        return None
    domain = str(recognition.get("domain") or "").strip()
    if not domain or domain == "general":
        return None
    raw_metric_keys = recognition.get("metric_keys")
    metric_keys = (
        tuple(str(item).strip() for item in raw_metric_keys if str(item).strip())
        if isinstance(raw_metric_keys, (list, tuple))
        else ()
    )
    raw_business_date = str(recognition.get("business_date") or "").strip()
    try:
        business_date = date.fromisoformat(raw_business_date) if raw_business_date else None
    except ValueError:
        business_date = None
    return domain, metric_keys, business_date


def _machine_evidence_decision(
    *,
    plan: RootOwnerMessagePlan,
    facts: Mapping[str, Any],
    gap_event: Any,
    trace_id: str,
) -> EvidenceDecision:
    fact_count = int(
        (
            facts.get("record_count")
            if plan.intent == "machine_operation"
            else facts.get("stop_count")
        )
        or 0
    )
    fact_status = str(facts.get("fact_status") or ("confirmed" if fact_count > 0 else "missing"))
    is_confirmed = fact_status == "confirmed"
    source_key = "mes_readonly" if facts.get("data_source") == "mes_readonly" else "data_hub_projection"
    candidate = (
        EvidenceCandidate(
            source_key=source_key,
            source_type="external_readonly" if source_key == "mes_readonly" else "data_hub",
            domain="machine",
            priority=20 if source_key == "mes_readonly" else 40,
            status=fact_status,
            value=dict(facts),
            summary=f"{plan.business_date.isoformat()} 机器事实 {fact_count} 条",
            trace_ref={
                "trace_id": trace_id,
                "event_id": getattr(gap_event, "id", None),
            },
        )
        if fact_count > 0
        else None
    )
    return EvidenceDecision(
        primary=candidate if is_confirmed else None,
        candidates=(candidate,) if candidate is not None else (),
        conflicts=(),
        missing_sources=[] if is_confirmed else [source_key],
        trace={
            "trace_id": trace_id,
            "source_status": {
                source_key: {
                    "status": "ok" if is_confirmed else fact_status,
                    "fact_count": fact_count,
                }
            },
            "machine_fact_gap": {
                "event_id": getattr(gap_event, "id", None),
                "status": getattr(gap_event, "status", None),
                "action_route": (
                    (getattr(gap_event, "payload", None) or {}).get("action_route")
                ),
            },
        },
    )


def _build_machine_answer(
    *,
    plan: RootOwnerMessagePlan,
    facts: Mapping[str, Any],
    gap_event: Any,
    trace_id: str,
) -> str:
    machine_label = (
        f"{facts.get('machine_filter')}号机"
        if facts.get("machine_filter")
        else "相关机器"
    )
    if plan.intent == "machine_operation":
        operations = [
            item
            for item in facts.get("top_operations") or []
            if isinstance(item, Mapping)
        ]
        if not operations:
            return (
                f"{_HERMES_PUBLIC_NAME}回答：{plan.business_date.isoformat()} 暂未查到"
                f"{machine_label}可证明的 MES 生产起止记录。"
                "这不代表机器没有运行，也不能当作物理通断电结论；"
                "我已在异常中心生成来源复查任务。"
                f"状态：missing。追踪编号：{trace_id}。"
            )
        if facts.get("fact_status") != "confirmed":
            details = "；".join(_format_machine_operation(item) for item in operations)
            return (
                f"{_HERMES_PUBLIC_NAME}回答：{plan.business_date.isoformat()} 查到"
                f"{machine_label}工序记录，但生产起止时间不完整：{details}。"
                "这些记录不足以证明完整开停明细，也不等同于物理通断电；"
                "我已在异常中心生成 MES 来源复查任务。"
                f"状态：partial。追踪编号：{trace_id}。"
            )
        details = "；".join(_format_machine_operation(item) for item in operations)
        return (
            f"{_HERMES_PUBLIC_NAME}回答：{plan.business_date.isoformat()} {details}。"
            "以上是 MES 工序生产起止记录，不等同于设备物理开关机或通断电。"
            f"来源：{_machine_source_labels(facts)}。状态：confirmed。追踪编号：{trace_id}。"
        )

    stops = [
        item
        for item in facts.get("top_stops") or []
        if isinstance(item, Mapping)
    ]
    if not stops:
        action_route = str(
            (getattr(gap_event, "payload", None) or {}).get("action_route")
            or "/entry/fill"
        )
        return (
            f"{_HERMES_PUBLIC_NAME}回答：{plan.business_date.isoformat()} 暂未查到"
            f"{machine_label}可信的停机时长和原因。"
            f"我已生成大修内勤补录任务：{action_route}。"
            f"状态：missing。追踪编号：{trace_id}。"
        )
    if facts.get("fact_status") != "confirmed":
        action_route = str(
            (getattr(gap_event, "payload", None) or {}).get("action_route")
            or "/entry/fill"
        )
        details = "；".join(_format_machine_stop(item) for item in stops)
        return (
            f"{_HERMES_PUBLIC_NAME}回答：{plan.business_date.isoformat()} 已查到部分停机记录："
            f"{details}。停机原因仍不完整，我已生成大修内勤补录任务：{action_route}。"
            f"状态：partial。追踪编号：{trace_id}。"
        )
    details = "；".join(_format_machine_stop(item) for item in stops)
    return (
        f"{_HERMES_PUBLIC_NAME}回答：{plan.business_date.isoformat()} {details}。"
        f"来源：{_machine_source_labels(facts)}。状态：confirmed。追踪编号：{trace_id}。"
    )


def _format_machine_operation(item: Mapping[str, Any]) -> str:
    device = str(item.get("device_name") or "未标记机台")
    begin_at = _format_machine_time(item.get("begin_at"))
    end_at = _format_machine_time(item.get("end_at"))
    elapsed = item.get("elapsed_minutes")
    elapsed_text = f"，历时 {elapsed} 分钟" if elapsed is not None else ""
    workshop = str(item.get("workshop_name") or "未标记车间")
    process = str(item.get("process_name") or "未标记工序")
    return f"{device} {begin_at} 至 {end_at}{elapsed_text}（{workshop}/{process}）"


def _format_machine_stop(item: Mapping[str, Any]) -> str:
    device = str(item.get("equipment_name") or "未标记机台")
    minutes = int(item.get("downtime_minutes") or 0)
    reason = str(item.get("downtime_reason") or "未填写原因")
    shift = str(item.get("shift_name") or "未标记班次")
    return f"{device}停机 {minutes} 分钟，原因：{reason}（{shift}）"


def _format_machine_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "时间缺失"
    try:
        return datetime.fromisoformat(text).strftime("%H:%M")
    except ValueError:
        return text


def _machine_source_labels(facts: Mapping[str, Any]) -> str:
    if facts.get("data_source") == "mes_readonly":
        return "MES 只读库"
    sources = {
        str(item.get("data_source") or "")
        for key in ("top_operations", "top_stops")
        for item in facts.get(key) or []
        if isinstance(item, Mapping)
    }
    labels = []
    if any("owner_daily_machine_stop" in source for source in sources):
        labels.append("责任人扫码补录")
    if any(source.replace("owner_daily_machine_stop", "").strip("+") for source in sources):
        labels.append("数据中枢投影")
    return "、".join(labels) or "数据中枢投影"


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
    fact_text = _render_selected_facts(plan=plan, decision=decision) or decision.primary.summary
    return (
        f"{_HERMES_PUBLIC_NAME}回答：按{source_label}读取 {plan.business_date.isoformat()}，"
        f"{fact_text}{conflict_text}；"
        f"来源：{_source_labels(decision)}。状态：{status}。追踪编号：{trace_id}。"
    )


def _render_selected_facts(*, plan: RootOwnerMessagePlan, decision: EvidenceDecision) -> str:
    candidates = decision.candidates or ((decision.primary,) if decision.primary is not None else ())
    rendered: list[str] = []
    for field_name in plan.metric_keys:
        for candidate in candidates:
            fact = _candidate_field_fact(candidate, field_name)
            if fact is None:
                continue
            value, unit, fact_source, source_trace_id = fact
            value_text = _format_fact_value(value)
            if not value_text:
                continue
            label = _METRIC_LABELS.get(field_name, field_name)
            unit_text = f" {unit}" if unit else ""
            source_text = _FACT_SOURCE_LABELS.get(fact_source) or _source_label(candidate.source_key)
            details = [f"事实来源：{source_text}"] if source_text else []
            if source_trace_id:
                details.append(f"事实追踪：{source_trace_id}")
            detail_text = f"（{'；'.join(details)}）" if details else ""
            rendered.append(f"{label}：{value_text}{unit_text}{detail_text}")
            break
    return "；".join(rendered)


def _candidate_field_fact(
    candidate: EvidenceCandidate,
    field_name: str,
) -> tuple[Any, str | None, str, str | None] | None:
    value = candidate.value
    if not isinstance(value, Mapping):
        return None
    if field_name in value:
        raw_fact = value[field_name]
    elif value.get("metric_key") == field_name and "value" in value:
        raw_fact = value
    else:
        return None
    field_fact = raw_fact if isinstance(raw_fact, Mapping) and "value" in raw_fact else {}
    fact_value = field_fact.get("value") if field_fact else raw_fact
    if fact_value in (None, ""):
        return None
    contract = DAILY_REPORT_METRIC_CONTRACTS.get(field_name)
    unit = str(field_fact.get("unit") or (contract.unit if contract else "") or "").strip() or None
    source_ref = field_fact.get("source_ref") if isinstance(field_fact.get("source_ref"), Mapping) else {}
    fact_source = str(field_fact.get("source_type") or candidate.source_type or "").strip()
    source_trace_id = str(
        field_fact.get("trace_id")
        or field_fact.get("source_trace_id")
        or source_ref.get("trace_id")
        or candidate.trace_ref.get("trace_id")
        or ""
    ).strip() or None
    return fact_value, unit, fact_source, source_trace_id


def _format_fact_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key, item in value.items():
            item_text = _format_fact_value(item)
            if item_text:
                parts.append(f"{_METRIC_LABELS.get(str(key), str(key))} {item_text}")
        return "、".join(parts)
    if isinstance(value, (list, tuple)):
        return "、".join(text for item in value if (text := _format_fact_value(item)))
    return str(value).strip()


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
    primary = decision.primary
    primary_payload = (
        filter_sensitive_mapping(
            {
                "source_key": primary.source_key,
                "source_type": primary.source_type,
                "status": primary.status,
                "value": primary.value,
                "trace_ref": dict(primary.trace_ref),
            }
        )
        if primary is not None
        else None
    )
    return {
        "primary_source": primary.source_key if primary else None,
        "primary": primary_payload,
        "candidate_facts": [
            filter_sensitive_mapping(
                {
                    "source_key": candidate.source_key,
                    "source_type": candidate.source_type,
                    "status": candidate.status,
                    "value": candidate.value,
                    "trace_ref": dict(candidate.trace_ref),
                }
            )
            for candidate in decision.candidates
        ],
        "candidate_sources": [candidate.source_key for candidate in decision.candidates],
        "conflicts": list(decision.conflicts),
        "missing_sources": list(decision.missing_sources),
        "trace": filter_sensitive_mapping(decision.trace),
    }
