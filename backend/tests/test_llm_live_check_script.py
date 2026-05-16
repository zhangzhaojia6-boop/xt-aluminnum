from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from types import SimpleNamespace
import json

from app.adapters.llm import LlmTextResponse
from app.config import Settings
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_llm_live.py'


def _load_script_module():
    spec = spec_from_file_location('check_llm_live_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'sqlite:///:memory:',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'LLM_ENABLED': True,
        'LLM_API_BASE': 'https://llm.example.invalid/v1',
        'LLM_API_KEY': 'real-secret-key',
        'LLM_MODEL': 'deepseek-v3',
    }
    values.update(overrides)
    return Settings(**values)


def test_llm_live_check_reports_missing_config_without_calling_api() -> None:
    module = _load_script_module()

    def fail_if_called(**_kwargs):
        raise AssertionError('LLM API should not be called without complete config')

    payload = module.inspect_llm_live(
        runtime_settings=_settings(LLM_ENABLED=False, LLM_API_KEY=None),
        summary_func=fail_if_called,
    )

    assert payload['ok'] is False
    assert payload['configured'] is False
    assert 'LLM_ENABLED' in payload['missing_env']
    assert 'LLM_API_KEY' in payload['missing_env']


def test_llm_live_check_reports_sanitized_success() -> None:
    module = _load_script_module()

    def fake_summary(**kwargs):
        assert kwargs['max_tokens'] == 64
        return LlmTextResponse(
            content='数据中枢 LLM 联通 OK',
            input_tokens=8,
            output_tokens=6,
            total_tokens=14,
            raw_usage={'prompt_tokens': 8, 'completion_tokens': 6, 'total_tokens': 14},
        )

    payload = module.inspect_llm_live(runtime_settings=_settings(), summary_func=fake_summary)

    assert payload['ok'] is True
    assert payload['configured'] is True
    assert payload['response_received'] is True
    assert payload['content_length'] == len('数据中枢 LLM 联通 OK')
    assert payload['usage'] == {'input_tokens': 8, 'output_tokens': 6, 'total_tokens': 14}


def test_main_json_does_not_print_api_key(capsys) -> None:
    module = _load_script_module()

    def fake_summary(**_kwargs):
        return LlmTextResponse(content='OK')

    exit_code = module.main(
        ['--json'],
        runtime_settings=_settings(),
        summary_func=fake_summary,
    )

    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload['ok'] is True
    assert 'real-secret-key' not in output
