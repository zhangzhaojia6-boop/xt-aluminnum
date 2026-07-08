from __future__ import annotations

import json
import os
import subprocess
import sys

from app.config import Settings
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'hermes_dingtalk_stream_gateway.py'


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
