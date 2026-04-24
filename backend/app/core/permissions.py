from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.config import settings
from app.core.deps import get_current_user
from app.core.scope import ScopeSummary, build_scope_summary
from app.models.system import User


def _forbidden(detail: str = 'Permission denied') -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _matches_scope(summary: ScopeSummary, *, workshop_id: int | None, team_id: int | None, shift_id: int | None = None) -> bool:
    if summary.is_admin or summary.data_scope_type == 'all':
        return True

    if summary.data_scope_type == 'assigned':
        if workshop_id is not None and summary.workshop_id is not None and summary.workshop_id != workshop_id:
            return False
        if summary.team_id is not None and team_id is not None and summary.team_id != team_id:
            return False
        if summary.assigned_shift_ids and shift_id is not None:
            return int(shift_id) in summary.assigned_shift_ids
        return summary.workshop_id is None or summary.workshop_id == workshop_id

    if summary.data_scope_type == 'self_workshop':
        return summary.workshop_id is not None and summary.workshop_id == workshop_id

    # self_team default
    return (
        summary.workshop_id is not None
        and summary.team_id is not None
        and summary.workshop_id == workshop_id
        and summary.team_id == team_id
    )


def assert_scope_access(
    current_user: User,
    *,
    workshop_id: int | None,
    team_id: int | None,
    shift_id: int | None = None,
) -> ScopeSummary:
    summary = build_scope_summary(current_user)
    if not _matches_scope(summary, workshop_id=workshop_id, team_id=team_id, shift_id=shift_id):
        raise _forbidden('Data scope denied')
    return summary


def assert_mobile_user_access(current_user: User) -> ScopeSummary:
    summary = build_scope_summary(current_user)
    allow_admin_debug = summary.is_admin and not settings.is_production_like
    if not summary.is_mobile_user and not allow_admin_debug:
        raise _forbidden('Mobile access denied')
    return summary


def assert_mobile_report_access(current_user: User, *, report, write: bool) -> ScopeSummary:
    summary = assert_mobile_user_access(current_user)
    assert_scope_access(
        current_user,
        workshop_id=getattr(report, 'workshop_id', None),
        team_id=getattr(report, 'team_id', None),
        shift_id=getattr(report, 'shift_config_id', None),
    )
    owner_user_id = getattr(report, 'owner_user_id', None)
    if owner_user_id is not None and owner_user_id != getattr(current_user, 'id', None) and not summary.is_admin:
        if not write:
            raise _forbidden('You cannot view another mobile user report')
        raise _forbidden('You cannot modify another mobile user report')
    return summary


def assert_reviewer_access(current_user: User) -> ScopeSummary:
    summary = build_scope_summary(current_user)
    if not summary.is_reviewer and not summary.is_admin:
        raise _forbidden('Reviewer access denied')
    return summary


def assert_review_access(
    current_user: User,
    *,
    workshop_id: int | None,
    team_id: int | None,
    shift_id: int | None = None,
) -> ScopeSummary:
    summary = assert_reviewer_access(current_user)
    if summary.is_admin:
        return summary
    if not _matches_scope(summary, workshop_id=workshop_id, team_id=team_id, shift_id=shift_id):
        raise _forbidden('Review scope denied')
    return summary


def assert_manager_access(current_user: User) -> ScopeSummary:
    summary = build_scope_summary(current_user)
    if not summary.is_manager and not summary.is_admin:
        raise _forbidden('Manager access denied')
    return summary


def assert_manager_dashboard_access(current_user: User, *, workshop_id: int | None = None) -> ScopeSummary:
    summary = assert_manager_access(current_user)
    if summary.is_admin or workshop_id is None or summary.data_scope_type == 'all':
        return summary
    if not _matches_scope(summary, workshop_id=workshop_id, team_id=None):
        raise _forbidden('Dashboard scope denied')
    return summary


def assert_manage_override_access(current_user: User) -> ScopeSummary:
    summary = build_scope_summary(current_user)
    if not summary.is_admin:
        raise _forbidden('Only admin can perform override actions')
    return summary


def get_current_mobile_user(current_user: User = Depends(get_current_user)) -> User:
    assert_mobile_user_access(current_user)
    return current_user


def get_current_reviewer_user(current_user: User = Depends(get_current_user)) -> User:
    assert_reviewer_access(current_user)
    return current_user


def get_current_manager_user(current_user: User = Depends(get_current_user)) -> User:
    assert_manager_access(current_user)
    return current_user
