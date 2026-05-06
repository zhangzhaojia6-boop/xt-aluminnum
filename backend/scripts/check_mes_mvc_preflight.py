"""Safe MES MVC connectivity preflight.

This command is intentionally read-only and never prints credentials. Use
`--attempt-login` only after the production `.env` has the MES MVC fields.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters.mvc_mes_adapter import MvcMesAdapter
from app.config import Settings, settings


def _is_blank(value: str | None) -> bool:
    return value is None or not str(value).strip()


def _sender(**kwargs) -> httpx.Response:
    return httpx.request(**kwargs)


def _missing_mvc_env(runtime: Settings) -> list[str]:
    missing: list[str] = []
    adapter = (runtime.MES_ADAPTER or 'null').strip().lower()
    if adapter != 'mvc':
        missing.append('MES_ADAPTER')
    for name in ('MES_MVC_BASE_URL', 'MES_MVC_USERNAME', 'MES_MVC_PASSWORD'):
        if _is_blank(getattr(runtime, name)):
            missing.append(name)
    return missing


def inspect_mes_mvc_preflight(
    *,
    runtime_settings: Settings | None = None,
    sender=None,
    attempt_login: bool = False,
) -> dict[str, Any]:
    runtime = runtime_settings or settings
    request_sender = sender or _sender
    adapter_name = (runtime.MES_ADAPTER or 'null').strip().lower()
    missing_env = _missing_mvc_env(runtime)
    base_url = str(runtime.MES_MVC_BASE_URL or '').strip()
    payload: dict[str, Any] = {
        'adapter': adapter_name,
        'mvc_configured': not missing_env,
        'missing_env': missing_env,
        'login_page': {
            'status': 'skipped',
            'token_present': False,
        },
        'login': {
            'status': 'skipped',
        },
    }

    if _is_blank(base_url):
        payload['login_page']['reason'] = 'missing_base_url'
        payload['login']['reason'] = 'missing_config'
        return payload

    adapter = MvcMesAdapter(
        base_url=base_url,
        username=str(runtime.MES_MVC_USERNAME or ''),
        password=str(runtime.MES_MVC_PASSWORD or ''),
        timeout_seconds=runtime.MES_MVC_TIMEOUT_SECONDS,
        sender=request_sender,
    )

    try:
        token = adapter._ensure_request_verification_token()
    except Exception as exc:  # noqa: BLE001 - diagnostic command reports class only
        payload['login_page'] = {
            'status': 'failed',
            'token_present': False,
            'error': exc.__class__.__name__,
        }
        payload['login']['reason'] = 'login_page_unavailable'
        return payload

    payload['login_page'] = {
        'status': 'reachable',
        'token_present': bool(token),
    }

    if not attempt_login:
        payload['login']['reason'] = 'not_requested'
        return payload

    if missing_env:
        payload['login']['reason'] = 'missing_config'
        return payload

    try:
        adapter._login()
    except Exception as exc:  # noqa: BLE001 - diagnostic command reports class only
        payload['login'] = {
            'status': 'failed',
            'error': exc.__class__.__name__,
        }
        return payload

    payload['login'] = {'status': 'success'}
    return payload


def _print_text(payload: dict[str, Any]) -> None:
    print(f"MES MVC adapter: {payload['adapter']}")
    print(f"MVC configured: {str(payload['mvc_configured']).lower()}")
    if payload['missing_env']:
        print(f"Missing env: {', '.join(payload['missing_env'])}")
    print(
        'Login page: '
        f"{payload['login_page']['status']}, "
        f"token_present={str(payload['login_page'].get('token_present', False)).lower()}"
    )
    print(f"Login: {payload['login']['status']}")
    if payload['login'].get('reason'):
        print(f"Login reason: {payload['login']['reason']}")
    if payload['login'].get('error'):
        print(f"Login error: {payload['login']['error']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Check MES MVC configuration and connectivity without printing secrets.')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    parser.add_argument('--attempt-login', action='store_true', help='Attempt MES login using configured credentials.')
    args = parser.parse_args(argv)

    payload = inspect_mes_mvc_preflight(attempt_login=args.attempt_login)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
