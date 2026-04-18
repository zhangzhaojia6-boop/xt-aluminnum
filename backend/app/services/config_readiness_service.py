"""配置就绪检查服务。

用于替代试点前人工逐项核对主数据，提前识别会导致无法上报、
上报率失真或权限异常的配置缺口。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.attendance import AttendanceSchedule
from app.models.master import Equipment, Team, Workshop
from app.models.shift import ShiftConfig
from app.models.system import User


MOBILE_ROLES = {
    "team_leader",
    "deputy_leader",
    "mobile_user",
    "shift_leader",
    "weigher",
    "qc",
    "energy_stat",
    "maintenance_lead",
    "hydraulic_lead",
    "contracts",
    "inventory_keeper",
    "utility_manager",
}


def _issue(
    *,
    level: str,
    code: str,
    message: str,
    suggestion: str,
    sample: list[str] | None = None,
) -> dict[str, Any]:
    """构造统一格式的问题项。"""

    payload = {
        "level": level,
        "code": code,
        "message": message,
        "suggestion": suggestion,
    }
    if sample:
        payload["sample"] = sample[:8]
    return payload


def inspect_pilot_config(db: Session, *, target_date: date) -> dict[str, Any]:
    """检查试点运行必需配置是否完整。"""

    issues: list[dict[str, Any]] = []

    workshops = db.query(Workshop).filter(Workshop.is_active.is_(True)).all()
    workshop_ids = {item.id for item in workshops}
    if not workshops:
        issues.append(
            _issue(
                level="hard",
                code="NO_ACTIVE_WORKSHOP",
                message="未找到启用中的车间。",
                suggestion="请先在主数据中启用至少一个车间。",
            )
        )

    shifts = db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).all()
    if not shifts:
        issues.append(
            _issue(
                level="hard",
                code="NO_ACTIVE_SHIFT",
                message="未找到启用中的班次。",
                suggestion="请先在班次配置中启用班次，并检查起止时间。",
            )
        )
    else:
        for workshop in workshops:
            has_shift = any(item.workshop_id in {None, workshop.id} for item in shifts)
            if not has_shift:
                issues.append(
                    _issue(
                        level="hard",
                        code="WORKSHOP_SHIFT_MISSING",
                        message=f"车间“{workshop.name}”没有可用班次。",
                        suggestion="请为该车间配置班次，或启用可复用的公共班次。",
                    )
                )

    teams = db.query(Team).filter(Team.is_active.is_(True)).all()
    team_map = {item.id: item for item in teams}

    mobile_users = (
        db.query(User)
        .filter(User.is_active.is_(True))
        .filter((User.is_mobile_user.is_(True)) | (User.role.in_(tuple(MOBILE_ROLES))))
        .all()
    )
    if not mobile_users:
        issues.append(
            _issue(
                level="hard",
                code="NO_MOBILE_USER",
                message="未找到可用于现场填报的启用账号。",
                suggestion="请至少配置一个启用中的移动填报账号（班长/机台账号）。",
            )
        )
    else:
        no_workshop_users = [f"{user.username}({user.name})" for user in mobile_users if user.workshop_id is None]
        if no_workshop_users:
            issues.append(
                _issue(
                    level="hard",
                    code="MOBILE_USER_WORKSHOP_MISSING",
                    message="存在未绑定车间的移动填报账号。",
                    suggestion="请在用户管理中为账号绑定车间归属。",
                    sample=no_workshop_users,
                )
            )

        bad_team_users: list[str] = []
        for user in mobile_users:
            if user.team_id is None:
                continue
            team = team_map.get(user.team_id)
            if team is None or team.workshop_id != user.workshop_id:
                bad_team_users.append(f"{user.username}({user.name})")
        if bad_team_users:
            issues.append(
                _issue(
                    level="warning",
                    code="MOBILE_USER_TEAM_MISMATCH",
                    message="存在班组归属异常的移动账号（班组不存在或不在同车间）。",
                    suggestion="请修正账号班组归属，避免统计维度异常。",
                    sample=bad_team_users,
                )
            )

    equipment_rows = db.query(Equipment).filter(Equipment.is_active.is_(True)).all()
    if not equipment_rows:
        issues.append(
            _issue(
                level="warning",
                code="NO_ACTIVE_EQUIPMENT",
                message="未找到启用中的设备记录。",
                suggestion="如采用机台绑定填报，请先启用设备并绑定机台账号。",
            )
        )
    else:
        bad_workshop_equipment = [
            f"{item.code}({item.name})"
            for item in equipment_rows
            if item.workshop_id not in workshop_ids
        ]
        if bad_workshop_equipment:
            issues.append(
                _issue(
                    level="hard",
                    code="EQUIPMENT_WORKSHOP_INVALID",
                    message="存在设备挂载到无效车间的配置。",
                    suggestion="请修正设备所属车间，避免机台账号无法填报。",
                    sample=bad_workshop_equipment,
                )
            )

        user_map = {item.id: item for item in db.query(User).all()}
        bad_binding = []
        for item in equipment_rows:
            if item.bound_user_id is None:
                continue
            user = user_map.get(item.bound_user_id)
            if user is None:
                bad_binding.append(f"{item.code}({item.name})")
                continue
            if user.workshop_id != item.workshop_id:
                bad_binding.append(f"{item.code}({item.name})")
        if bad_binding:
            issues.append(
                _issue(
                    level="hard",
                    code="EQUIPMENT_USER_BINDING_INVALID",
                    message="存在机台账号绑定异常（账号不存在或跨车间绑定）。",
                    suggestion="请重新绑定机台账号，保证账号与设备在同一车间。",
                    sample=bad_binding,
                )
            )

    schedules = db.query(AttendanceSchedule).filter(AttendanceSchedule.business_date == target_date).all()
    if not schedules:
        issues.append(
            _issue(
                level="hard",
                code="SCHEDULE_EMPTY",
                message=f"{target_date.isoformat()} 的应报清单为空。",
                suggestion="请先导入或生成当日排班/应报清单，再开始试点。",
            )
        )
    else:
        missing_workshop_rows = [row for row in schedules if row.workshop_id is None]
        if missing_workshop_rows:
            issues.append(
                _issue(
                    level="hard",
                    code="SCHEDULE_WORKSHOP_MISSING",
                    message="应报清单存在未绑定车间的记录。",
                    suggestion="请修复排班数据的车间字段，避免统计丢失。",
                )
            )

        missing_shift_rows = [row for row in schedules if row.shift_config_id is None]
        if missing_shift_rows:
            issues.append(
                _issue(
                    level="hard",
                    code="SCHEDULE_SHIFT_MISSING",
                    message="应报清单存在未绑定班次的记录。",
                    suggestion="请修复排班数据的班次字段，避免提醒和上报率异常。",
                )
            )

        shift_ids = {item.id for item in shifts}
        invalid_shift_rows = [row for row in schedules if row.shift_config_id is not None and row.shift_config_id not in shift_ids]
        if invalid_shift_rows:
            issues.append(
                _issue(
                    level="hard",
                    code="SCHEDULE_SHIFT_INVALID",
                    message="应报清单引用了未启用或不存在的班次。",
                    suggestion="请在班次配置中启用对应班次，或修正排班数据。",
                )
            )

        schedule_workshop_ids = {row.workshop_id for row in schedules if row.workshop_id is not None}
        mobile_workshop_ids = {user.workshop_id for user in mobile_users if user.workshop_id is not None}
        uncovered_workshops = [item.name for item in workshops if item.id in mobile_workshop_ids and item.id not in schedule_workshop_ids]
        if uncovered_workshops:
            issues.append(
                _issue(
                    level="hard",
                    code="SCHEDULE_WORKSHOP_UNCOVERED",
                    message="存在有填报账号但无当日应报清单的车间。",
                    suggestion="请补齐这些车间的当日排班/应报清单。",
                    sample=uncovered_workshops,
                )
            )

    hard_issues = [item for item in issues if item["level"] == "hard"]
    warning_issues = [item for item in issues if item["level"] == "warning"]
    return {
        "target_date": target_date.isoformat(),
        "hard_gate_passed": len(hard_issues) == 0,
        "hard_issues": hard_issues,
        "warning_issues": warning_issues,
        "stats": {
            "active_workshop_count": len(workshops),
            "active_shift_count": len(shifts),
            "active_mobile_user_count": len(mobile_users),
            "active_equipment_count": len(equipment_rows),
            "schedule_row_count": len(schedules),
        },
    }
