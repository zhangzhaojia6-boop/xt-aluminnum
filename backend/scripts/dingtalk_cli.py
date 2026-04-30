from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services import dingtalk_service


DINGTALK_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ('DINGTALK_CORP_ID', 'corp_id', False),
    ('DINGTALK_APP_KEY', 'app_key', False),
    ('DINGTALK_APP_SECRET', 'app_secret', True),
    ('DINGTALK_AGENT_ID', 'agent_id', False),
)


def _is_blank(value: Any) -> bool:
    return value is None or not str(value).strip()


def _mask(value: Any, *, secret: bool = False) -> str | None:
    if _is_blank(value):
        return None
    if secret:
        return '***set***'

    text = str(value).strip()
    if len(text) <= 4:
        return '*' * len(text)
    if len(text) <= 8:
        return f'{text[:1]}***{text[-1:]}'
    return f'{text[:3]}***{text[-3:]}'


def _config_value(service: Any, field_name: str) -> Any:
    config = getattr(service, 'config', None)
    return getattr(config, field_name, None)


def build_status_payload(service: Any = dingtalk_service.service) -> dict[str, Any]:
    fields: dict[str, dict[str, Any]] = {}
    missing: list[str] = []

    for env_name, config_name, is_secret in DINGTALK_FIELDS:
        value = _config_value(service, config_name)
        is_set = not _is_blank(value)
        if not is_set:
            missing.append(env_name)
        fields[env_name] = {
            'set': is_set,
            'masked': _mask(value, secret=is_secret),
        }

    configured = bool(getattr(service, 'enabled', False)) and not missing
    return {
        'ok': configured,
        'configured': configured,
        'mode': 'dingtalk_h5' if configured else 'web_debug',
        'missing': missing,
        'fields': fields,
    }


def check_access_token(service: Any = dingtalk_service.service) -> dict[str, Any]:
    status = build_status_payload(service)
    if not status['configured']:
        return {
            'ok': False,
            'configured': False,
            'missing': status['missing'],
            'message': 'DingTalk is not configured',
        }

    try:
        token = service._get_access_token()
    except Exception as exc:  # noqa: BLE001
        return {
            'ok': False,
            'configured': True,
            'message': f'{exc.__class__.__name__}: {exc}',
        }

    return {
        'ok': bool(token),
        'configured': True,
        'token_received': bool(token),
        'token_length': len(str(token)),
    }


def sync_clock_payload(
    *,
    start_date: str,
    end_date: str,
    service: Any = dingtalk_service.service,
    sessionmaker_factory: Callable[[], Any] | None = None,
    sync_func: Callable[..., dict[str, int]] | None = None,
) -> dict[str, Any]:
    status = build_status_payload(service)
    if not status['configured']:
        return {
            'ok': False,
            'configured': False,
            'missing': status['missing'],
            'message': 'DingTalk is not configured',
        }

    make_session = sessionmaker_factory or get_sessionmaker
    run_sync = sync_func or dingtalk_service.sync_clock_records
    sessionmaker = make_session()
    db = sessionmaker()
    try:
        summary = run_sync(db, start_date=start_date, end_date=end_date)
    finally:
        close = getattr(db, 'close', None)
        if callable(close):
            close()

    failed = int(summary.get('failed', 0))
    return {
        'ok': failed == 0,
        'configured': True,
        'start_date': start_date,
        'end_date': end_date,
        'summary': summary,
    }


def _print_payload(payload: dict[str, Any], *, json_mode: bool, command: str) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if command == 'status':
        print(f"configured={'yes' if payload['configured'] else 'no'}")
        print(f"mode={payload['mode']}")
        print(f"missing={','.join(payload['missing']) if payload['missing'] else '-'}")
        for field_name, field in payload['fields'].items():
            print(f"{field_name}={'set' if field['set'] else 'missing'}")
        return

    if command == 'token':
        if payload['ok']:
            print('token_check=ok')
            print(f"token_length={payload['token_length']}")
        else:
            print('token_check=failed')
            print(f"message={payload.get('message', 'unknown')}")
        return

    if command == 'sync-clock':
        summary = payload.get('summary') or {}
        print(f"clock_sync={'ok' if payload['ok'] else 'failed'}")
        print(f"synced={summary.get('synced', 0)}")
        print(f"skipped={summary.get('skipped', 0)}")
        print(f"failed={summary.get('failed', 0)}")


def _exit_code(command: str, payload: dict[str, Any]) -> int:
    if payload.get('ok'):
        return 0
    if payload.get('configured') is False:
        return 2
    if command == 'sync-clock':
        return 4
    return 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='dingtalk-cli')
    subparsers = parser.add_subparsers(dest='command', required=True)

    status_parser = subparsers.add_parser('status')
    status_parser.add_argument('--json', action='store_true', help='Output JSON only')

    token_parser = subparsers.add_parser('token')
    token_parser.add_argument('--json', action='store_true', help='Output JSON only')

    today = date.today().isoformat()
    sync_parser = subparsers.add_parser('sync-clock')
    sync_parser.add_argument('--start-date', default=today, help='Start date, YYYY-MM-DD')
    sync_parser.add_argument('--end-date', default=today, help='End date, YYYY-MM-DD')
    sync_parser.add_argument('--json', action='store_true', help='Output JSON only')

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    service: Any = dingtalk_service.service,
    sessionmaker_factory: Callable[[], Any] | None = None,
    sync_func: Callable[..., dict[str, int]] | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == 'status':
        payload = build_status_payload(service)
    elif args.command == 'token':
        payload = check_access_token(service)
    elif args.command == 'sync-clock':
        payload = sync_clock_payload(
            start_date=args.start_date,
            end_date=args.end_date,
            service=service,
            sessionmaker_factory=sessionmaker_factory,
            sync_func=sync_func,
        )
    else:
        parser.error(f'unsupported command: {args.command}')

    _print_payload(payload, json_mode=args.json, command=args.command)
    return _exit_code(args.command, payload)


if __name__ == '__main__':
    raise SystemExit(main())
