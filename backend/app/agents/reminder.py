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
from app.models.attendance import AttendanceSchedule
from app.models.master import Workshop
from app.models.production import MobileReminderRecord, MobileShiftReport
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import dingtalk_service
from app.core.business_time import local_now, resolve_owner_daily_business_date, resolve_production_business_date
from app.services.dingtalk_service import record_work_notification_attempt, send_detail_text
from app.services.mobile_reminder_service import _owner_daily_candidates, _shift_deadline

READY_STATUSES = {"submitted", "approved", "auto_confirmed"}
MOBILE_ROLE_NAMES = {"machine_operator", "energy_stat"}


def _resolve_notify_identity(user: User) -> tuple[str, str]:
    dingtalk_user_id = str(getattr(user, "dingtalk_user_id", None) or "").strip()
    if settings.DINGTALK_ENABLED and dingtalk_user_id:
        return "dingtalk", dingtalk_user_id
    fallback = str(getattr(user, "username", None) or getattr(user, "id", "") or "").strip()
    return "system", fallback or "unknown"


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
        - 3 次内发送催报消息
        - 第 3 次后触发升级提醒管理员
        - 不提交事务，由调用方控制 commit
        """

        self._decisions = []
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
            reminder_count = max(
                int(history_query.count()),
                int(getattr(existing, "reminder_count", 0) or 0),
            )
            next_count = reminder_count + 1

            if reminder_count < 3:
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
                message = (
                    f"【催报提醒】{workshop_name} {shift_name} 的生产数据尚未提交，"
                    f"请尽快在钉钉中完成填报。（第{next_count}次提醒）"
                )
                self._send_reminder_message(leader, message)
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
                escalation_message = (
                    f"【催报升级】{workshop_name} {shift_name} 已催报{next_count}次未响应，"
                    f"请管理员关注。负责人：{leader.name}"
                )
                self._send_escalation_message(admin_user, escalation_message)

            self.record_decision(
                AgentAction.AUTO_ALERT,
                "mobile_reminder_record",
                0,
                f"【催报升级】{workshop_name} {shift_name} 已催报{next_count}次未响应，请管理员关注。负责人：{leader.name}",
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
            reminder_count = max(
                int(history_query.count()),
                int(getattr(existing, "reminder_count", 0) or 0),
            )
            next_count = reminder_count + 1

            if reminder_count < 3:
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
                message = (
                    f"【催报提醒】{workshop_name} {role_label} 尚未提交，"
                    f"请尽快在填报端完成。（第{next_count}次提醒）"
                )
                self._send_reminder_message(leader, message, db=db)
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
                escalation_message = (
                    f"【催报升级】{workshop_name} {role_label} 已催报{next_count}次未响应，"
                    f"请管理员关注。负责人：{leader.name}"
                )
                self._send_escalation_message(admin_user, escalation_message, db=db)

            self.record_decision(
                AgentAction.AUTO_ALERT,
                "mobile_reminder_record",
                0,
                f"【催报升级】{workshop_name} {role_label} 已催报{next_count}次未响应，请管理员关注。负责人：{leader.name}",
                workshop_id=candidate["workshop_id"],
                shift_id=candidate["shift_config_id"],
                leader_user_id=leader.id,
                reminder_count=next_count,
            )

        return self._decisions


reminder_agent = ReminderAgent()
