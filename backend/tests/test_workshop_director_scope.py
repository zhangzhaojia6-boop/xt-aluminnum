from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.permissions import assert_manager_dashboard_access
from app.core.scope import build_scope_summary, resolve_work_order_entry_workshop_scope


def _user(**overrides):
    data = {
        'id': 1,
        'role': 'workshop_director',
        'workshop_id': 10,
        'team_id': None,
        'data_scope_type': 'self_team',
        'assigned_shift_ids': [],
        'is_mobile_user': False,
        'is_reviewer': False,
        'is_manager': False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_workshop_director_is_manager_but_scoped_to_own_workshop() -> None:
    summary = build_scope_summary(_user())

    assert summary.is_manager is True
    assert summary.data_scope_type == 'self_workshop'
    assert resolve_work_order_entry_workshop_scope(summary) == 10


def test_workshop_director_dashboard_denies_other_workshop() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_manager_dashboard_access(_user(), workshop_id=11)

    assert exc.value.status_code == 403


def test_workshop_director_without_workshop_is_denied_dashboard_scope() -> None:
    with pytest.raises(HTTPException) as exc:
        assert_manager_dashboard_access(_user(workshop_id=None), workshop_id=None)

    assert exc.value.status_code == 403
