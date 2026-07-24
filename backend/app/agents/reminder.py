"""
催报 Agent。

职责：
- 围绕“未报/迟报”做异常闭环
- 在必要时升级给管理员

非职责：
- 不承担日常人工总催收
- 不把正常数据流重新拉回人工汇总渠道
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.config import settings
from app.core.business_time import (
    local_now,
    resolve_owner_daily_business_date,
    resolve_production_business_date,
)
from app.models.attendance import AttendanceSchedule
from app.models.master import Workshop
from app.models.production import MobileReminderRecord, MobileShiftReport
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import dingtalk_service
from app.services.dingtalk_service import (
    record_work_notification_attempt,
    send_detail_text,
)
from app.services.mobile_reminder_service import (
    _owner_daily_candidates,
    _shift_deadline,
)

READY_STATUSES = {"submitted", "approved", "auto_confirmed"}
MOBILE_ROLE_NAMES = {"machine_operator", "energy_stat"}
MAX_DIRECT_REMINDERS = 1
FINISHED_REMINDER_STATUSES = {"acknowledged", "closed"}


def _resolve_notify_identity(user: User) -> tuple[str, str]:
    dingtalk_user_id = str(getattr(user, "dingtalk_user_id", None) or "").strip()
    if settings.DINGTALK_ENABLED and dingtalk_user_id:
        return "dingtalk", dingtalk_user_id
    fallback = str(getattr(user, "username", None) or getattr(user, "id", "") or "").strip()
    return "system", fallback or "unknown"


def _reminder_is_finished(reminder: MobileReminderRecord | None) -> bool:
    if reminder is None:
        return False
    return (
        str(getattr(reminder, "reminder_status", "") or "").strip().lower() in FINISHED_REMINDER_STATUSES
        or getattr(reminder, "acknowledged_at", None) is not None
        or getattr(reminder, "closed_at", None) is not None
    )


def _escalation_was_sent(reminder: MobileReminderRecord | None) -> bool:
    if reminder is None:
        return False
    return (
        str(getattr(reminder, "reminder_status", "") or "").strip().lower() == "sent"
        and getattr(reminder, "last_reminded_at", None) is not None
    )


def _queue_notification(
    batches: dict[str, dict[str, object]],
    *,
    user: User,
    label: str,
) -> None:
    channel, identity = _resolve_notify_identity(user)
    key = f"{channel}:{identity}"
    batch = batches.setdefault(key, {"user": user, "labels": []})
    labels = batch["labels"]
    if isinstance(labels, list) and label not in labels:
        labels.append(label)


def _format_labels(labels: list[str], *, limit: int = 6) -> str:
    visible = labels[:limit]
    text = "、".join(visible)
    remaining = len(labels) - len(visible)
    if remaining > 0:
        text = f"{text}，另{remaining}项"
    return text


def _render_reminder_batch(labels: list[str]) -> str:
    if len(labels) == 1:
        return f"{labels[0]}还没看到数据，方便时从填报端补一下。已经提交的话不用管这条。"
    return (
        f"今天还有{len(labels)}项没看到数据：{_format_labels(labels)}。"
        "方便时从填报端一次补齐，已经提交的不用重复操作。"
    )


def _render_escalation_batch(labels: list[str]) -> str:
    if len(labels) == 1:
        return f"{labels[0]}提醒后仍未补齐，麻烦关注一下。有新进展我再更新。"
    return (
        f"今天有{len(labels)}项提醒后仍未补齐：{_format_labels(labels)}。"
        "麻烦统一看一下；状态没变化我不会重复提醒。"
    )


class ReminderAgent(BaseAgent):
    """催报Agent：自动检测未报班次并催报。"""

    def __init__(self):
        """初始化催报 Agent。"""
        super().__init__("reminder")

    def _send_reminder_message(self, user: User, content: str, *, db: Session | None = None) -> tuple[bool, str]:
        """Send a reminder through DingTalk or local sink."""

        if not settings.AUTO_PUSH_ENABLED:
            self.logger.info("自动推送已关闭，催报消息仅记录：%s", content)
            return True, "auto_push_disabled"

        channel, identity = _resolve_notify_identity(user)
        if channel == "dingtalk":
            ok, detail = dingtalk_service.send_work_notification(identity, content)
            detail_text = (
                record_work_notification_attempt(db, userid=identity, ok=ok, detail=detail)
                if db is not None
                else send_detail_text(detail)
            )
            if ok:
                return ok, detail_text
            self.logger.info("[notify] %s | %s", identity, content)
            return True, f"stdout_sink_after_dingtalk_failed:{detail_text}"

        self.logger.info("[notify] %s | %s", identity, content)
        return True, "stdout_sink"

    def _send_escalation_message(self, user: User, content: str, *, db: Session | None = None) -> tuple[bool, str]:
        """Send an escalation through DingTalk or local sink."""

        if not settings.AUTO_PUSH_ENABLED:
            self.logger.info("自动推送已关闭，升级消息仅记录：%s", content)
            return True, "auto_push_disabled"

        channel, identity = _resolve_notify_identity(user)
        if channel == "dingtalk":
            ok, detail = dingtalk_service.send_work_notification(identity, content)
            detail_text = (
                record_work_notification_attempt(db, userid=identity, ok=ok, detail=detail)
                if db is not None
                else send_detail_text(detail)
            )
            if ok:
                return ok, detail_text
            self.logger.info("[notify] %s | %s", identity, content)
            return True, f"stdout_sink_after_dingtalk_failed:{detail_text}"

        self.logger.info("[notify] %s | %s", identity, content)
        return True, "stdout_sink"

    def _resolve_leader(self, db: Session, *, workshop_id: int, team_id: int | None) -> User | None:
        """按班组优先、车间兜底查找负责人。"""

        base_query = db.query(User).filter(
            User.is_active.is_(True),
            User.workshop_id == workshop_id,
            User.role.in_(tuple(MOBILE_ROLE_NAMES)),
        )
        if team_id is not None:
            leader = (
                base_query.filter(User.team_id == team_id).order_by(User.id.asc()).first()
            )
            if leader is not None:
                return leader
        return base_query.filter(User.team_id.is_(None)).order_by(User.id.asc()).first()

    def _admin_users(self, db: Session) -> list[User]:
        """获取管理员用户列表。"""

        return (
            db.query(User)
            .filter(User.is_active.is_(True), User.role.in_(("admin", "manager")))
            .order_by(User.id.asc())
            .all()
        )

    def execute(self, *, db: Session, target_date: date, shift_config_id: int | None = None) -> list[AgentDecision]:
        """
        检查未提交报告班次并执行催报或升级提醒。

        规则：
        - 同一事项只提醒责任人一次
        - 仍未补齐时只升级管理员一次
        - 同一收件人的多项提醒合并成一条
        - 不提交事务，由调用方控制 commit
        """

        self._decisions = []
        reminder_batches: dict[str, dict[str, object]] = {}
        escalation_batches: dict[str, dict[str, object]] = {}
        schedule_query = (
            db.query(
                AttendanceSchedule.business_date,
                AttendanceSchedule.shift_config_id,
                AttendanceSchedule.workshop_id,
                AttendanceSchedule.team_id,
            )
            .filter(
                AttendanceSchedule.business_date == target_date,
                AttendanceSchedule.workshop_id.is_not(None),
                AttendanceSchedule.shift_config_id.is_not(None),
            )
            .distinct()
        )
        if shift_config_id is not None:
            schedule_query = schedule_query.filter(AttendanceSchedule.shift_config_id == shift_config_id)
        expected_rows = schedule_query.all()

        report_rows = (
            db.query(MobileShiftReport)
            .filter(MobileShiftReport.business_date == target_date)
            .all()
        )
        report_key_set = {
            (row.business_date, row.shift_config_id, row.workshop_id, row.team_id)
            for row in report_rows
            if row.report_status in READY_STATUSES
        }
        workshop_ids = {int(item.workshop_id) for item in expected_rows if item.workshop_id is not None}
        shift_ids = {int(item.shift_config_id) for item in expected_rows if item.shift_config_id is not None}
        workshop_name_map = {
            item.id: item.name for item in db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all()
        } if workshop_ids else {}
        shift_name_map = {
            item.id: (item.name or item.code) for item in db.query(ShiftConfig).filter(ShiftConfig.id.in_(shift_ids)).all()
        } if shift_ids else {}
        shift_map = {
            item.id: item for item in db.query(ShiftConfig).filter(ShiftConfig.id.in_(shift_ids)).all()
        } if shift_ids else {}

        now_local = local_now()
        for item in expected_rows:
            key = (item.business_date, item.shift_config_id, item.workshop_id, item.team_id)
            if key in report_key_set:
                continue

            leader = self._resolve_leader(
                db,
                workshop_id=int(item.workshop_id),
                team_id=int(item.team_id) if item.team_id is not None else None,
            )
            if leader is None:
                continue

            workshop_name = workshop_name_map.get(int(item.workshop_id), f"车间{item.workshop_id}")
            shift_name = shift_name_map.get(int(item.shift_config_id), f"班次{item.shift_config_id}")
            shift_obj = shift_map.get(int(item.shift_config_id))
            reminder_type = "unreported"
            if shift_obj is not None and now_local >= _shift_deadline(
                business_date=item.business_date,
                shift=shift_obj,
                grace_minutes=30,
            ):
                reminder_type = "late_report"

            history_query = db.query(MobileReminderRecord).filter(
                MobileReminderRecord.business_date == item.business_date,
                MobileReminderRecord.shift_config_id == item.shift_config_id,
                MobileReminderRecord.workshop_id == item.workshop_id,
                MobileReminderRecord.team_id == item.team_id,
                MobileReminderRecord.leader_user_id == leader.id,
            )
            type_query = history_query.filter(MobileReminderRecord.reminder_type == reminder_type)
            existing = type_query.first()
            if _reminder_is_finished(existing):
                continue
            reminder_count = max(
                int(history_query.count()),
                int(getattr(existing, "reminder_count", 0) or 0),
            )
            next_count = reminder_count + 1

            if reminder_count < MAX_DIRECT_REMINDERS:
                entity = existing
                if entity is None:
                    entity = MobileReminderRecord(
                        business_date=item.business_date,
                        shift_config_id=item.shift_config_id,
                        workshop_id=item.workshop_id,
                        team_id=item.team_id,
                        leader_user_id=leader.id,
                        reminder_type=reminder_type,
                    )
                    db.add(entity)
                entity.reminder_status = "sent"
                entity.reminder_channel = _resolve_notify_identity(leader)[0]
                entity.reminder_count = next_count
                entity.last_reminded_at = datetime.now(timezone.utc)
                entity.note = None
                label = f"{workshop_name}{shift_name}"
                message = (
                    f"{label}还没看到数据，方便时从填报端补一下。"
                    "已经提交的话不用管这条。"
                )
                _queue_notification(reminder_batches, user=leader, label=label)
                self.record_decision(
                    AgentAction.AUTO_REMIND,
                    "mobile_reminder_record",
                    0,
                    message,
                    workshop_id=item.workshop_id,
                    shift_id=item.shift_config_id,
                    leader_user_id=leader.id,
                    reminder_count=next_count,
                )
                continue

            escalation_query = history_query.filter(MobileReminderRecord.reminder_type == "escalation")
            escalation = escalation_query.first()
            if _reminder_is_finished(escalation) or _escalation_was_sent(escalation):
                continue
            if escalation is None:
                escalation = MobileReminderRecord(
                    business_date=item.business_date,
                    shift_config_id=item.shift_config_id,
                    workshop_id=item.workshop_id,
                    team_id=item.team_id,
                    leader_user_id=leader.id,
                    reminder_type="escalation",
                )
                db.add(escalation)
            escalation.reminder_status = "sent"
            escalation.reminder_channel = _resolve_notify_identity(leader)[0]
            escalation.reminder_count = next_count
            escalation.last_reminded_at = datetime.now(timezone.utc)
            escalation.note = "自动升级提醒管理员"

            admin_users = self._admin_users(db)
            for admin_user in admin_users:
                _queue_notification(
                    escalation_batches,
                    user=admin_user,
                    label=f"{workshop_name}{shift_name}（{leader.name}）",
                )

            self.record_decision(
                AgentAction.AUTO_ALERT,
                "mobile_reminder_record",
                0,
                f"{workshop_name}{shift_name}提醒后仍未补齐，已升级管理员。负责人：{leader.name}",
                workshop_id=item.workshop_id,
                shift_id=item.shift_config_id,
                leader_user_id=leader.id,
                reminder_count=next_count,
            )

        current_business_date = resolve_production_business_date(now_local)
        daily_business_date = (
            resolve_owner_daily_business_date(now_local)
            if target_date == current_business_date
            else target_date
        )
        daily_scope = SimpleNamespace(is_admin=True, data_scope_type="all", workshop_id=None, team_id=None)
        daily_candidates, daily_users = _owner_daily_candidates(
            db,
            business_date=daily_business_date,
            scope_summary=daily_scope,
            now=now_local,
        )
        daily_workshop_ids = {int(item["workshop_id"]) for item in daily_candidates if item.get("workshop_id") is not None}
        daily_workshop_names = {
            item.id: item.name for item in db.query(Workshop).filter(Workshop.id.in_(daily_workshop_ids)).all()
        } if daily_workshop_ids else {}

        for candidate in daily_candidates:
            leader = daily_users.get(int(candidate["leader_user_id"]))
            if leader is None:
                continue

            workshop_name = daily_workshop_names.get(int(candidate["workshop_id"]), f"车间{candidate['workshop_id']}")
            role_label = candidate.get("note") or "每日一填"
            history_query = db.query(MobileReminderRecord).filter(
                MobileReminderRecord.business_date == candidate["business_date"],
                MobileReminderRecord.shift_config_id == candidate["shift_config_id"],
                MobileReminderRecord.workshop_id == candidate["workshop_id"],
                MobileReminderRecord.team_id == candidate["team_id"],
                MobileReminderRecord.leader_user_id == leader.id,
            )
            type_query = history_query.filter(MobileReminderRecord.reminder_type == candidate["reminder_type"])
            existing = type_query.first()
            if _reminder_is_finished(existing):
                continue
            reminder_count = max(
                int(history_query.count()),
                int(getattr(existing, "reminder_count", 0) or 0),
            )
            next_count = reminder_count + 1

            if reminder_count < MAX_DIRECT_REMINDERS:
                entity = existing
                if entity is None:
                    entity = MobileReminderRecord(
                        business_date=candidate["business_date"],
                        shift_config_id=candidate["shift_config_id"],
                        workshop_id=candidate["workshop_id"],
                        team_id=candidate["team_id"],
                        leader_user_id=leader.id,
                        reminder_type=candidate["reminder_type"],
                    )
                    db.add(entity)
                entity.reminder_status = "sent"
                entity.reminder_channel = _resolve_notify_identity(leader)[0]
                entity.reminder_count = next_count
                entity.last_reminded_at = datetime.now(timezone.utc)
                entity.note = role_label
                label = f"{workshop_name}{role_label}"
                message = f"{label}还没看到数据，方便时从填报端补一下。已经提交的话不用管这条。"
                _queue_notification(reminder_batches, user=leader, label=label)
                self.record_decision(
                    AgentAction.AUTO_REMIND,
                    "mobile_reminder_record",
                    0,
                    message,
                    workshop_id=candidate["workshop_id"],
                    shift_id=candidate["shift_config_id"],
                    leader_user_id=leader.id,
                    reminder_count=next_count,
                )
                continue

            escalation_query = history_query.filter(MobileReminderRecord.reminder_type == "daily_escalation")
            escalation = escalation_query.first()
            if _reminder_is_finished(escalation) or _escalation_was_sent(escalation):
                continue
            if escalation is None:
                escalation = MobileReminderRecord(
                    business_date=candidate["business_date"],
                    shift_config_id=candidate["shift_config_id"],
                    workshop_id=candidate["workshop_id"],
                    team_id=candidate["team_id"],
                    leader_user_id=leader.id,
                    reminder_type="daily_escalation",
                )
                db.add(escalation)
            escalation.reminder_status = "sent"
            escalation.reminder_channel = _resolve_notify_identity(leader)[0]
            escalation.reminder_count = next_count
            escalation.last_reminded_at = datetime.now(timezone.utc)
            escalation.note = f"{role_label} 自动升级提醒管理员"

            for admin_user in self._admin_users(db):
                _queue_notification(
                    escalation_batches,
                    user=admin_user,
                    label=f"{workshop_name}{role_label}（{leader.name}）",
                )

            self.record_decision(
                AgentAction.AUTO_ALERT,
                "mobile_reminder_record",
                0,
                f"{workshop_name}{role_label}提醒后仍未补齐，已升级管理员。负责人：{leader.name}",
                workshop_id=candidate["workshop_id"],
                shift_id=candidate["shift_config_id"],
                leader_user_id=leader.id,
                reminder_count=next_count,
            )

        for batch in reminder_batches.values():
            labels = batch.get("labels")
            user = batch.get("user")
            if isinstance(labels, list) and labels and user is not None:
                self._send_reminder_message(user, _render_reminder_batch(labels), db=db)
        for batch in escalation_batches.values():
            labels = batch.get("labels")
            user = batch.get("user")
            if isinstance(labels, list) and labels and user is not None:
                self._send_escalation_message(user, _render_escalation_batch(labels), db=db)

        return self._decisions


reminder_agent = ReminderAgent()
