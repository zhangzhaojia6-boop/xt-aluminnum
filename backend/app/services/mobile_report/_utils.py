from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.agents.validator import validator_agent
from app.agents.base import AgentAction, AgentDecision
from app.config import settings
from app.core.permissions import assert_mobile_report_access, assert_mobile_user_access, assert_scope_access
from app.core.scope import build_scope_summary, scope_to_dict
from app.core.workshop_templates import resolve_workshop_type
from app.models.attendance import AttendanceSchedule
from app.models.energy import MachineEnergyRecord
from app.models.master import Equipment, Team, Workshop
from app.models.production import (
    MobileReminderRecord,
    MobileShiftReport,
    ProductionException,
    ShiftProductionData,
    WorkOrderEntry,
)
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import dingtalk_service
from app.services.audit_service import record_entity_change
from app.services.equipment_service import get_bound_machine_for_user
from app.services.pilot_observability_service import log_pilot_event


AUTO_CONFIRMED_REPORT_STATUS = 'auto_confirmed'

APPROVED_REPORT_STATUSES = {'approved', AUTO_CONFIRMED_REPORT_STATUS}

SUBMITTED_STATUSES = {'submitted', *APPROVED_REPORT_STATUSES}

LOCAL_TZ = ZoneInfo(settings.DEFAULT_TIMEZONE)

PHOTO_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

PHOTO_MAX_BYTES = 5 * 1024 * 1024

@dataclass(slots=True)
class ShiftContext:
    business_date: date
    shift: ShiftConfig | None
    workshop: Workshop
    team: Team | None
    machine: Equipment | None = None

def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)

def _json_ready(value):
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value

def _model_to_dict(entity) -> dict:
    return {column.name: getattr(entity, column.name) for column in entity.__table__.columns}

def _normalize_override_reason(value: str | None) -> str | None:
    normalized = (value or '').strip()
    return normalized or None

def _mobile_report_decision_status(report: MobileShiftReport | None) -> str:
    if report is None:
        return 'unreported'
    if _normalize_override_reason(getattr(report, 'returned_reason', None)) is not None:
        return 'returned'
    report_status = getattr(report, 'report_status', None)
    if report_status in APPROVED_REPORT_STATUSES:
        return AUTO_CONFIRMED_REPORT_STATUS
    if report_status == 'returned':
        return 'returned'
    return report_status or 'unreported'

def _is_mobile_report_auto_confirmed(report: MobileShiftReport | None) -> bool:
    return _mobile_report_decision_status(report) == AUTO_CONFIRMED_REPORT_STATUS

def _build_agent_decision_snapshot(
    *,
    report: MobileShiftReport | None,
    decisions: list[AgentDecision] | None = None,
) -> dict:
    latest = decisions[-1] if decisions else None
    if latest is not None:
        details = latest.details or {}
        if latest.action == AgentAction.AUTO_CONFIRM:
            status = AUTO_CONFIRMED_REPORT_STATUS
        elif latest.action == AgentAction.AUTO_REJECT:
            status = 'returned'
        else:
            status = _mobile_report_decision_status(report)
        return {
            'agent_decision_status': status,
            'agent_decision_action': latest.action.value,
            'agent_decision_agent': latest.agent_name,
            'agent_decision_reason': latest.reason,
            'agent_decision_warnings': [str(item) for item in (details.get('warnings') or [])],
            'agent_decision_errors': [str(item) for item in (details.get('errors') or [])],
            'agent_decision_at': latest.timestamp,
        }

    status = _mobile_report_decision_status(report)
    if status == AUTO_CONFIRMED_REPORT_STATUS:
        return {
            'agent_decision_status': AUTO_CONFIRMED_REPORT_STATUS,
            'agent_decision_action': AgentAction.AUTO_CONFIRM.value,
            'agent_decision_agent': 'validator',
            'agent_decision_reason': '系统自动校验通过',
            'agent_decision_warnings': [],
            'agent_decision_errors': [],
            'agent_decision_at': None,
        }
    if status == 'returned':
        return {
            'agent_decision_status': 'returned',
            'agent_decision_action': AgentAction.AUTO_REJECT.value,
            'agent_decision_agent': 'validator',
            'agent_decision_reason': (
                _normalize_override_reason(getattr(report, 'returned_reason', None))
                or '系统自动校验未通过，请按提示修正后再提交。'
            ),
            'agent_decision_warnings': [],
            'agent_decision_errors': [],
            'agent_decision_at': None,
        }
    return {
        'agent_decision_status': status if report is not None else None,
        'agent_decision_action': None,
        'agent_decision_agent': None,
        'agent_decision_reason': None,
        'agent_decision_warnings': [],
        'agent_decision_errors': [],
        'agent_decision_at': None,
    }

def _ensure_mobile_write_scope(current_user: User, *, workshop_id: int, shift_id: int) -> None:
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.is_reviewer:
        return
    if current_user.workshop_id is None or int(current_user.workshop_id) != int(workshop_id):
        raise HTTPException(status_code=403, detail='当前账号不在该车间权限内，请联系管理员检查用户归属。')
    if summary.assigned_shift_ids and int(shift_id) not in summary.assigned_shift_ids:
        raise HTTPException(status_code=403, detail='当前账号未分配该班次，请联系管理员检查班次权限。')

def _ensure_mobile_override_for_locked_report(report: MobileShiftReport, current_user: User, *, override_reason: str | None) -> None:
    if report.report_status not in SUBMITTED_STATUSES:
        return
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.is_reviewer:
        if override_reason is not None:
            return
    raise HTTPException(
        status_code=403,
        detail='submitted or approved reports require reviewer/admin override with reason',
    )

def _round_value(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)

def _public_upload_url(relative_path: str, *, public_prefix: str = '/uploads') -> str:
    prefix = public_prefix.rstrip('/')
    return f"{prefix}/{relative_path.lstrip('/')}"

def _normalize_filename(name: str) -> str:
    raw_name = (name or '').strip() or 'photo'
    suffix = Path(raw_name).suffix.lower()
    if suffix not in PHOTO_ALLOWED_EXTENSIONS:
        suffix = '.jpg'
    stem = Path(raw_name).stem.strip().replace(' ', '_') or 'photo'
    safe_stem = ''.join(char for char in stem if char.isalnum() or char in {'_', '-', '.', '\u4e00', '\u9fff'})
    safe_stem = safe_stem[:48] or 'photo'
    return f'{safe_stem}{suffix}'

def _local_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(LOCAL_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=LOCAL_TZ)
    return now.astimezone(LOCAL_TZ)

def _month_range(target_date: date) -> tuple[date, date]:
    month_start = target_date.replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1) - timedelta(days=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1) - timedelta(days=1)
    return month_start, month_end

def _serialize_active_reminders(rows: list[MobileReminderRecord]) -> list[dict]:
    return [
        {
            'id': row.id,
            'reminder_type': row.reminder_type,
            'reminder_status': row.reminder_status,
            'reminder_channel': row.reminder_channel,
            'reminder_count': row.reminder_count,
            'last_reminded_at': row.last_reminded_at,
            'note': row.note,
        }
        for row in rows
    ]

def _active_reminders_for_context(
    db: Session,
    *,
    business_date: date,
    shift_id: int,
    workshop_id: int,
    team_id: int | None,
    leader_user_id: int | None,
) -> list[dict]:
    query = db.query(MobileReminderRecord).filter(
        MobileReminderRecord.business_date == business_date,
        MobileReminderRecord.shift_config_id == shift_id,
        MobileReminderRecord.workshop_id == workshop_id,
        MobileReminderRecord.reminder_status.in_(['pending', 'sent', 'acknowledged']),
    )
    if team_id is None:
        query = query.filter(MobileReminderRecord.team_id.is_(None))
    else:
        query = query.filter(MobileReminderRecord.team_id == team_id)
    if leader_user_id is not None:
        query = query.filter(MobileReminderRecord.leader_user_id == leader_user_id)
    rows = query.order_by(MobileReminderRecord.id.desc()).all()
    return _serialize_active_reminders(rows)

def _ownership_note(*, report: MobileShiftReport | None, current_user: User) -> str | None:
    if report is None:
        return None
    owner_user_id = report.owner_user_id or report.leader_user_id
    if owner_user_id and owner_user_id != current_user.id:
        return '当前班次已由其他负责人处理，如需代填请走授权流程。'
    return None

def _same_month(base_date: date, compare_date: date) -> bool:
    return base_date.year == compare_date.year and base_date.month == compare_date.month
