"""报告 Agent。

职责：
- 在日报已形成后完成自动触达和留痕
- 面向管理层输出简洁经营摘要

非职责：
- 不推送旧式整张人工汇总表截图
- 不承担“先人工整理，再逐个复制发送”的中间层工作
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.config import settings
from app.core.event_bus import publish as publish_realtime_event
from app.core.workflow_events import attach_workflow_event, build_workflow_event
from app.models.reports import DailyReport
from app.models.system import User
from app.services import app_connection_service
from app.services import dingtalk_service
from app.services import leader_summary_service
from app.services import report_service
from app.services.pilot_observability_service import log_pilot_event


def _resolve_notify_identity(user: User) -> tuple[str, str]:
    dingtalk_user_id = str(getattr(user, "dingtalk_user_id", None) or "").strip()
    if settings.DINGTALK_ENABLED and dingtalk_user_id:
        return "dingtalk", dingtalk_user_id
    fallback = str(getattr(user, "username", None) or getattr(user, "id", "") or "").strip()
    return "system", fallback or "unknown"


def _build_push_key(report: DailyReport) -> str:
    """构建用于避免重复推送的幂等键。"""

    time_point = (
        getattr(report, "published_at", None)
        or getattr(report, "generated_at", None)
        or getattr(report, "updated_at", None)
    )
    if time_point is None:
        return f"report:{report.id}"
    return f"report:{report.id}:{time_point.isoformat()}"


def _build_auto_publish_payload(
    report: DailyReport,
    *,
    published_shift_count: int,
    delivery_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_date = report.report_date.isoformat()
    delivery = delivery_payload or {}
    workflow_event = build_workflow_event(
        event_type="report_published",
        actor_role="system",
        actor_id=None,
        scope_type="workshop" if (delivery.get("delivery_target") == "workshop" or report.workshop_id) else "factory",
        workshop_id=int(delivery.get("delivery_target_key")) if delivery.get("delivery_target") == "workshop" and str(delivery.get("delivery_target_key") or '').isdigit() else report.workshop_id,
        team_id=None,
        shift_id=None,
        entity_type="daily_report",
        entity_id=report.id,
        status=report.status,
        payload={
            "report_date": report_date,
            "report_type": report.report_type,
            "scope": report.generated_scope,
            "published_shift_count": int(published_shift_count),
            "delivery_lane": delivery.get("delivery_lane"),
            "delivery_scope": delivery.get("delivery_scope"),
            "delivery_target": delivery.get("delivery_target") or "management",
            "delivery_target_key": delivery.get("delivery_target_key"),
            "delivery_resolution_status": delivery.get("delivery_resolution_status"),
            "resolved_targets": delivery.get("resolved_targets", []),
        },
    )
    return attach_workflow_event(
        {
            "report_id": report.id,
            "report_date": report_date,
            "report_type": report.report_type,
            "workshop_id": report.workshop_id,
            "scope": report.generated_scope,
            "output_mode": report.output_mode,
            "status": report.status,
            "published_shift_count": int(published_shift_count),
        },
        workflow_event,
    )


class ReporterAgent(BaseAgent):
    """报告Agent：自动推送日报给管理层。"""

    def __init__(self):
        """初始化报告 Agent。"""
        super().__init__("reporter")

    def _send_message(self, user: User, content: str) -> tuple[bool, str]:
        """Send a report notification through DingTalk or local sink."""

        if not settings.AUTO_PUSH_ENABLED:
            self.logger.info("自动推送已关闭，仅记录推送日志。")
            return True, "auto_push_disabled"

        channel, identity = _resolve_notify_identity(user)
        if channel == "dingtalk":
            ok, detail = dingtalk_service.send_work_notification(identity, content)
            if ok:
                return ok, detail
            self.logger.info("[notify] %s | %s", identity, content)
            return True, f"stdout_sink_after_dingtalk_failed:{detail}"

        self.logger.info("[notify] %s | %s", identity, content)
        return True, "stdout_sink"

    def _ensure_auto_publish_workflow(self, *, db: Session, report: DailyReport) -> dict[str, Any]:
        report_data: dict[str, Any] = dict(report.report_data or {})
        push_key = _build_push_key(report)

        if report.published_by is not None:
            report.report_data = report_data
            return report_data

        if report.report_type == "production" and not report_data.get("published_shift_count"):
            published_shift_count = report_service.mark_shift_data_published(
                db,
                target_date=report.report_date,
                scope=report.generated_scope,
                operator=SimpleNamespace(id=None),
            )
            report_data["published_shift_count"] = int(published_shift_count)

        if report_data.get("auto_publish_workflow_key") == push_key:
            report.report_data = report_data
            return report_data

        if not settings.WORKFLOW_ENABLED:
            log_pilot_event(
                "auto_publish_workflow_skipped",
                report_id=report.id,
                report_date=report.report_date.isoformat(),
                reason="WORKFLOW_ENABLED=false",
            )
            report.report_data = report_data
            return report_data

        published_shift_count = int(report_data.get("published_shift_count") or 0)
        delivery_payload = report_service.resolve_report_delivery_payload(db, entity=report)
        report_data["delivery_resolution"] = delivery_payload
        emitted = publish_realtime_event(
            "report_published",
            _build_auto_publish_payload(report, published_shift_count=published_shift_count, delivery_payload=delivery_payload),
        )
        if emitted:
            report_data["auto_publish_workflow_key"] = push_key
            report_data["auto_publish_workflow_at"] = datetime.now(timezone.utc).isoformat()
            log_pilot_event(
                "auto_publish_workflow_completed",
                report_id=report.id,
                report_date=report.report_date.isoformat(),
                published_shift_count=published_shift_count,
            )
        else:
            log_pilot_event(
                "auto_publish_workflow_skipped",
                report_id=report.id,
                report_date=report.report_date.isoformat(),
                reason="event_bus_publish_failed",
            )
        report.report_data = report_data
        return report_data

    def execute(self, *, db: Session, target_date: date) -> list[AgentDecision]:
        """推送日报给管理层。"""

        self._decisions = []
        report = (
            db.query(DailyReport)
            .filter(
                DailyReport.report_date == target_date,
                DailyReport.report_type == "production",
                DailyReport.status == "published",
            )
            .order_by(DailyReport.published_at.desc().nullslast(), DailyReport.id.desc())
            .first()
        )
        if report is None:
            return self._decisions

        report_data = self._ensure_auto_publish_workflow(db=db, report=report)
        push_key = _build_push_key(report)

        quality_gate_status = getattr(report, "quality_gate_status", None)
        if quality_gate_status == "blocked":
            report_data["auto_push_blocked_reason"] = "quality_gate_blocked"
            report.report_data = report_data
            log_pilot_event(
                "auto_push_skipped",
                report_id=report.id,
                report_date=target_date.isoformat(),
                reason="quality_gate_blocked",
                push_key=push_key,
            )
            return self._decisions

        if report_data.get("auto_push_last_key") == push_key:
            log_pilot_event(
                "auto_push_skipped",
                report_id=report.id,
                report_date=target_date.isoformat(),
                reason="duplicate_push_key",
                push_key=push_key,
            )
            return self._decisions

        total_output = float(report_data.get("total_output_weight") or 0.0)
        reporting_rate = float(report_data.get("reporting_rate") or 0.0)
        yield_matrix_lane = dict(report_data.get("yield_matrix_lane") or {})
        matrix_company_total = (
            yield_matrix_lane.get("company_total_yield")
            if yield_matrix_lane.get("quality_status") == "ready"
            else None
        )
        yield_rate = float(matrix_company_total) if matrix_company_total is not None else float(report_data.get("yield_rate") or 0.0)
        attendance_total = int(report_data.get("total_attendance") or 0)
        anomaly_summary = dict(report_data.get("anomaly_summary") or {})
        anomaly_total = int(anomaly_summary.get("total") or 0)
        anomaly_digest = str(anomaly_summary.get("digest") or "未发现关键异常")
        leader_summary = leader_summary_service.build_best_effort_leader_summary(
            report_date=target_date,
            report_data=report_data,
        )
        report_data["leader_summary"] = leader_summary
        summary_text = str(
            leader_summary.get("summary_text")
            or report.final_text_summary
            or report.text_summary
            or "暂无日报摘要。"
        )
        message = (
            f"【生产日报】{target_date.strftime('%Y-%m-%d')}\n"
            f"今日产量：{total_output:.2f} 吨\n"
            f"上报率：{reporting_rate:.2f}%\n"
            f"成材率：{yield_rate:.2f}%\n"
            f"出勤：{attendance_total} 人\n"
            f"异常：{anomaly_total} 条（{anomaly_digest}）\n\n"
            f"{summary_text}"
        )

        leaders = (
            db.query(User)
            .filter(User.is_active.is_(True), User.role.in_(("admin", "manager")))
            .order_by(User.id.asc())
            .all()
        )

        sent_count = 0
        failed_count = 0
        for leader in leaders:
            ok, detail = self._send_message(leader, message)
            if ok:
                sent_count += 1
            else:
                failed_count += 1
            self.record_decision(
                AgentAction.AUTO_PUBLISH,
                "daily_report",
                report.id,
                f"向{leader.name or leader.username}推送日报：{detail}",
                leader_user_id=leader.id,
                report_date=target_date.isoformat(),
                success=ok,
            )

        report_data["auto_push_last_key"] = push_key
        report_data["auto_push_sent_count"] = sent_count
        report_data["auto_push_failed_count"] = failed_count
        report_data["auto_push_last_at"] = datetime.now(timezone.utc).isoformat()
        app_connection_payload = app_connection_service.build_app_connection_payload(
            report=report,
            report_data=report_data,
            leader_summary_text=summary_text,
            summary_source=str(leader_summary.get("summary_source") or "deterministic"),
        )
        report_data["app_connection_delivery"] = app_connection_service.dispatch_app_connection_payload(
            payload=app_connection_payload,
        )
        report.report_data = report_data

        log_pilot_event(
            "auto_push_completed",
            report_id=report.id,
            report_date=target_date.isoformat(),
            push_key=push_key,
            sent_count=sent_count,
            failed_count=failed_count,
            auto_push_enabled=settings.AUTO_PUSH_ENABLED,
        )
        return self._decisions


reporter_agent = ReporterAgent()
