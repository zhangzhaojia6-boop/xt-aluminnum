from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json

from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_backend_completion_gate.py'


def _load_script_module():
    spec = spec_from_file_location('check_backend_completion_gate_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ready_payload(**overrides):
    payload = {
        'hard_gate_passed': True,
        'hard_issues': [],
        'warning_issues': [],
        'stats': {'mes_ready': True},
    }
    payload.update(overrides)
    return payload


def test_backend_completion_gate_requires_real_dingtalk_userid() -> None:
    module = _load_script_module()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError('send-test must not run without a real DingTalk userid')

    payload = module.inspect_backend_completion_gate(
        readiness_func=lambda **_kwargs: _ready_payload(),
        llm_func=lambda **_kwargs: {'ok': True, 'response_received': True},
        dingtalk_token_func=lambda: {'ok': True, 'token_received': True},
        dingtalk_contacts_func=lambda **_kwargs: {'ok': True, 'department_access': True},
        dingtalk_send_func=fail_if_called,
    )

    assert payload['ok'] is False
    assert payload['checks']['dingtalk_send_test']['ok'] is False
    assert payload['checks']['dingtalk_send_test']['configured'] is True
    assert payload['blockers'][0]['code'] == 'DINGTALK_TEST_USER_REQUIRED'


def test_backend_completion_gate_passes_only_when_all_live_checks_pass() -> None:
    module = _load_script_module()

    payload = module.inspect_backend_completion_gate(
        dingtalk_userid='dt-user-secret',
        readiness_func=lambda **_kwargs: _ready_payload(),
        llm_func=lambda **_kwargs: {'ok': True, 'response_received': True},
        dingtalk_token_func=lambda: {'ok': True, 'token_received': True},
        dingtalk_contacts_func=lambda **_kwargs: {'ok': True, 'department_access': True},
        dingtalk_send_func=lambda userid, **_kwargs: {
            'ok': True,
            'configured': True,
            'userid_masked': 'dt-***ret',
            'detail': 'dingtalk_sent',
        },
    )

    assert payload['ok'] is True
    assert payload['blockers'] == []
    assert payload['checks']['llm_live']['response_received'] is True
    assert payload['checks']['dingtalk_send_test']['userid_masked'] == 'dt-***ret'


def test_backend_completion_gate_ignores_readiness_items_outside_backend_plan() -> None:
    module = _load_script_module()

    payload = module.inspect_backend_completion_gate(
        dingtalk_userid='dt-user-secret',
        readiness_func=lambda **_kwargs: _ready_payload(
            hard_gate_passed=False,
            hard_issues=[
                {'code': 'LLM_DISABLED'},
                {'code': 'APP_CONNECTION_DISABLED'},
            ],
            warning_issues=[
                {'code': 'DINGTALK_CONTACTS_PERMISSION_MISSING'},
            ],
        ),
        llm_func=lambda **_kwargs: {'ok': True, 'response_received': True},
        dingtalk_token_func=lambda: {'ok': True, 'token_received': True},
        dingtalk_contacts_func=lambda **_kwargs: {
            'ok': False,
            'department_access': False,
            'missing_scope': 'qyapi_get_department_member',
        },
        dingtalk_send_func=lambda userid, **_kwargs: {
            'ok': True,
            'configured': True,
            'userid_masked': 'dt-***ret',
        },
    )

    assert payload['ok'] is True
    assert payload['blockers'] == []
    assert payload['checks']['dingtalk_contacts']['department_access'] is False


def test_backend_completion_gate_blocks_plan_readiness_failures() -> None:
    module = _load_script_module()

    payload = module.inspect_backend_completion_gate(
        dingtalk_userid='dt-user-secret',
        readiness_func=lambda **_kwargs: _ready_payload(
            hard_gate_passed=False,
            hard_issues=[
                {'code': 'MES_UNCONFIGURED'},
                {'code': 'APP_CONNECTION_DISABLED'},
            ],
        ),
        llm_func=lambda **_kwargs: {'ok': True, 'response_received': True},
        dingtalk_token_func=lambda: {'ok': True, 'token_received': True},
        dingtalk_contacts_func=lambda **_kwargs: {'ok': True, 'department_access': True},
        dingtalk_send_func=lambda userid, **_kwargs: {'ok': True, 'configured': True},
    )

    assert payload['ok'] is False
    assert payload['blockers'] == [
        {'code': 'READINESS_GATE_FAILED', 'message': 'MES_UNCONFIGURED'}
    ]


def test_main_json_does_not_print_raw_dingtalk_userid_or_secret(capsys) -> None:
    module = _load_script_module()

    exit_code = module.main(
        ['--json', '--dingtalk-userid', 'dt-user-secret'],
        readiness_func=lambda **_kwargs: _ready_payload(),
        llm_func=lambda **_kwargs: {'ok': True, 'response_received': True, 'content_preview': 'OK'},
        dingtalk_token_func=lambda: {'ok': True, 'token_received': True, 'token_length': 32},
        dingtalk_contacts_func=lambda **_kwargs: {'ok': True, 'department_access': True},
        dingtalk_send_func=lambda userid, **_kwargs: {
            'ok': True,
            'configured': True,
            'userid_masked': 'dt-***ret',
            'detail': 'dingtalk_sent',
        },
    )

    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload['ok'] is True
    assert 'dt-user-secret' not in output
