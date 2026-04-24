from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.permissions import assert_mobile_report_access


def _user(**overrides):
    payload = {
        'id': 11,
        'role': 'team_leader',
        'workshop_id': 1,
        'team_id': 10,
        'data_scope_type': 'self_team',
        'assigned_shift_ids': None,
        'is_mobile_user': True,
        'is_reviewer': False,
        'is_manager': False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _report(**overrides):
    payload = {
        'id': 7,
        'workshop_id': 1,
        'team_id': 10,
        'shift_config_id': 1,
        'owner_user_id': 11,
        'submitted_by_user_id': 11,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_mobile_user_cannot_view_other_team_report() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_mobile_report_access(
            _user(),
            report=_report(team_id=20, owner_user_id=22),
            write=False,
        )

    assert exc.value.status_code == 403


def test_mobile_user_cannot_modify_other_user_report() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_mobile_report_access(
            _user(),
            report=_report(owner_user_id=22, submitted_by_user_id=22),
            write=True,
        )

    assert exc.value.status_code == 403


def test_mobile_user_can_modify_own_report_within_scope() -> None:
    assert_mobile_report_access(
        _user(),
        report=_report(owner_user_id=11, submitted_by_user_id=11),
        write=True,
    )


def test_manager_cannot_use_mobile_report_access_without_mobile_role() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_mobile_report_access(
            _user(
                role='manager',
                is_mobile_user=False,
                is_manager=True,
                team_id=None,
                data_scope_type='self_workshop',
            ),
            report=_report(owner_user_id=11, submitted_by_user_id=11),
            write=False,
        )

    assert exc.value.status_code == 403
