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

import asyncio
from datetime import date, datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision, BaseAgent
from app.config import settings
from app.models.attendance import AttendanceSchedule
from app.models.master import Workshop
from app.models.production import MobileReminderRecord, MobileShiftReport
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.mobile_reminder_service import _shift_deadline

READY_STATUSES = {"submitted", "approved", "auto_confirmed"}
MOBILE_ROLE_NAMES = {"team_leader", "deputy_leader", "mobile_user"}


def _wecom_userid(user: User) -> str | None:
    """提取可用于企业微信发送的用户标识。"""

    return (user.dingtalk_user_id or user.username or "").strip() or None


class ReminderAgent(BaseAgent):
    """催报Agent：自动检测未报班次并催报。"""

    def __init__(self):
        """初始化催报 Agent。"""
        super().__init__("reminder")

    def _send_reminder_message(self, userid: str, content: str) -> None:
        """发送催报消息；企业微信未启用时仅记录日志。"""

        if not settings.AUTO_PUSH_ENABLED:
            self.logger.info("自动推送已关闭，催报消息仅记录：%s", content)
            return
        if not settings.WECOM_APP_ENABLED:
            self.logger.info("企业微信未启用，催报消息仅记录：%s", content)
            return
        from app.adapters.wecom import send_app_message

        asyncio.run(send_app_message(userid, content))

    def _send_escalation_message(self, userid: str, content: str) -> None:
        """发送升级消息；企业微信未启用时仅记录日志。"""

        if not settings.AUTO_PUSH_ENABLED:
            self.logger.info("自动推送已关闭，升级消息仅记录：%s", content)
            return
        if not settings.WECOM_APP_ENABLED:
            self.logger.info("企业微信未启用，升级消息仅记录：%s", content)
            return
        from app.adapters.wecom import send_app_message

        asyncio.run(send_app_message(userid, content))

    def _resolve_leader(self, db: Session, *, workshop_id: int, team_id: int | None) -> User | None:
        """按班组优先、车间兜底查找负责人。"""

        base_query = db.query(User).filter(
            User.is_active.is_(True),
            User.workshop_id == workshop_id,
            or_(User.is_mobile_user.is_(True), User.role.in_(tuple(MOBILE_ROLE_NAMES))),
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
        if not expected_rows:
            return self._decisions

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

        now_local = datetime.now(timezone.utc).astimezone()
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

            reminder_count = int(
                db.query(MobileReminderRecord)
                .filter(
                    MobileReminderRecord.business_date == item.business_date,
                    MobileReminderRecord.shift_config_id == item.shift_config_id,
                    MobileReminderRecord.workshop_id == item.workshop_id,
                    MobileReminderRecord.team_id == item.team_id,
                    MobileReminderRecord.leader_user_id == leader.id,
                )
                .count()
            )
            next_count = reminder_count + 1

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

            if reminder_count < 3:
                entity = MobileReminderRecord(
                    business_date=item.business_date,
                    shift_config_id=item.shift_config_id,
                    workshop_id=item.workshop_id,
                    team_id=item.team_id,
                    leader_user_id=leader.id,
                    reminder_type=reminder_type,
                    reminder_status="sent",
                    reminder_channel="wecom" if settings.WECOM_APP_ENABLED else "system",
                    reminder_count=next_count,
                    last_reminded_at=datetime.now(timezone.utc),
                    note=None,
                )
                db.add(entity)
                message = (
                    f"【催报提醒】{workshop_name} {shift_name} 的生产数据尚未提交，"
                    f"请尽快在企业微信中完成填报。（第{next_count}次提醒）"
                )
                user_id = _wecom_userid(leader)
                if user_id:
                    self._send_reminder_message(user_id, message)
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

            escalation = MobileReminderRecord(
                business_date=item.business_date,
                shift_config_id=item.shift_config_id,
                workshop_id=item.workshop_id,
                team_id=item.team_id,
                leader_user_id=leader.id,
                reminder_type="escalation",
                reminder_status="sent",
                reminder_channel="wecom" if settings.WECOM_APP_ENABLED else "system",
                reminder_count=next_count,
                last_reminded_at=datetime.now(timezone.utc),
                note="自动升级提醒管理员",
            )
            db.add(escalation)

            admin_users = self._admin_users(db)
            for admin_user in admin_users:
                admin_userid = _wecom_userid(admin_user)
                if not admin_userid:
                    continue
                escalation_message = (
                    f"【催报升级】{workshop_name} {shift_name} 已催报{next_count}次未响应，"
                    f"请管理员关注。负责人：{leader.name}"
                )
                self._send_escalation_message(admin_userid, escalation_message)

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

        return self._decisions


reminder_agent = ReminderAgent()
