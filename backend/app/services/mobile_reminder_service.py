from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.permissions import assert_scope_access
from app.core.scope import build_scope_summary
from app.models.attendance import AttendanceSchedule
from app.models.production import MobileReminderRecord, MobileShiftReport
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import dingtalk_service
from app.services.audit_service import record_audit

LOCAL_TZ = ZoneInfo(settings.DEFAULT_TIMEZONE)
READY_REPORT_STATUSES = {'submitted', 'approved', 'auto_confirmed'}
OPEN_REMINDER_STATUSES = {'pending', 'sent', 'acknowledged'}
MOBILE_ROLE_NAMES = {'team_leader', 'deputy_leader', 'mobile_user'}


def _local_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(LOCAL_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=LOCAL_TZ)
    return now.astimezone(LOCAL_TZ)


def _schedule_key(row) -> tuple[date, int, int, int | None]:
    return (row.business_date, row.shift_config_id, row.workshop_id, row.team_id)


def _shift_deadline(
    *,
    business_date: date,
    shift,
    grace_minutes: int,
) -> datetime:
    end_dt = datetime.combine(business_date, shift.end_time, tzinfo=LOCAL_TZ)
    if getattr(shift, 'business_day_offset', 0):
        end_dt += timedelta(days=shift.business_day_offset)
    if getattr(shift, 'is_cross_day', False) or shift.end_time <= shift.start_time:
        end_dt += timedelta(days=1)
    return end_dt + timedelta(minutes=grace_minutes)


def _serialize_reminder(item: MobileReminderRecord) -> dict:
    return {
        'id': item.id,
        'business_date': item.business_date,
        'shift_config_id': item.shift_config_id,
        'workshop_id': item.workshop_id,
        'team_id': item.team_id,
        'leader_user_id': item.leader_user_id,
        'reminder_type': item.reminder_type,
        'reminder_status': item.reminder_status,
        'reminder_channel': item.reminder_channel,
        'reminder_count': item.reminder_count,
        'last_reminded_at': item.last_reminded_at,
        'acknowledged_at': item.acknowledged_at,
        'acknowledged_by': item.acknowledged_by,
        'closed_at': item.closed_at,
        'closed_by': item.closed_by,
        'note': item.note,
    }


def _apply_scope_filter(query, *, current_user: User):
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.data_scope_type == 'all':
        return query
    if summary.is_mobile_user and not summary.is_reviewer and not summary.is_manager:
        return query.filter(MobileReminderRecord.leader_user_id == current_user.id)
    if summary.workshop_id is not None:
        query = query.filter(MobileReminderRecord.workshop_id == summary.workshop_id)
    if summary.data_scope_type == 'self_team' and summary.team_id is not None:
        query = query.filter(MobileReminderRecord.team_id == summary.team_id)
    if summary.data_scope_type == 'assigned' and summary.assigned_shift_ids:
        query = query.filter(MobileReminderRecord.shift_config_id.in_(summary.assigned_shift_ids))
    return query


def _ensure_reminder_operator(current_user: User) -> None:
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.is_reviewer or summary.is_manager:
        return
    raise HTTPException(status_code=403, detail='Reminder operation denied')


def _ensure_reminder_access(current_user: User, reminder: MobileReminderRecord) -> None:
    summary = build_scope_summary(current_user)
    if summary.is_mobile_user and not summary.is_reviewer and not summary.is_manager and not summary.is_admin:
        if reminder.leader_user_id != current_user.id:
            raise HTTPException(status_code=403, detail='Reminder access denied')
        return
    assert_scope_access(
        current_user,
        workshop_id=reminder.workshop_id,
        team_id=reminder.team_id,
        shift_id=reminder.shift_config_id,
    )


def build_reminder_candidates(
    *,
    expected_rows: list,
    report_rows: list,
    shift_map: dict[int, object],
    leader_map: dict[tuple[int, int | None], int],
    now: datetime | None,
    grace_minutes: int,
) -> list[dict]:
    current_local = _local_now(now)
    report_map = {_schedule_key(row): row for row in report_rows}
    candidates: list[dict] = []

    for row in expected_rows:
        leader_user_id = leader_map.get((row.workshop_id, row.team_id))
        if leader_user_id is None:
            continue
        shift = shift_map.get(row.shift_config_id)
        if shift is None:
            continue
        report = report_map.get(_schedule_key(row))
        if report is not None and getattr(report, 'report_status', None) in READY_REPORT_STATUSES:
            continue

        reminder_type = 'unreported'
        if current_local >= _shift_deadline(business_date=row.business_date, shift=shift, grace_minutes=grace_minutes):
            reminder_type = 'late_report'

        candidates.append(
            {
                'business_date': row.business_date,
                'shift_config_id': row.shift_config_id,
                'workshop_id': row.workshop_id,
                'team_id': row.team_id,
                'leader_user_id': leader_user_id,
                'reminder_type': reminder_type,
                'reminder_status': 'pending',
                'reminder_channel': 'system',
                'reminder_count': 1,
                'note': None,
            }
        )
    return candidates


def _leader_map_for_rows(db: Session, *, expected_rows: list) -> tuple[dict[tuple[int, int | None], int], dict[int, User]]:
    keys = {(row.workshop_id, row.team_id) for row in expected_rows}
    workshop_ids = {item[0] for item in keys if item[0] is not None}
    team_ids = {item[1] for item in keys if item[1] is not None}
    query = db.query(User).filter(User.is_active.is_(True))
    if workshop_ids:
        query = query.filter(User.workshop_id.in_(workshop_ids))
    if team_ids:
        query = query.filter(or_(User.team_id.in_(team_ids), User.team_id.is_(None)))
    query = query.filter(or_(User.is_mobile_user.is_(True), User.role.in_(tuple(MOBILE_ROLE_NAMES))))
    users = query.order_by(User.id.asc()).all()

    leader_map: dict[tuple[int, int | None], int] = {}
    user_map: dict[int, User] = {}
    for user in users:
        key = (user.workshop_id, user.team_id)
        if key not in keys or key in leader_map:
            continue
        leader_map[key] = user.id
        user_map[user.id] = user
    return leader_map, user_map


def run_reminders(
    db: Session,
    *,
    current_user: User,
    target_date: date | None = None,
    grace_minutes: int = 30,
) -> list[dict]:
    _ensure_reminder_operator(current_user)
    business_date = target_date or _local_now().date()

    schedule_query = (
        db.query(
            AttendanceSchedule.business_date,
            AttendanceSchedule.shift_config_id,
            AttendanceSchedule.workshop_id,
            AttendanceSchedule.team_id,
        )
        .filter(
            AttendanceSchedule.business_date == business_date,
            AttendanceSchedule.shift_config_id.is_not(None),
            AttendanceSchedule.workshop_id.is_not(None),
        )
        .distinct()
    )
    scope_summary = build_scope_summary(current_user)
    if not scope_summary.is_admin and scope_summary.data_scope_type != 'all':
        if scope_summary.workshop_id is not None:
            schedule_query = schedule_query.filter(AttendanceSchedule.workshop_id == scope_summary.workshop_id)
        if scope_summary.data_scope_type == 'self_team' and scope_summary.team_id is not None:
            schedule_query = schedule_query.filter(AttendanceSchedule.team_id == scope_summary.team_id)
        if scope_summary.data_scope_type == 'assigned' and scope_summary.assigned_shift_ids:
            schedule_query = schedule_query.filter(AttendanceSchedule.shift_config_id.in_(scope_summary.assigned_shift_ids))

    expected_rows = schedule_query.all()
    if not expected_rows:
        return []

    report_query = db.query(MobileShiftReport).filter(MobileShiftReport.business_date == business_date)
    expected_keys = {_schedule_key(row) for row in expected_rows}
    report_rows = [
        row
        for row in report_query.all()
        if _schedule_key(row) in expected_keys
    ]

    shift_ids = {row.shift_config_id for row in expected_rows}
    shift_map = {item.id: item for item in db.query(ShiftConfig).filter(ShiftConfig.id.in_(shift_ids)).all()} if shift_ids else {}
    leader_map, leader_users = _leader_map_for_rows(db, expected_rows=expected_rows)
    candidates = build_reminder_candidates(
        expected_rows=expected_rows,
        report_rows=report_rows,
        shift_map=shift_map,
        leader_map=leader_map,
        now=_local_now(),
        grace_minutes=grace_minutes,
    )

    now_utc = datetime.utcnow()
    entities: list[MobileReminderRecord] = []
    for candidate in candidates:
        leader = leader_users.get(candidate['leader_user_id'])
        reminder_channel = (
            'dingtalk_reserved'
            if leader and (leader.dingtalk_user_id or leader.dingtalk_union_id)
            else 'system'
        )
        entity = (
            db.query(MobileReminderRecord)
            .filter(
                MobileReminderRecord.business_date == candidate['business_date'],
                MobileReminderRecord.shift_config_id == candidate['shift_config_id'],
                MobileReminderRecord.workshop_id == candidate['workshop_id'],
                MobileReminderRecord.team_id == candidate['team_id'],
                MobileReminderRecord.leader_user_id == candidate['leader_user_id'],
                MobileReminderRecord.reminder_type == candidate['reminder_type'],
            )
            .first()
        )
        if entity is None:
            entity = MobileReminderRecord(
                business_date=candidate['business_date'],
                shift_config_id=candidate['shift_config_id'],
                workshop_id=candidate['workshop_id'],
                team_id=candidate['team_id'],
                leader_user_id=candidate['leader_user_id'],
                reminder_type=candidate['reminder_type'],
                reminder_status='sent',
                reminder_channel=reminder_channel,
                reminder_count=1,
                last_reminded_at=now_utc,
                note=candidate.get('note'),
            )
            db.add(entity)
        else:
            entity.reminder_status = 'sent'
            entity.reminder_channel = reminder_channel
            entity.reminder_count = int(entity.reminder_count or 0) + 1
            entity.last_reminded_at = now_utc
            entity.note = candidate.get('note') or entity.note
        db.flush()
        if reminder_channel == 'dingtalk_reserved':
            dingtalk_service.service.send_text(
                title='班次填报提醒',
                content=f"{candidate['business_date']} 班次 {candidate['shift_config_id']} 尚未完成填报，请尽快处理。",
            )
        record_audit(
            db,
            user=current_user,
            action='mobile_reminder_run',
            module='mobile',
            entity_type='mobile_reminder_records',
            entity_id=entity.id,
            detail={
                'business_date': candidate['business_date'].isoformat(),
                'shift_id': candidate['shift_config_id'],
                'workshop_id': candidate['workshop_id'],
                'team_id': candidate['team_id'],
                'leader_user_id': candidate['leader_user_id'],
                'reminder_type': candidate['reminder_type'],
            },
            auto_commit=False,
        )
        entities.append(entity)

    db.commit()
    return [_serialize_reminder(item) for item in entities]


def list_reminders(
    db: Session,
    *,
    current_user: User,
    business_date: date | None = None,
    reminder_status: str | None = None,
) -> list[dict]:
    query = db.query(MobileReminderRecord)
    if business_date is not None:
        query = query.filter(MobileReminderRecord.business_date == business_date)
    if reminder_status:
        query = query.filter(MobileReminderRecord.reminder_status == reminder_status)
    query = _apply_scope_filter(query, current_user=current_user)
    rows = query.order_by(MobileReminderRecord.business_date.desc(), MobileReminderRecord.id.desc()).limit(200).all()
    return [_serialize_reminder(item) for item in rows]


def active_reminders_for_context(
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
        MobileReminderRecord.reminder_status.in_(tuple(OPEN_REMINDER_STATUSES)),
    )
    if team_id is None:
        query = query.filter(MobileReminderRecord.team_id.is_(None))
    else:
        query = query.filter(MobileReminderRecord.team_id == team_id)
    if leader_user_id is not None:
        query = query.filter(MobileReminderRecord.leader_user_id == leader_user_id)
    rows = query.order_by(MobileReminderRecord.id.desc()).all()
    return [_serialize_reminder(item) for item in rows]


def ack_reminder(
    db: Session,
    *,
    reminder_id: int,
    current_user: User,
    note: str | None = None,
) -> dict:
    reminder = db.get(MobileReminderRecord, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail='reminder not found')
    _ensure_reminder_access(current_user, reminder)
    reminder.reminder_status = 'acknowledged'
    reminder.acknowledged_at = datetime.utcnow()
    reminder.acknowledged_by = current_user.id
    reminder.note = note or reminder.note
    db.flush()
    record_audit(
        db,
        user=current_user,
        action='mobile_reminder_ack',
        module='mobile',
        entity_type='mobile_reminder_records',
        entity_id=reminder.id,
        detail={'status': reminder.reminder_status, 'note': note},
        reason=note,
        auto_commit=False,
    )
    db.commit()
    db.refresh(reminder)
    return _serialize_reminder(reminder)


def close_reminder(
    db: Session,
    *,
    reminder_id: int,
    current_user: User,
    note: str | None = None,
) -> dict:
    reminder = db.get(MobileReminderRecord, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail='reminder not found')
    _ensure_reminder_access(current_user, reminder)
    summary = build_scope_summary(current_user)
    if not summary.is_admin and not summary.is_manager and not summary.is_reviewer:
        raise HTTPException(status_code=403, detail='Only reviewer or manager can close reminders')
    reminder.reminder_status = 'closed'
    reminder.closed_at = datetime.utcnow()
    reminder.closed_by = current_user.id
    reminder.note = note or reminder.note
    db.flush()
    record_audit(
        db,
        user=current_user,
        action='mobile_reminder_close',
        module='mobile',
        entity_type='mobile_reminder_records',
        entity_id=reminder.id,
        detail={'status': reminder.reminder_status, 'note': note},
        reason=note,
        auto_commit=False,
    )
    db.commit()
    db.refresh(reminder)
    return _serialize_reminder(reminder)


def summarize_reminders(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None = None,
) -> dict:
    query = db.query(MobileReminderRecord).filter(MobileReminderRecord.business_date == target_date)
    if workshop_id is not None:
        query = query.filter(MobileReminderRecord.workshop_id == workshop_id)
    rows = query.all()
    return {
        'unreported_count': len([row for row in rows if row.reminder_type == 'unreported' and row.reminder_status != 'closed']),
        'late_report_count': len([row for row in rows if row.reminder_type == 'late_report' and row.reminder_status != 'closed']),
        'today_reminder_count': sum(int(row.reminder_count or 0) for row in rows),
        'recent_items': [_serialize_reminder(row) for row in rows[-8:]],
    }
