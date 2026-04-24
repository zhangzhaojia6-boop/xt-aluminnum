from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.permissions import (
    assert_manage_override_access,
    assert_manager_dashboard_access,
    assert_review_access,
)


def _user(**overrides):
    payload = {
        'id': 31,
        'role': 'reviewer',
        'workshop_id': 1,
        'team_id': 10,
        'data_scope_type': 'self_team',
        'assigned_shift_ids': None,
        'is_mobile_user': False,
        'is_reviewer': True,
        'is_manager': False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_team_reviewer_cannot_review_outside_scope() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_review_access(_user(), workshop_id=1, team_id=20, shift_id=1)

    assert exc.value.status_code == 403


def test_workshop_reviewer_can_review_same_workshop() -> None:
    assert_review_access(
        _user(data_scope_type='self_workshop', team_id=None),
        workshop_id=1,
        team_id=20,
        shift_id=2,
    )


def test_admin_can_execute_override_actions() -> None:
    assert_manage_override_access(
        _user(
            role='admin',
            workshop_id=None,
            team_id=None,
            data_scope_type='all',
            is_reviewer=True,
            is_manager=True,
        )
    )


def test_reviewer_cannot_enter_manager_dashboard_entry() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_manager_dashboard_access(_user(), workshop_id=1)

    assert exc.value.status_code == 403


def test_manager_can_enter_dashboard_within_scope() -> None:
    summary = assert_manager_dashboard_access(
        _user(
            role='manager',
            is_reviewer=False,
            is_manager=True,
            data_scope_type='self_workshop',
            team_id=None,
        ),
        workshop_id=1,
    )

    assert summary.is_manager is True
