from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.agents.base import AgentAction, AgentDecision
from app.services import assistant_action_service


class _FakeDB:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True


class _FakeQuery:
    def __init__(self, row) -> None:
        self.row = row

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.row


class _FakeScopedDB(_FakeDB):
    def __init__(self, *, report=None, shift=None) -> None:
        super().__init__()
        self.report = report
        self.shift = shift

    def query(self, model):
        model_name = getattr(model, '__name__', '')
        if model_name == 'MobileShiftReport':
            return _FakeQuery(self.report)
        if model_name == 'ShiftConfig':
            return _FakeQuery(self.shift)
        return _FakeQuery(None)


def test_execute_action_routes_to_registered_agent_and_logs(monkeypatch) -> None:
    events = []
    db = _FakeDB()

    def fake_handler(*, db, payload):
        assert isinstance(db, _FakeDB)
        assert payload['target_id'] == '2026-05-03'
        return [
            AgentDecision(
                agent_name='reconciler',
                action=AgentAction.AUTO_RECONCILE,
                target_type='business_date',
                target_id=20260503,
                reason='ok',
            )
        ]

    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {'call_reconciler': fake_handler})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda event_name, **fields: events.append((event_name, fields)),
    )

    result = assistant_action_service.execute_action(
        db=db,
        user=SimpleNamespace(id=7, role='manager'),
        action_payload={'action': 'call_reconciler', 'target_type': 'business_date', 'target_id': '2026-05-03'},
    )

    assert result['decisions'][0]['action'] == 'auto_reconcile'
    assert db.committed is True
    assert events[0][0] == 'assistant_action_invoked'
    assert events[0][1]['user_id'] == 7
    assert events[0][1]['success'] is True


def test_execute_action_rejects_non_manager_and_logs(monkeypatch) -> None:
    events = []
    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda event_name, **fields: events.append((event_name, fields)),
    )

    with pytest.raises(HTTPException) as exc:
        assistant_action_service.execute_action(
            db='db',
            user=SimpleNamespace(id=8, role='team_leader'),
            action_payload={'action': 'call_reconciler', 'target_type': 'business_date', 'target_id': '2026-05-03'},
        )

    assert exc.value.status_code == 403
    assert events[0][0] == 'assistant_action_invoked'
    assert events[0][1]['success'] is False


def test_execute_action_rejects_scoped_manager_outside_report(monkeypatch) -> None:
    called = False
    db = _FakeScopedDB(report=SimpleNamespace(id=91, workshop_id=2, team_id=20, shift_config_id=3))

    def fake_handler(*, db, payload):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {'call_validator': fake_handler})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda *args, **kwargs: None,
    )

    with pytest.raises(HTTPException) as exc:
        assistant_action_service.execute_action(
            db=db,
            user=SimpleNamespace(
                id=7,
                role='manager',
                workshop_id=1,
                team_id=None,
                data_scope_type='self_workshop',
                is_manager=True,
            ),
            action_payload={'action': 'call_validator', 'target_type': 'mobile_shift_report', 'target_id': 91},
        )

    assert exc.value.status_code == 403
    assert called is False
    assert db.committed is False


def test_execute_action_rejects_scoped_manager_global_date_action(monkeypatch) -> None:
    called = False

    def fake_handler(*, db, payload):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {'call_reconciler': fake_handler})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda *args, **kwargs: None,
    )

    with pytest.raises(HTTPException) as exc:
        assistant_action_service.execute_action(
            db=_FakeDB(),
            user=SimpleNamespace(
                id=7,
                role='manager',
                workshop_id=1,
                team_id=None,
                data_scope_type='self_workshop',
                is_manager=True,
            ),
            action_payload={'action': 'call_reconciler', 'target_type': 'business_date', 'target_id': '2026-05-03'},
        )

    assert exc.value.status_code == 403
    assert called is False


def test_execute_action_rejects_assigned_manager_unassigned_shift_reminder(monkeypatch) -> None:
    called = False
    db = _FakeScopedDB(shift=SimpleNamespace(id=5, workshop_id=1))

    def fake_handler(*, db, payload):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {'call_reminder': fake_handler})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda *args, **kwargs: None,
    )

    with pytest.raises(HTTPException) as exc:
        assistant_action_service.execute_action(
            db=db,
            user=SimpleNamespace(
                id=7,
                role='manager',
                workshop_id=1,
                team_id=None,
                data_scope_type='assigned',
                assigned_shift_ids=[1],
                is_manager=True,
            ),
            action_payload={
                'action': 'call_reminder',
                'target_type': 'shift_config',
                'target_id': 5,
                'target_date': '2026-05-03',
            },
        )

    assert exc.value.status_code == 403
    assert called is False
