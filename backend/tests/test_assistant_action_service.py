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
