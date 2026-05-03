from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app


def test_team_lead_overview_router_allows_leader_roles(monkeypatch) -> None:
    seen = {}

    def fake_get_db():
        yield 'db'

    def fake_user():
        return SimpleNamespace(id=7, role='team_leader', workshop_id=1, team_id=10)

    def fake_build_overview(db, *, leader_user, target_date):
        seen['db'] = db
        seen['leader_id'] = leader_user.id
        seen['date'] = target_date
        return {
            'scheduled_count': 1,
            'attended_count': 1,
            'reported_count': 0,
            'returned_count': 0,
            'reminder_count': 0,
            'escalation_count': 0,
            'pending_list': [],
            'returned_list': [],
            'reminder_list': [],
            'shift_health': 'green',
        }

    monkeypatch.setattr('app.routers.team_lead.team_lead_service.build_overview', fake_build_overview)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_user
    try:
        response = TestClient(app).get('/api/v1/team-lead/overview', params={'date': '2026-05-03'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['shift_health'] == 'green'
    assert seen == {'db': 'db', 'leader_id': 7, 'date': date(2026, 5, 3)}


def test_team_lead_overview_router_rejects_worker_role(monkeypatch) -> None:
    def fake_get_db():
        yield 'db'

    def fake_user():
        return SimpleNamespace(id=8, role='mobile_user')

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_user
    try:
        response = TestClient(app).get('/api/v1/team-lead/overview', params={'date': '2026-05-03'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
