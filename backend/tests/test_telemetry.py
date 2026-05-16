from fastapi.testclient import TestClient
import json
import logging

from app.core.logging import JsonLogFormatter
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


def test_json_log_formatter_outputs_structured_payload():
    record = logging.LogRecord(
        name='app.telemetry',
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg='frontend_error',
        args=(),
        exc_info=None,
    )
    record.telemetry = {'message': 'boom', 'url': '/dashboard'}

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload['level'] == 'WARNING'
    assert payload['message'] == 'frontend_error'
    assert payload['telemetry'] == {'message': 'boom', 'url': '/dashboard'}
