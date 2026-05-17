from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.check_llm_live import inspect_llm_live
from scripts.check_statistics_module_ready import inspect_statistics_module_ready
from scripts.dingtalk_cli import check_access_token, check_department_contacts, send_test_notification


PLAN_READINESS_BLOCKER_CODES = {
    'DATABASE_UNAVAILABLE',
    'MES_UNCONFIGURED',
    'MES_REST_CONFIG_MISSING',
    'MES_MVC_CONFIG_MISSING',
    'WORKFLOW_DISABLED',
    'LIVE_AGGREGATION_UNAVAILABLE',
}


def _truthy(payload: dict[str, Any], key: str = 'ok') -> bool:
    return bool(payload.get(key))


def _blocker(code: str, message: str) -> dict[str, str]:
    return {'code': code, 'message': message}


def _required_dingtalk_user_payload() -> dict[str, Any]:
    return {
        'ok': False,
        'configured': True,
        'userid_masked': None,
        'message': 'A real DingTalk userid is required for send-test.',
    }


def _plan_readiness_blockers(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    issues = readiness.get('hard_issues', [])
    return [
        item
        for item in issues
        if str(item.get('code') or '') in PLAN_READINESS_BLOCKER_CODES
    ]


def inspect_backend_completion_gate(
    *,
    dingtalk_userid: str | None = None,
    dingtalk_department_id: int = 1,
    message: str = '数据中枢后端完全体联通测试',
    readiness_func: Callable[..., dict[str, Any]] = inspect_statistics_module_ready,
    llm_func: Callable[..., dict[str, Any]] = inspect_llm_live,
    dingtalk_token_func: Callable[[], dict[str, Any]] = check_access_token,
    dingtalk_contacts_func: Callable[..., dict[str, Any]] = check_department_contacts,
    dingtalk_send_func: Callable[..., dict[str, Any]] = send_test_notification,
) -> dict[str, Any]:
    readiness = readiness_func(check_live_aggregation=True, check_dingtalk_contacts=True)
    llm_live = llm_func()
    dingtalk_token = dingtalk_token_func()
    dingtalk_contacts = dingtalk_contacts_func(department_id=dingtalk_department_id)

    user_id = str(dingtalk_userid or '').strip()
    if user_id:
        dingtalk_send_test = dingtalk_send_func(user_id, message=message)
    else:
        dingtalk_send_test = _required_dingtalk_user_payload()

    blockers: list[dict[str, str]] = []
    readiness_blockers = _plan_readiness_blockers(readiness)
    if readiness_blockers:
        suffix = ','.join(str(item.get('code')) for item in readiness_blockers)
        blockers.append(_blocker('READINESS_GATE_FAILED', suffix or 'readiness gate failed'))
    if not (_truthy(llm_live) and bool(llm_live.get('response_received'))):
        blockers.append(_blocker('LLM_LIVE_FAILED', 'live LLM response was not received'))
    if not _truthy(dingtalk_token):
        blockers.append(_blocker('DINGTALK_TOKEN_FAILED', 'DingTalk token check failed'))
    if not user_id:
        blockers.append(_blocker('DINGTALK_TEST_USER_REQUIRED', 'real DingTalk userid is required'))
    elif not _truthy(dingtalk_send_test):
        blockers.append(_blocker('DINGTALK_SEND_TEST_FAILED', 'DingTalk send-test failed'))

    return {
        'ok': not blockers,
        'blockers': blockers,
        'checks': {
            'readiness': readiness,
            'llm_live': llm_live,
            'dingtalk_token': dingtalk_token,
            'dingtalk_contacts': dingtalk_contacts,
            'dingtalk_send_test': dingtalk_send_test,
        },
    }


def main(
    argv: list[str] | None = None,
    *,
    readiness_func: Callable[..., dict[str, Any]] = inspect_statistics_module_ready,
    llm_func: Callable[..., dict[str, Any]] = inspect_llm_live,
    dingtalk_token_func: Callable[[], dict[str, Any]] = check_access_token,
    dingtalk_contacts_func: Callable[..., dict[str, Any]] = check_department_contacts,
    dingtalk_send_func: Callable[..., dict[str, Any]] = send_test_notification,
) -> int:
    parser = argparse.ArgumentParser(description='Run backend completion live gate checks.')
    parser.add_argument('--json', action='store_true', help='Print JSON output.')
    parser.add_argument('--dingtalk-userid', default=None, help='Real DingTalk userid for send-test.')
    parser.add_argument('--dingtalk-department-id', type=int, default=1, help='DingTalk department id.')
    parser.add_argument('--message', default='数据中枢后端完全体联通测试', help='DingTalk send-test message.')
    args = parser.parse_args(argv)

    payload = inspect_backend_completion_gate(
        dingtalk_userid=args.dingtalk_userid,
        dingtalk_department_id=args.dingtalk_department_id,
        message=args.message,
        readiness_func=readiness_func,
        llm_func=llm_func,
        dingtalk_token_func=dingtalk_token_func,
        dingtalk_contacts_func=dingtalk_contacts_func,
        dingtalk_send_func=dingtalk_send_func,
    )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"backend_completion_gate={'ok' if payload['ok'] else 'blocked'}")
        for blocker in payload['blockers']:
            print(f"- [{blocker['code']}] {blocker['message']}")
    return 0 if payload['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
