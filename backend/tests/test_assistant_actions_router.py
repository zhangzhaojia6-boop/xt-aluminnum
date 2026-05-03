from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app


def test_assistant_action_router_executes_service(monkeypatch) -> None:
    seen = {}

    def fake_get_db():
        yield 'db'

    def fake_user():
        return SimpleNamespace(id=7, role='admin', name='Admin')

    def fake_execute_action(*, db, user, action_payload):
        seen['db'] = db
        seen['user_id'] = user.id
        seen['payload'] = action_payload
        return {'decisions': [{'action': 'auto_reconcile'}]}

    monkeypatch.setattr('app.routers.assistant_actions.assistant_action_service.execute_action', fake_execute_action)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_user
    try:
        response = TestClient(app).post(
            '/api/v1/assistant/actions',
            json={'action': 'call_reconciler', 'target_type': 'business_date', 'target_id': '2026-05-03'},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['decisions'][0]['action'] == 'auto_reconcile'
    assert seen['db'] == 'db'
    assert seen['user_id'] == 7

