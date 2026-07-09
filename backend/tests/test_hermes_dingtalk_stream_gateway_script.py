from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
import json
import os
import subprocess
import sys

from app.config import Settings
from app.models import Base
from app.models.agent_communication import MultimodalEvidence
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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


def _db_sessionmaker():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)


def _sample_text_payload() -> dict:
    return {
        'data': {
            'conversationId': 'group-001',
            'conversationType': 'group',
            'messageId': 'msg-once-001',
            'senderStaffId': 'staff-001',
            'msgtype': 'text',
            'text': {'content': '今日日报：产量 32 吨'},
            'businessDate': '2026-07-07',
        }
    }


def test_build_health_payload_reports_disabled_when_stream_disabled() -> None:
    module = _load_script_module()

    payload = module.build_health_payload(runtime_settings=build_settings())

    assert payload == {'ok': True, 'enabled': False, 'mode': 'disabled'}


def test_main_health_exits_cleanly_when_stream_disabled_without_subprocess() -> None:
    module = _load_script_module()
    captured = StringIO()

    exit_code = module.main(
        ['--health'],
        runtime_settings=build_settings(),
        stdout=captured,
    )

    assert exit_code == 0
    assert json.loads(captured.getvalue()) == {'ok': True, 'enabled': False, 'mode': 'disabled'}


def test_main_without_health_returns_disabled_health_when_stream_disabled() -> None:
    module = _load_script_module()
    captured_stdout = StringIO()

    exit_code = module.main(
        [],
        runtime_settings=build_settings(),
        stdout=captured_stdout,
    )

    assert exit_code == 0
    assert json.loads(captured_stdout.getvalue()) == {'ok': True, 'enabled': False, 'mode': 'disabled'}


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
    assert json.loads(result.stdout) == {'ok': True, 'enabled': False, 'mode': 'disabled'}


def test_build_health_payload_reports_all_group_scope_for_wildcard() -> None:
    module = _load_script_module()

    payload = module.build_health_payload(
        runtime_settings=build_settings(
            DINGTALK_STREAM_ENABLED=True,
            DINGTALK_APP_KEY='ding-app-key',
            DINGTALK_APP_SECRET='ding-app-secret',
            DINGTALK_AUTHORIZED_GROUP_IDS='*',
        )
    )

    assert payload == {
        'ok': True,
        'enabled': True,
        'mode': 'stream',
        'authorized_group_count': 1,
        'authorized_group_scope': 'all',
    }


def test_once_json_ingests_sample_text_callback(monkeypatch, tmp_path) -> None:
    module = _load_script_module()
    Session = _db_sessionmaker()
    payload_path = tmp_path / 'payload.json'
    payload_path.write_text(json.dumps(_sample_text_payload(), ensure_ascii=False), encoding='utf-8')
    captured = StringIO()
    monkeypatch.setattr(module, 'get_sessionmaker', lambda: Session)
    monkeypatch.setattr(module.settings, 'DINGTALK_AUTHORIZED_GROUP_IDS', 'group-001', raising=False)

    exit_code = module.main(['--once-json', str(payload_path)], stdout=captured)

    assert exit_code == 0
    result = json.loads(captured.getvalue())
    assert result['accepted'] is True
    assert result['message_text'] is True
    db = Session()
    try:
        evidence = db.query(MultimodalEvidence).one()
        assert evidence.payload['message_text'] == '今日日报：产量 32 吨'
    finally:
        db.close()


def test_once_json_dry_run_does_not_write_evidence(tmp_path) -> None:
    module = _load_script_module()
    Session = _db_sessionmaker()
    payload_path = tmp_path / 'payload.json'
    payload_path.write_text(json.dumps(_sample_text_payload(), ensure_ascii=False), encoding='utf-8')
    captured = StringIO()

    exit_code = module.main(
        ['--once-json', str(payload_path), '--dry-run'],
        runtime_settings=build_settings(DINGTALK_AUTHORIZED_GROUP_IDS='group-001'),
        stdout=captured,
    )

    assert exit_code == 0
    result = json.loads(captured.getvalue())
    assert result['accepted'] is True
    assert result['dry_run'] is True
    assert result['would_write'] is True
    db = Session()
    try:
        assert db.query(MultimodalEvidence).count() == 0
    finally:
        db.close()


def test_missing_stream_dependency_exits_with_chinese_operator_message(monkeypatch) -> None:
    module = _load_script_module()
    captured_stderr = StringIO()

    def missing_sdk():
        raise ModuleNotFoundError('dingtalk_stream')

    monkeypatch.setattr(module, '_load_dingtalk_stream_sdk', missing_sdk)
    exit_code = module.main(
        [],
        runtime_settings=build_settings(
            DINGTALK_STREAM_ENABLED=True,
            DINGTALK_APP_KEY='ding-app-key',
            DINGTALK_APP_SECRET='super-secret-value',
            DINGTALK_AUTHORIZED_GROUP_IDS='group-001',
        ),
        stderr=captured_stderr,
    )

    assert exit_code == 2
    assert '缺少 dingtalk-stream 依赖' in captured_stderr.getvalue()
    assert 'super-secret-value' not in captured_stderr.getvalue()


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
