from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentRun, AgentOutboxMessage, ExternalMessageLog
from app.models.system import User
from app.services import agent_communication_service
from app.services.hermes_20_question_acceptance import (
    AcceptanceSummary,
    AcceptanceTurnSnapshot,
    build_20_question_catalog,
    evaluate_acceptance_summary,
)
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
    dispatch = _dispatch_payload(db, outbox_message_id, target_results=target_results or [])
    return AcceptanceTurnSnapshot(
        question_id=question_id,
        trace_id=trace_id,
        status=status,
        answer=answer,
        recognition=dict(payload.get("recognition") or {}),
        evidence=dict(payload.get("evidence") or {}),
        dispatch=dispatch,
        source_health=source_health,
        required_source_health=tuple(required_source_health or ()),
    )


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
