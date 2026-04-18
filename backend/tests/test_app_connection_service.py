from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.config import Settings
from app.services import app_connection_service


class _FakeResponse:
    def __init__(self, *, status_code: int):
        self.status_code = status_code


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self._response = response

    def post(self, *_args, **_kwargs):
        return self._response


def _build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'WORKFLOW_ENABLED': True,
        'APP_CONNECTION_ENABLED': True,
        'APP_CONNECTION_PUSH_MODE': 'dry_run',
    }
    values.update(overrides)
    return Settings(**values)


def _build_report():
    return SimpleNamespace(
        id=99,
        report_date=date(2026, 4, 10),
        status='published',
        generated_scope='auto_confirmed',
        published_at=datetime(2026, 4, 10, 8, 0, tzinfo=UTC),
        generated_at=None,
        updated_at=None,
    )


def test_build_app_connection_payload_contains_contract_fields() -> None:
    payload = app_connection_service.build_app_connection_payload(
        report=_build_report(),
        report_data={'total_output_weight': 180.0},
        leader_summary_text='摘要',
        summary_source='deterministic',
    )

    assert payload['payload_version'] == 1
    assert payload['dispatch_key'].startswith('report:99:')
    assert payload['report_date'] == '2026-04-10'
    assert payload['summary_source'] == 'deterministic'
    assert payload['leader_summary'] == '摘要'


def test_dispatch_app_connection_payload_returns_dry_run_without_network() -> None:
    result = app_connection_service.dispatch_app_connection_payload(
        payload={'payload_version': 1},
        settings=_build_settings(APP_CONNECTION_PUSH_MODE='dry_run'),
    )

    assert result['status'] == 'dry_run'
    assert result['detail'] == 'payload_recorded_without_network'


def test_dispatch_app_connection_payload_sends_when_enabled() -> None:
    result = app_connection_service.dispatch_app_connection_payload(
        payload={'payload_version': 1},
        settings=_build_settings(
            APP_CONNECTION_PUSH_MODE='enabled',
            APP_CONNECTION_API_BASE='https://example.invalid/app',
            APP_CONNECTION_API_KEY='app-key',
        ),
        client=_FakeClient(_FakeResponse(status_code=202)),
    )

    assert result['status'] == 'sent'
    assert result['http_status'] == 202
