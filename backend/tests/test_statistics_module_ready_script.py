from importlib.util import module_from_spec, spec_from_file_location

from app.config import Settings
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_statistics_module_ready.py'


def _load_script_module():
    spec = spec_from_file_location('check_statistics_module_ready_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'WORKFLOW_ENABLED': True,
        'AUTO_PUBLISH_ENABLED': True,
        'AUTO_PUSH_ENABLED': True,
        'WECOM_APP_ENABLED': True,
        'WECOM_CORP_ID': 'corp-id',
        'WECOM_AGENT_ID': '1000002',
        'WECOM_APP_SECRET': 'secret',
        'LLM_ENABLED': True,
        'LLM_API_BASE': 'https://example.invalid/llm',
        'LLM_API_KEY': 'llm-key',
        'LLM_MODEL': 'gpt-5.4-mini',
        'APP_CONNECTION_ENABLED': True,
        'APP_CONNECTION_PUSH_MODE': 'enabled',
        'APP_CONNECTION_API_BASE': 'https://example.invalid/app-connection',
        'APP_CONNECTION_API_KEY': 'app-key',
    }
    values.update(overrides)
    return Settings(**values)


class _DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _query):
        return 1


def _sessionmaker_ok():
    return _DummySession()


def test_inspect_statistics_module_ready_passes_with_minimum_valid_setup() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(),
        sessionmaker_factory=_sessionmaker_ok,
    )

    assert payload['local_runnable'] is True
    assert payload['module_usable'] is True
    assert payload['external_connection_enabled'] is True
    assert payload['hard_gate_passed'] is True
    assert payload['hard_issues'] == []


def test_inspect_statistics_module_ready_allows_dry_run_app_connection_but_flags_external_not_enabled() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(
            APP_CONNECTION_PUSH_MODE='dry_run',
            APP_CONNECTION_API_BASE=None,
            APP_CONNECTION_API_KEY=None,
        ),
        sessionmaker_factory=_sessionmaker_ok,
    )

    assert payload['module_usable'] is True
    assert payload['external_connection_enabled'] is False
    assert any(item['code'] == 'APP_CONNECTION_DRY_RUN_ONLY' for item in payload['warning_issues'])


def test_inspect_statistics_module_ready_reports_hard_issues_when_required_integrations_are_disabled() -> None:
    module = _load_script_module()

    payload = module.inspect_statistics_module_ready(
        runtime_settings=_build_settings(
            WORKFLOW_ENABLED=False,
            LLM_ENABLED=False,
            WECOM_APP_ENABLED=False,
            APP_CONNECTION_ENABLED=False,
        ),
        sessionmaker_factory=_sessionmaker_ok,
    )

    assert payload['module_usable'] is False
    assert any(item['code'] == 'WORKFLOW_DISABLED' for item in payload['hard_issues'])
    assert any(item['code'] == 'LLM_DISABLED' for item in payload['hard_issues'])
    assert any(item['code'] == 'WECOM_APP_DISABLED' for item in payload['hard_issues'])
    assert any(item['code'] == 'APP_CONNECTION_DISABLED' for item in payload['hard_issues'])
