from fastapi.testclient import TestClient

from app.main import app


def test_alloy_grades_returns_list():
    client = TestClient(app)
    resp = client.get("/api/config/alloy-grades")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "5052" in data
    assert "3003" in data


def test_material_states_returns_list():
    client = TestClient(app)
    resp = client.get("/api/config/material-states")
    assert resp.status_code == 200
    data = resp.json()
    assert "O" in data
    assert "H14" in data
