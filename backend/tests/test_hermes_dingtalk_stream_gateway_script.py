from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
import json
import os
import subprocess
import sys

from app.config import Settings
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'hermes_dingtalk_stream_gateway.py'


def _load_script_module():
    spec = spec_from_file_location('hermes_dingtalk_stream_gateway_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_settings(**overrides) -> Settings:
    values = {
        '_env_file': None,
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'DINGTALK_STREAM_ENABLED': False,
        'DINGTALK_APP_KEY': None,
        'DINGTALK_APP_SECRET': None,
        'DINGTALK_AUTHORIZED_GROUP_IDS': '',
    }
    values.update(overrides)
    return Settings(**values)


def test_build_health_payload_reports_disabled_when_stream_disabled() -> None:
    module = _load_script_module()

    payload = module.build_health_payload(runtime_settings=build_settings())

    assert payload == {'status': 'disabled', 'stream_enabled': False}


def test_main_health_exits_cleanly_when_stream_disabled_without_subprocess() -> None:
    module = _load_script_module()
    captured = StringIO()

    exit_code = module.main(
        ['--health'],
        runtime_settings=build_settings(),
        stdout=captured,
    )

    assert exit_code == 0
    assert json.loads(captured.getvalue()) == {'status': 'disabled', 'stream_enabled': False}


def test_main_without_health_returns_exit_code_2_and_writes_stderr() -> None:
    module = _load_script_module()
    captured_stderr = StringIO()

    exit_code = module.main(
        [],
        runtime_settings=build_settings(),
        stderr=captured_stderr,
    )

    assert exit_code == 2
    assert 'Stream runtime is not implemented yet' in captured_stderr.getvalue()


def test_stream_gateway_health_exits_cleanly_when_stream_disabled() -> None:
    env = os.environ.copy()
    env.update(
        {
            'PYTHONPATH': '.',
            'APP_ENV': 'development',
            'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
            'SECRET_KEY': 's' * 32,
            'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
            'DINGTALK_STREAM_ENABLED': 'false',
        }
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--health'],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'status': 'disabled', 'stream_enabled': False}


def test_stream_config_requires_app_credentials_when_enabled() -> None:
    settings = build_settings(
        DINGTALK_STREAM_ENABLED=True,
        DINGTALK_AUTHORIZED_GROUP_IDS='cid-group-1',
    )

    issues = settings.validate_runtime()

    assert 'DINGTALK_STREAM_ENABLED requires DINGTALK_APP_KEY and DINGTALK_APP_SECRET' in issues


def test_stream_config_requires_authorized_group_ids_when_enabled() -> None:
    settings = build_settings(
        DINGTALK_STREAM_ENABLED=True,
        DINGTALK_APP_KEY='ding-app-key',
        DINGTALK_APP_SECRET='ding-app-secret',
    )

    issues = settings.validate_runtime()
    issues_text = ' '.join(issues)

    assert 'DINGTALK_STREAM_ENABLED requires at least one DINGTALK_AUTHORIZED_GROUP_IDS entry' in issues
    assert 'ding-app-secret' not in issues_text


def test_stream_config_rejects_too_small_file_text_limit() -> None:
    settings = build_settings(DINGTALK_FILE_TEXT_MAX_BYTES=1023)

    issues = settings.validate_runtime()

    assert 'DINGTALK_FILE_TEXT_MAX_BYTES must be greater than or equal to 1024' in issues


def test_stream_config_rejects_backfill_days_outside_allowed_range() -> None:
    settings = build_settings(DINGTALK_BACKFILL_DAYS=0)

    issues = settings.validate_runtime()

    assert 'DINGTALK_BACKFILL_DAYS must be between 1 and 7' in issues


def test_dingtalk_robot_code_falls_back_to_empty_string() -> None:
    settings = build_settings(DINGTALK_ROBOT_CODE='', DINGTALK_APP_KEY=None)

    assert settings.dingtalk_robot_code == ''
