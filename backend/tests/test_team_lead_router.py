from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_team_lead_router_is_not_mounted() -> None:
    response = TestClient(app).get('/api/v1/team-lead/overview', params={'date': '2026-05-03'})

    assert response.status_code == 404
