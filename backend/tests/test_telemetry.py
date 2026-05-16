from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_telemetry_errors_endpoint():
    resp = client.post(
        '/api/v1/telemetry/errors',
        json={'message': 'test error', 'url': '/test'},
    )
    assert resp.status_code == 200
    assert resp.json() == {'received': True}


def test_telemetry_perf_endpoint():
    resp = client.post(
        '/api/v1/telemetry/perf',
        json={'route': '/dashboard', 'metric': 'lcp', 'value': 1200.5},
    )
    assert resp.status_code == 200
    assert resp.json() == {'received': True}


def test_telemetry_errors_rejects_invalid():
    resp = client.post('/api/v1/telemetry/errors', json={'message': 'x'})
    assert resp.status_code == 422
