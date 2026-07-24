from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.daily_report_field_contract import DAILY_REPORT_FIELD_CONTRACT_VERSION
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentEvent,
    AgentOutboxMessage,
    AgentProfile,
    CommunicationChannel,
)
from app.models.reports import DailyReport
from app.services import agent_communication_service
from app.services.report.template_daily_report import REQUIRED_FIELDS

AGENT_CODE = "daily_report_secretary"
CHANNEL_TYPE = "dingtalk_work_notice"
REFERENCE_SOURCE_TYPES = {
    "datahub_final_daily_report",
    "official_daily_report",
    "output_skill",
    "output_skill_daily_report",
}
DEDUP_WINDOW_MINUTES = 60 * 24 * 730
REQUIRED_FACT_FIELDS = tuple(field for field in REQUIRED_FIELDS if field != "report_date")


def deliver_completed_daily_report(db: Session, *, target_date: date) -> dict[str, Any]:
    report = _latest_report(db, target_date=target_date)
    if report is None:
        return {"status": "skipped", "reason": "daily_report_not_found"}

    template_payload = _template_payload(report)
    readiness = _delivery_readiness(report, template_payload=template_payload)
    if readiness is not None:
        return _record_delivery_result(db, report, readiness)

    recipient_name = str(settings.DAILY_REPORT_DINGTALK_RECIPIENT_NAME or "").strip()
    recipient_user_id = str(settings.DAILY_REPORT_DINGTALK_RECIPIENT_USER_ID or "").strip()
    if not recipient_name:
        return _record_delivery_result(
            db,
            report,
            {"status": "blocked_recipient", "reason": "recipient_name_missing"},
        )
    if not recipient_user_id:
        return _record_delivery_result(
            db,
            report,
            {"status": "blocked_recipient", "reason": "recipient_user_id_missing"},
        )
    if not settings.AUTO_PUSH_ENABLED:
        return _record_delivery_result(
            db,
            report,
            {"status": "disabled", "reason": "auto_push_disabled"},
        )
    if not settings.DINGTALK_ENABLED:
        return _record_delivery_result(
            db,
            report,
            {"status": "disabled", "reason": "dingtalk_disabled"},
        )

    agent, channel = _ensure_delivery_infrastructure(
        db,
        recipient_name=recipient_name,
        recipient_user_id=recipient_user_id,
    )
    dedupe_key = f"daily-report:{target_date.isoformat()}:{recipient_user_id}"
    existing = (
        db.query(AgentOutboxMessage)
        .filter(
            AgentOutboxMessage.agent_profile_id == agent.id,
            AgentOutboxMessage.channel_id == channel.id,
            AgentOutboxMessage.dedupe_key == dedupe_key,
        )
        .order_by(AgentOutboxMessage.id.desc())
        .first()
    )
    if existing is not None:
        result = {
            "status": existing.status,
            "outbox_message_id": existing.id,
            "duplicate": True,
        }
        return _record_delivery_result(db, report, result)

    trace_id = f"daily-report:{target_date.isoformat()}:{report.id}"
    event = AgentEvent(
        event_type="daily_report_ready",
        severity="info",
        status="queued",
        scope_type="factory",
        source_type="daily_report",
        source_ref=str(report.id),
        business_date=target_date,
        payload={
            "trace_id": trace_id,
            "recipient_name": recipient_name,
            "report_id": report.id,
            "field_contract_version": DAILY_REPORT_FIELD_CONTRACT_VERSION,
            "required_fact_count": len(REQUIRED_FACT_FIELDS),
        },
    )
    db.add(event)
    db.flush()

    message = agent_communication_service.queue_bound_message(
        db,
        agent_code=agent.code,
        channel_key=channel.channel_key,
        channel_type=channel.channel_type,
        title=f"{target_date.isoformat()} 鑫泰铝业生产日报",
        content=str(template_payload["text"]).strip(),
        business_date=target_date,
        source_summary="pure_real_source_127_field_report",
        trace_id=trace_id,
        event_id=event.id,
        payload={
            "report_id": report.id,
            "recipient_name": recipient_name,
            "field_contract_version": DAILY_REPORT_FIELD_CONTRACT_VERSION,
            "required_fact_count": len(REQUIRED_FACT_FIELDS),
        },
        dedupe_key=dedupe_key,
        dedupe_window_minutes=DEDUP_WINDOW_MINUTES,
        commit=False,
    )
    _store_delivery_state(
        report,
        {
            "status": "queued",
            "outbox_message_id": message.id,
            "duplicate": False,
        },
    )
    db.flush()

    outcome = agent_communication_service.dispatch_outbox_message(db, message.id)
    event.status = "completed" if outcome.status == "sent" else outcome.status
    event.payload = {
        **dict(event.payload or {}),
        "delivery_status": outcome.status,
        "outbox_message_id": message.id,
    }
    result = {
        "status": outcome.status,
        "outbox_message_id": message.id,
        "duplicate": False,
    }
    return _record_delivery_result(db, report, result)


def _latest_report(db: Session, *, target_date: date) -> DailyReport | None:
    return (
        db.query(DailyReport)
        .filter(
            DailyReport.report_date == target_date,
            DailyReport.report_type == "production",
        )
        .order_by(DailyReport.published_at.desc().nullslast(), DailyReport.id.desc())
        .first()
    )


def _template_payload(report: DailyReport) -> dict[str, Any]:
    report_data = report.report_data if isinstance(report.report_data, dict) else {}
    payload = report_data.get("template_daily_report")
    return dict(payload) if isinstance(payload, dict) else {}


def _delivery_readiness(
    report: DailyReport,
    *,
    template_payload: dict[str, Any],
) -> dict[str, Any] | None:
    missing_fields = [str(item) for item in template_payload.get("missing_fields") or []]
    conflicts = list(template_payload.get("conflicts") or [])
    text = str(template_payload.get("text") or "").strip()
    paragraph_count = len([paragraph for paragraph in text.split("\n\n") if paragraph.strip()])
    if (
        str(template_payload.get("status") or "") != "ready"
        or not report.delivery_ready
        or not text
        or paragraph_count != 5
        or missing_fields
        or conflicts
        or report.quality_gate_status == "blocked"
    ):
        return {
            "status": "blocked_incomplete",
            "missing_fields": missing_fields,
            "conflict_count": len(conflicts),
        }

    sources = template_payload.get("sources")
    source_map = sources if isinstance(sources, dict) else {}
    missing_source_fields = [
        field_name
        for field_name in REQUIRED_FACT_FIELDS
        if not isinstance(source_map.get(field_name), dict)
    ]
    if missing_source_fields:
        return {
            "status": "blocked_missing_sources",
            "missing_source_fields": missing_source_fields,
        }

    reference_fields = []
    for field_name in REQUIRED_FACT_FIELDS:
        source = source_map[field_name]
        source_type = str(source.get("source_type") or source.get("source") or "").strip().lower()
        if source_type in REFERENCE_SOURCE_TYPES or "output_skill" in source_type:
            reference_fields.append(field_name)
    if reference_fields:
        return {
            "status": "blocked_reference_source",
            "reference_fields": sorted(reference_fields),
        }
    return None


def _ensure_delivery_infrastructure(
    db: Session,
    *,
    recipient_name: str,
    recipient_user_id: str,
) -> tuple[AgentProfile, CommunicationChannel]:
    agent = db.query(AgentProfile).filter(AgentProfile.code == AGENT_CODE).one_or_none()
    if agent is None:
        agent = AgentProfile(code=AGENT_CODE, name="鑫泰铝业日报秘书", agent_type="reporting", scope_type="factory")
        db.add(agent)
    agent.name = "鑫泰铝业日报秘书"
    agent.agent_type = "reporting"
    agent.scope_type = "factory"
    agent.is_active = True
    agent.config_payload = {
        "delivery": "daily_report",
        "requires_complete_real_sources": True,
        "field_contract_version": DAILY_REPORT_FIELD_CONTRACT_VERSION,
    }
    db.flush()

    channel_key = f"daily-report-recipient:{recipient_user_id}"
    channel = (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_type == CHANNEL_TYPE,
            CommunicationChannel.channel_key == channel_key,
        )
        .one_or_none()
    )
    if channel is None:
        channel = CommunicationChannel(
            channel_type=CHANNEL_TYPE,
            channel_key=channel_key,
            name=f"{recipient_name}日报工作通知",
            target_type="user",
        )
        db.add(channel)
    channel.name = f"{recipient_name}日报工作通知"
    channel.target_type = "user"
    channel.target_key = recipient_user_id
    channel.dry_run = bool(settings.DINGTALK_NOTIFY_DRY_RUN)
    channel.is_active = True
    channel.metadata_payload = {
        "recipient_name": recipient_name,
        "managed_by": "daily_report_delivery_service",
    }
    db.flush()

    binding = (
        db.query(AgentChannelBinding)
        .filter(
            AgentChannelBinding.agent_profile_id == agent.id,
            AgentChannelBinding.channel_id == channel.id,
        )
        .one_or_none()
    )
    if binding is None:
        binding = AgentChannelBinding(
            agent_profile_id=agent.id,
            channel_id=channel.id,
            min_severity="info",
        )
        db.add(binding)
    binding.is_active = True
    binding.min_severity = "info"
    db.flush()
    return agent, channel


def _store_delivery_state(report: DailyReport, result: dict[str, Any]) -> None:
    report_data = dict(report.report_data or {})
    report_data["scheduled_daily_report_delivery"] = {
        **result,
        "scheduled_at": "10:00",
    }
    report.report_data = report_data


def _record_delivery_result(
    db: Session,
    report: DailyReport,
    result: dict[str, Any],
) -> dict[str, Any]:
    _store_delivery_state(report, result)
    db.commit()
    return result
