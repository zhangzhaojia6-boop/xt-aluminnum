from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.attendance import AttendanceSchedule
from app.models.master import Employee, Team, Workshop
from app.models.shift import ShiftConfig


TEAM_OWNER_TEMPLATES = (
    ('OP', '主操'),
    ('EN', '电工班长'),
    ('MT', '机修班长'),
    ('HY', '液压班长'),
    ('QC', '质检责任人'),
    ('PLAN', '合同责任人'),
)

WAREHOUSE_OWNER_TEMPLATES = (
    ('INV', '成品库负责人'),
    ('PLAN', '计划科负责人'),
    ('UTILITY', '水电气负责人'),
)


def current_business_date() -> date:
    return datetime.now(ZoneInfo(settings.DEFAULT_TIMEZONE)).date()


def _team_shift_code(team: Team | None) -> str | None:
    if team is None or not team.code:
        return None
    parts = str(team.code).split('-')
    if len(parts) < 2:
        return None
    return parts[-1].strip().upper() or None


def _owner_templates_for_workshop(workshop: Workshop) -> tuple[tuple[str, str], ...]:
    if workshop.code == 'CPK':
        return WAREHOUSE_OWNER_TEMPLATES
    return TEAM_OWNER_TEMPLATES


def _resolve_schedule_teams(workshop: Workshop, teams: list[Team]) -> list[Team | None]:
    workshop_teams = [item for item in teams if item.workshop_id == workshop.id]
    workshop_teams.sort(key=lambda item: (item.sort_order, item.id))
    return workshop_teams or [None]


def seed_default_pilot_schedule(db: Session, *, target_date: date | None = None) -> int:
    resolved_date = target_date or current_business_date()

    shifts = db.execute(
        select(ShiftConfig)
        .where(ShiftConfig.is_active.is_(True))
        .order_by(ShiftConfig.sort_order.asc(), ShiftConfig.id.asc())
    ).scalars().all()
    if not shifts:
        return 0
    default_shift = shifts[0]
    shifts_by_code = {str(item.code).strip().upper(): item for item in shifts}

    workshops = db.execute(
        select(Workshop)
        .where(Workshop.is_active.is_(True))
        .order_by(Workshop.sort_order.asc(), Workshop.id.asc())
    ).scalars().all()
    if not workshops:
        return 0

    teams = db.execute(select(Team).where(Team.is_active.is_(True))).scalars().all()
    existing_employees = {item.employee_no: item for item in db.execute(select(Employee)).scalars().all()}

    created_or_updated = 0
    for workshop in workshops:
        owner_templates = _owner_templates_for_workshop(workshop)
        for team in _resolve_schedule_teams(workshop, teams):
            shift_code = _team_shift_code(team)
            scheduled_shift = shifts_by_code.get(shift_code or '', default_shift)
            shift_label = team.name if team is not None else scheduled_shift.name

            for role_code, role_label in owner_templates:
                suffix = shift_code or scheduled_shift.code
                employee_no = f'PILOT-{workshop.code}-{suffix}-{role_code}'
                employee = existing_employees.get(employee_no)
                employee_name = f'{workshop.name}{shift_label}{role_label}'
                if employee is None:
                    employee = Employee(
                        employee_no=employee_no,
                        name=employee_name,
                        workshop_id=workshop.id,
                        team_id=team.id if team else None,
                        is_active=True,
                    )
                    db.add(employee)
                    db.flush()
                    existing_employees[employee_no] = employee
                    created_or_updated += 1
                else:
                    employee.name = employee_name
                    employee.workshop_id = workshop.id
                    employee.team_id = team.id if team else None
                    employee.is_active = True

                schedule = db.execute(
                    select(AttendanceSchedule).where(
                        AttendanceSchedule.employee_id == employee.id,
                        AttendanceSchedule.business_date == resolved_date,
                    )
                ).scalar_one_or_none()
                if schedule is None:
                    schedule = AttendanceSchedule(
                        employee_id=employee.id,
                        business_date=resolved_date,
                        shift_config_id=scheduled_shift.id,
                        team_id=team.id if team else None,
                        workshop_id=workshop.id,
                        source='bootstrap',
                        is_rest_day=False,
                    )
                    db.add(schedule)
                    created_or_updated += 1
                    continue

                schedule.shift_config_id = scheduled_shift.id
                schedule.team_id = team.id if team else None
                schedule.workshop_id = workshop.id
                schedule.source = 'bootstrap'
                schedule.is_rest_day = False

    db.commit()
    return created_or_updated
