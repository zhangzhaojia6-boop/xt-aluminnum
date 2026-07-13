from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.adapters import get_mes_adapter, set_mes_adapter
from app.adapters.factory import create_mes_adapter
from app.adapters.mes_adapter import NullMesAdapter
from app.models.agent_communication import AgentRun, AgentOutboxMessage, ExternalMessageLog
from app.models.system import User
from app.services import agent_communication_service
from app.services.hermes_20_question_acceptance import (
    AcceptanceSummary,
    AcceptanceTurnSnapshot,
    build_20_question_catalog,
    evaluate_acceptance_summary,
)
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.hermes_root_owner_production_orchestrator import run_root_owner_production_turn

_ALLOWED_DELIVERY_CHANNEL_TYPES = frozenset(
    {"dingtalk_group", "dingtalk_work_notice", "dingtalk_custom_robot"}
)


@dataclass(frozen=True, slots=True)
class DingTalkDeliveryTarget:
    channel_type: str
    channel_key: str


@dataclass(frozen=True, slots=True)
class Hermes20QuestionRunOutcome:
    snapshots: tuple[AcceptanceTurnSnapshot, ...]
    summary: AcceptanceSummary


def run_20_question_acceptance(
    db: Session,
    *,
    current_user: User,
    sender_external_id: str,
    business_date: date,
    source_health: dict[str, Any] | None = None,
    required_source_health: tuple[str, ...] = (),
    delivery_targets: Sequence[DingTalkDeliveryTarget] = (),
    limit: int | None = None,
) -> Hermes20QuestionRunOutcome:
    questions = build_20_question_catalog()
    if limit is not None:
        questions = questions[: max(1, int(limit))]
    snapshots: list[AcceptanceTurnSnapshot] = []
    mes_reader = _build_mes_reader()
    for question in questions:
        trace_id = f"hermes-20q-{business_date.isoformat()}-{question.question_id:02d}"
        result = run_root_owner_production_turn(
            db,
            text=question.question,
            current_user=current_user,
            sender_external_id=sender_external_id,
            trace_id=trace_id,
            source_payload={"source": "hermes_20_question_acceptance", "question_id": question.question_id},
            default_business_date=business_date,
            mes_reader=mes_reader,
        )
        target_results = _dispatch_approved_targets(
            db,
            answer=result.answer,
            business_date=business_date,
            trace_id=result.trace_id,
            question_id=question.question_id,
            targets=delivery_targets,
        )
        snapshots.append(
            build_snapshot_from_turn(
                db,
                question_id=question.question_id,
                trace_id=result.trace_id,
                status=result.status,
                answer=result.answer,
                outbox_message_id=result.outbox_message_id,
                source_health=source_health or {},
                required_source_health=required_source_health,
                target_results=target_results,
            )
        )
    return Hermes20QuestionRunOutcome(
        snapshots=tuple(snapshots),
        summary=evaluate_acceptance_summary(snapshots),
    )


def _build_mes_reader() -> HermesMesReadService | None:
    adapter = get_mes_adapter()
    if isinstance(adapter, NullMesAdapter):
        try:
            adapter = create_mes_adapter()
            set_mes_adapter(adapter)
        except Exception:  # noqa: BLE001
            return None
    return HermesMesReadService(adapter)


def build_snapshot_from_turn(
    db: Session,
    *,
    question_id: int,
    trace_id: str,
    status: str,
    answer: str,
    outbox_message_id: int | None,
    source_health: dict[str, Any],
    required_source_health: tuple[str, ...],
    target_results: list[dict[str, Any]] | None = None,
) -> AcceptanceTurnSnapshot:
    run = (
        db.query(AgentRun)
        .filter(AgentRun.trace_id == trace_id)
        .order_by(AgentRun.id.desc())
        .first()
    )
    payload = run.result_payload if run is not None and isinstance(run.result_payload, dict) else {}
    recognition = dict(payload.get("recognition") or {})
    evidence = dict(payload.get("evidence") or {})
    dispatch = _dispatch_payload(db, outbox_message_id, target_results=target_results or [])
    return AcceptanceTurnSnapshot(
        question_id=question_id,
        trace_id=trace_id,
        status=status,
        answer=answer,
        recognition=recognition,
        evidence=evidence,
        dispatch=dispatch,
        source_health=source_health,
        required_source_health=tuple(required_source_health or ()),
        fact_answer=_build_fact_answer(
            question_id=question_id,
            turn_trace_id=trace_id,
            recognition=recognition,
            evidence=evidence,
        ),
    )


def _build_fact_answer(
    *,
    question_id: int,
    turn_trace_id: str,
    recognition: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metric_keys = _string_list(recognition.get("metric_keys"))
    primary_value = evidence.get("primary")
    primary = primary_value if isinstance(primary_value, Mapping) else {}
    source = str(primary.get("source_key") or evidence.get("primary_source") or "").strip()
    primary_status = str(primary.get("status") or "").strip().lower()
    trace_value = evidence.get("trace")
    evidence_trace = trace_value if isinstance(trace_value, Mapping) else {}
    source_trace_id, fact_trace_id = _fact_trace_ids(
        primary=primary,
        evidence_trace=evidence_trace,
        source=source,
        turn_trace_id=turn_trace_id,
    )
    records: list[dict[str, Any]] = []
    for field_name in metric_keys:
        value, unit, has_value = _primary_field_value(primary.get("value"), field_name)
        conflict = _conflict_for_field(evidence.get("conflicts"), field_name)
        if not has_value:
            status = "missing"
        elif conflict is not None:
            status = "conflict"
        elif primary_status in {"ok", "ready", "confirmed", "passed"}:
            status = "confirmed"
        else:
            status = primary_status or "missing"
        reason = _fact_reason(
            status=status,
            conflict=conflict,
            missing_sources=evidence.get("missing_sources"),
        )
        records.append(
            {
                "question_id": question_id,
                "field": field_name,
                "status": status,
                "value": value if has_value else None,
                "source": source if has_value else None,
                "business_date": recognition.get("business_date") or recognition.get("business_window"),
                "unit": unit,
                "trace_id": fact_trace_id if has_value else None,
                "source_trace_id": source_trace_id if has_value else None,
                "reason": reason,
                "action": _fact_action(recognition, evidence, evidence_trace, field_name),
            }
        )
    return records


def _primary_field_value(value: Any, field_name: str) -> tuple[Any, str | None, bool]:
    if not isinstance(value, Mapping):
        return None, None, False
    if field_name in value:
        field_value = value[field_name]
        if isinstance(field_value, Mapping) and "value" in field_value:
            raw_value = field_value.get("value")
            return raw_value, str(field_value.get("unit") or "").strip() or None, raw_value is not None and raw_value != ""
        return field_value, None, field_value is not None and field_value != ""
    if value.get("metric_key") == field_name and "value" in value:
        raw_value = value.get("value")
        return raw_value, str(value.get("unit") or "").strip() or None, raw_value is not None and raw_value != ""
    return None, None, False


def _fact_trace_ids(
    *,
    primary: Mapping[str, Any],
    evidence_trace: Mapping[str, Any],
    source: str,
    turn_trace_id: str,
) -> tuple[str | None, str | None]:
    trace_ref_value = primary.get("trace_ref")
    trace_ref = trace_ref_value if isinstance(trace_ref_value, Mapping) else {}
    source_trace_id = str(trace_ref.get("source_trace_id") or "").strip() or None
    if source_trace_id:
        return source_trace_id, source_trace_id
    primary_trace_id = str(trace_ref.get("trace_id") or "").strip() or None
    if primary_trace_id:
        return None, primary_trace_id
    source_order = _string_list(evidence_trace.get("source_order"))
    if source and source in source_order and primary:
        fallback = str(evidence_trace.get("trace_id") or turn_trace_id or "").strip() or None
        return None, fallback
    return None, None


def _conflict_for_field(value: Any, field_name: str) -> Mapping[str, Any] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    for conflict in value:
        if not isinstance(conflict, Mapping):
            continue
        conflict_field = str(conflict.get("field") or conflict.get("metric_key") or "").strip()
        if not conflict_field or conflict_field == field_name:
            return conflict
    return None


def _fact_reason(
    *,
    status: str,
    conflict: Mapping[str, Any] | None,
    missing_sources: Any,
) -> str | None:
    if status == "conflict" and conflict is not None:
        return str(conflict.get("reason") or "").strip() or None
    if status != "missing":
        return None
    missing = _string_list(missing_sources)
    return f"missing_sources:{','.join(missing)}" if missing else None


def _fact_action(
    recognition: Mapping[str, Any],
    evidence: Mapping[str, Any],
    evidence_trace: Mapping[str, Any],
    field_name: str,
) -> str | None:
    containers: list[Any] = []
    for payload in (evidence, evidence_trace):
        for key in ("actions", "pending_actions", "follow_up_actions"):
            containers.append(payload.get(key))
        gap_plan = payload.get("gap_plan")
        if isinstance(gap_plan, Mapping):
            containers.append(gap_plan.get("items"))
    fallback: str | None = None
    for container in containers:
        items = [container] if isinstance(container, Mapping) else container
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
            continue
        for item in items:
            if not isinstance(item, Mapping):
                continue
            action = str(item.get("next_step") or item.get("action") or "").strip()
            if not action:
                continue
            item_field = str(item.get("field") or item.get("metric_key") or "").strip()
            if item_field == field_name:
                return action
            fallback = fallback or action
    if fallback:
        return fallback
    if recognition.get("needs_clarification"):
        return str(recognition.get("clarification_question") or "").strip() or None
    return None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    return [str(value)]


def _dispatch_approved_targets(
    db: Session,
    *,
    answer: str,
    business_date: date,
    trace_id: str,
    question_id: int,
    targets: Sequence[DingTalkDeliveryTarget],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not targets:
        return results
    for target in targets:
        _validate_delivery_target(target)
    agent = agent_communication_service.register_agent(
        db,
        code="hermes_20_question_acceptance",
        name="鑫泰铝业智能大脑",
        agent_type="acceptance",
        scope_type="factory",
        config_payload={"managed_by": "hermes_20_question_acceptance"},
    )
    for target in targets:
        try:
            channel = agent_communication_service.register_channel(
                db,
                channel_type=target.channel_type,
                channel_key=target.channel_key,
                name=f"20问验收-{target.channel_type}",
                target_type="acceptance_test",
                target_key=_delivery_target_key(target),
                dry_run=False,
                metadata_payload={"managed_by": "hermes_20_question_acceptance"},
            )
            agent_communication_service.bind_agent_to_channel(
                db,
                agent_code=agent.code,
                channel_key=channel.channel_key,
                channel_type=channel.channel_type,
                min_severity="info",
            )
            message = agent_communication_service.queue_bound_message(
                db,
                agent_code=agent.code,
                channel_key=channel.channel_key,
                channel_type=channel.channel_type,
                title="鑫泰铝业智能大脑 20问验收",
                content=answer,
                business_date=business_date,
                source_summary=f"question_{question_id}",
                trace_id=trace_id,
                payload={"question_id": question_id, "acceptance_target": True},
                dedupe_key=_delivery_dedupe_key(trace_id, channel_type=channel.channel_type, channel_key=channel.channel_key),
            )
            outcome = agent_communication_service.dispatch_outbox_message(db, message.id)
            logs = agent_communication_service.list_external_logs(db, outbox_message_id=message.id)
            latest_log = logs[-1] if logs else None
            results.append(
                {
                    "status": outcome.status,
                    "detail": outcome.detail,
                    "outbox_message_id": outcome.outbox_message_id,
                    "log_status": latest_log.status if latest_log is not None else "",
                    "channel_type": channel.channel_type,
                    "channel_key": channel.channel_key,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "status": "retrying",
                    "detail": f"{type(exc).__name__}: {exc}",
                    "outbox_message_id": None,
                    "log_status": "",
                    "channel_type": target.channel_type,
                    "channel_key": target.channel_key,
                }
            )
    return results


def _validate_delivery_target(target: DingTalkDeliveryTarget) -> None:
    if target.channel_type not in _ALLOWED_DELIVERY_CHANNEL_TYPES:
        raise ValueError(f"unsupported delivery target channel_type: {target.channel_type}")


def _delivery_target_key(target: DingTalkDeliveryTarget) -> str:
    if target.channel_type == "dingtalk_work_notice":
        return target.channel_key
    return "hermes_20_question_acceptance"


def _delivery_dedupe_key(trace_id: str, *, channel_type: str, channel_key: str) -> str:
    digest = hashlib.sha256(f"{channel_type}:{channel_key}".encode("utf-8")).hexdigest()[:16]
    return f"{trace_id}:{channel_type}:{digest}"


def _dispatch_payload(
    db: Session,
    outbox_message_id: int | None,
    *,
    target_results: list[dict[str, Any]],
) -> dict[str, Any]:
    if not outbox_message_id:
        base = {"status": "missing", "detail": "outbox_message_missing"}
        return _aggregate_dispatch_payload(base, target_results)
    message = db.get(AgentOutboxMessage, int(outbox_message_id))
    log = (
        db.query(ExternalMessageLog)
        .filter(ExternalMessageLog.outbox_message_id == int(outbox_message_id))
        .order_by(ExternalMessageLog.id.desc())
        .first()
    )
    base = {
        "status": message.status if message is not None else "missing",
        "detail": (log.detail if log is not None else None) or (message.last_error if message is not None else None) or "",
        "outbox_message_id": outbox_message_id,
        "log_status": log.status if log is not None else "",
        "channel_type": log.channel_type if log is not None else "",
        "channel_key": log.channel_key if log is not None else "",
    }
    return _aggregate_dispatch_payload(base, target_results)


def _aggregate_dispatch_payload(base: dict[str, Any], target_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not target_results:
        return base
    all_results = [base, *target_results]
    sent_count = sum(1 for item in all_results if item.get("status") == "sent")
    failed = [item for item in all_results if item.get("status") != "sent"]
    if not failed:
        status = "sent"
        detail = "all_targets_sent"
    else:
        status = str(failed[0].get("status") or "retrying")
        detail = "; ".join(str(item.get("detail") or item.get("status") or "delivery_failed") for item in failed)
    return {
        **base,
        "status": status,
        "detail": detail,
        "log_status": status,
        "target_results": target_results,
        "delivery_sent_count": sent_count,
        "delivery_target_count": len(all_results),
    }
