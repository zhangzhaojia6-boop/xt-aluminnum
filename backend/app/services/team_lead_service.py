from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.attendance import AttendanceResult, AttendanceSchedule
from app.models.master import Employee, Team, Workshop
from app.models.production import MobileReminderRecord, MobileShiftReport
from app.models.shift import ShiftConfig
from app.models.system import User


ATTENDED_STATUSES = {'normal', 'late', 'early_leave', 'overtime', 'present'}
REPORTED_STATUSES = {'submitted', 'approved', 'auto_confirmed', 'returned'}


def _apply_scope(query, model, user: User):
    if getattr(user, 'role', '') == 'admin':
        return query
    workshop_id = getattr(user, 'workshop_id', None)
    team_id = getattr(user, 'team_id', None)
    if workshop_id is not None and hasattr(model, 'workshop_id'):
        query = query.filter(model.workshop_id == workshop_id)
    if team_id is not None and hasattr(model, 'team_id'):
        query = query.filter(model.team_id == team_id)
    return query


def _map_by_id(db: Session, model, ids: set[int]) -> dict[int, Any]:
    if not ids:
        return {}
    return {int(item.id): item for item in db.query(model).filter(model.id.in_(ids)).all()}


def _iso(value) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, 'isoformat') else None


def _shift_name(shift_map: dict[int, ShiftConfig], shift_id: int | None) -> str:
    if shift_id is None:
        return '未排班次'
    shift = shift_map.get(int(shift_id))
    return shift.name if shift is not None else f'班次{shift_id}'


def _workshop_name(workshop_map: dict[int, Workshop], workshop_id: int | None) -> str:
    if workshop_id is None:
        return '未分车间'
    workshop = workshop_map.get(int(workshop_id))
    return workshop.name if workshop is not None else f'车间{workshop_id}'


def _team_name(team_map: dict[int, Team], team_id: int | None) -> str:
    if team_id is None:
        return '未分班组'
    team = team_map.get(int(team_id))
    return team.name if team is not None else f'班组{team_id}'


def _health(*, scheduled_count: int, returned_count: int, pending_count: int) -> str:
    if scheduled_count > 0 and returned_count / scheduled_count > 0.2:
        return 'red'
    if pending_count > 0:
        return 'yellow'
    return 'green'


def build_overview(db: Session, *, leader_user: User, target_date: date) -> dict[str, Any]:
    schedules = _apply_scope(
        db.query(AttendanceSchedule).filter(
            AttendanceSchedule.business_date == target_date,
            AttendanceSchedule.is_rest_day.is_(False),
        ),
        AttendanceSchedule,
        leader_user,
    ).all()
    attendance_results = _apply_scope(
        db.query(AttendanceResult).filter(AttendanceResult.business_date == target_date),
        AttendanceResult,
        leader_user,
    ).all()
    reports = _apply_scope(
        db.query(MobileShiftReport).filter(MobileShiftReport.business_date == target_date),
        MobileShiftReport,
        leader_user,
    ).all()
    reminders = _apply_scope(
        db.query(MobileReminderRecord).filter(MobileReminderRecord.business_date == target_date),
        MobileReminderRecord,
        leader_user,
    ).all()

    workshop_ids = {
        int(value)
        for value in [
            *(getattr(item, 'workshop_id', None) for item in schedules),
            *(getattr(item, 'workshop_id', None) for item in reports),
            *(getattr(item, 'workshop_id', None) for item in reminders),
        ]
        if value is not None
    }
    team_ids = {
        int(value)
        for value in [
            *(getattr(item, 'team_id', None) for item in schedules),
            *(getattr(item, 'team_id', None) for item in reports),
            *(getattr(item, 'team_id', None) for item in reminders),
        ]
        if value is not None
    }
    shift_ids = {
        int(value)
        for value in [
            *(getattr(item, 'shift_config_id', None) for item in schedules),
            *(getattr(item, 'shift_config_id', None) for item in reports),
            *(getattr(item, 'shift_config_id', None) for item in reminders),
        ]
        if value is not None
    }
    employee_ids = {int(item.employee_id) for item in schedules if getattr(item, 'employee_id', None) is not None}

    workshop_map = _map_by_id(db, Workshop, workshop_ids)
    team_map = _map_by_id(db, Team, team_ids)
    shift_map = _map_by_id(db, ShiftConfig, shift_ids)
    employee_map = _map_by_id(db, Employee, employee_ids)

    attended_employee_ids = {
        int(item.employee_id)
        for item in attendance_results
        if getattr(item, 'employee_id', None) is not None and str(item.attendance_status) in ATTENDED_STATUSES
    }
    scheduled_count = len(schedules)
    attended_count = len(attended_employee_ids)
    reported_rows = [item for item in reports if str(item.report_status) in REPORTED_STATUSES or item.returned_reason]
    returned_rows = [item for item in reports if str(item.report_status) == 'returned' or item.returned_reason]
    reported_key_set = {
        (item.business_date, item.shift_config_id, item.workshop_id, item.team_id)
        for item in reported_rows
    }

    pending_groups: dict[tuple[int | None, int | None, int | None], list[str]] = defaultdict(list)
    for schedule in schedules:
        schedule_key = (schedule.business_date, schedule.shift_config_id, schedule.workshop_id, schedule.team_id)
        has_report = schedule_key in reported_key_set
        has_attendance = int(schedule.employee_id) in attended_employee_ids
        if has_report and has_attendance:
            continue
        employee = employee_map.get(int(schedule.employee_id))
        pending_groups[(schedule.workshop_id, schedule.shift_config_id, schedule.team_id)].append(
            employee.name if employee is not None else f'员工{schedule.employee_id}'
        )

    pending_list = [
        {
            'business_date': target_date.isoformat(),
            'shift_id': shift_id,
            'workshop': _workshop_name(workshop_map, workshop_id),
            'shift': _shift_name(shift_map, shift_id),
            'team': _team_name(team_map, team_id),
            'members': members,
        }
        for (workshop_id, shift_id, team_id), members in pending_groups.items()
    ]

    returned_list = [
        {
            'report_id': int(item.id),
            'returned_reason': item.returned_reason or '',
            'member': item.leader_name or (f'负责人{item.leader_user_id}' if item.leader_user_id else ''),
        }
        for item in returned_rows
    ]

    reminder_groups: dict[tuple[int | None, int | None, int | None], dict[str, Any]] = {}
    for item in reminders:
        key = (item.workshop_id, item.shift_config_id, item.team_id)
        current = reminder_groups.setdefault(
            key,
            {
                'shift': _shift_name(shift_map, item.shift_config_id),
                'count': 0,
                'last_at': None,
            },
        )
        current['count'] += int(item.reminder_count or 1)
        current_at = getattr(item, 'last_reminded_at', None)
        if current_at is not None and (current['last_at'] is None or current_at > current['last_at']):
            current['last_at'] = current_at

    reminder_list = [
        {
            'shift': item['shift'],
            'count': item['count'],
            'last_at': _iso(item['last_at']),
        }
        for item in reminder_groups.values()
    ]
    reminder_count = sum(int(item.reminder_count or 1) for item in reminders)
    escalation_count = len(
        [
            item
            for item in reminders
            if str(item.reminder_type) == 'escalation' or str(item.reminder_status) == 'escalated'
        ]
    )
    pending_count = sum(len(item['members']) for item in pending_list)

    return {
        'scheduled_count': scheduled_count,
        'attended_count': attended_count,
        'reported_count': len(reported_rows),
        'returned_count': len(returned_rows),
        'reminder_count': reminder_count,
        'escalation_count': escalation_count,
        'pending_list': pending_list,
        'returned_list': returned_list,
        'reminder_list': reminder_list,
        'shift_health': _health(
            scheduled_count=scheduled_count,
            returned_count=len(returned_rows),
            pending_count=pending_count,
        ),
    }
