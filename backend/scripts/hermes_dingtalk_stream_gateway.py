from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Mapping, TextIO

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings, settings
from app.database import get_sessionmaker
from app.services.dingtalk_stream_event_service import normalize_dingtalk_stream_event, validate_authorized_group
from app.services.dingtalk_stream_gateway_service import ingest_dingtalk_stream_event


LOGGER = logging.getLogger(__name__)


def build_health_payload(runtime_settings: Settings = settings) -> dict[str, object]:
    if not runtime_settings.DINGTALK_STREAM_ENABLED:
        return {'ok': True, 'enabled': False, 'mode': 'disabled'}
    issues = runtime_settings.validate_runtime()
    if issues:
        return {'ok': False, 'enabled': True, 'mode': 'stream', 'issues': issues}
    return {
        'ok': True,
        'enabled': True,
        'mode': 'stream',
        'authorized_group_count': len(runtime_settings.dingtalk_authorized_group_ids),
        'authorized_group_scope': 'all' if runtime_settings.dingtalk_all_groups_authorized else 'allowlist',
    }


def load_json_payload(path: str | Path) -> Mapping[str, Any]:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(payload, Mapping):
        raise ValueError('payload_must_be_json_object')
    return payload


def dry_run_payload(payload: Mapping[str, Any], runtime_settings: Settings = settings) -> dict[str, Any]:
    event = normalize_dingtalk_stream_event(payload)
    try:
        validate_authorized_group(event, runtime_settings.dingtalk_authorized_group_ids)
    except ValueError as exc:
        return {
            'accepted': False,
            'dry_run': True,
            'would_write': False,
            'reason': str(exc),
            'trace_id': event.trace_id,
            'message_text': False,
            'file_text': False,
            'parse_status': 'not_written',
        }
    return {
        'accepted': True,
        'dry_run': True,
        'would_write': True,
        'trace_id': event.trace_id,
        'message_text': bool(str(event.message_text or '').strip()),
        'file_text': bool(event.file_name or event.file_id or event.download_code),
        'parse_status': 'not_written',
    }


def ingest_once_payload(
    payload: Mapping[str, Any],
    *,
    dry_run: bool = False,
    runtime_settings: Settings = settings,
) -> dict[str, Any]:
    if dry_run:
        return dry_run_payload(payload, runtime_settings=runtime_settings)

    session_factory = get_sessionmaker()
    db = session_factory()
    try:
        return ingest_dingtalk_stream_event(db, payload)
    finally:
        db.close()


def _load_dingtalk_stream_sdk():
    import dingtalk_stream
    from dingtalk_stream.chatbot import ChatbotHandler, ChatbotMessage

    return dingtalk_stream, ChatbotHandler, ChatbotMessage


def run_stream_forever(
    *,
    runtime_settings: Settings = settings,
    dry_run: bool = False,
    max_reconnects: int = 3,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    health = build_health_payload(runtime_settings=runtime_settings)
    if not health.get('enabled'):
        print(json.dumps(health, ensure_ascii=False), file=output)
        return 0
    if not health.get('ok'):
        print(json.dumps(health, ensure_ascii=False), file=error_output)
        return 2

    try:
        dingtalk_stream, ChatbotHandler, ChatbotMessage = _load_dingtalk_stream_sdk()
    except ModuleNotFoundError:
        print('缺少 dingtalk-stream 依赖，请先安装 backend/requirements.txt 后再启动钉钉 Stream。', file=error_output)
        return 2

    class HermesChatbotHandler(ChatbotHandler):
        def process(self, callback):
            payload = getattr(callback, 'data', callback)
            result = ingest_once_payload(payload, dry_run=dry_run, runtime_settings=runtime_settings)
            LOGGER.info('dingtalk_stream_event_result=%s', json.dumps(result, ensure_ascii=False))
            return dingtalk_stream.AckMessage.STATUS_OK

    credential = dingtalk_stream.Credential(
        runtime_settings.DINGTALK_APP_KEY,
        runtime_settings.DINGTALK_APP_SECRET,
    )
    client = dingtalk_stream.DingTalkStreamClient(credential)
    client.register_callback_handler(ChatbotMessage.TOPIC, HermesChatbotHandler())

    reconnects = 0
    while True:
        try:
            client.start_forever()
            return 0
        except KeyboardInterrupt:
            print('钉钉 Stream 已收到停止信号。', file=output)
            return 130
        except Exception as exc:  # noqa: BLE001
            reconnects += 1
            LOGGER.warning('dingtalk_stream_reconnect error=%s attempt=%s', exc.__class__.__name__, reconnects)
            if reconnects > max_reconnects:
                print('钉钉 Stream 重连次数已达上限，请检查网络、应用凭据和钉钉开放平台配置。', file=error_output)
                return 1
            time.sleep(min(30, 2**reconnects))


def main(
    argv: list[str] | None = None,
    runtime_settings: Settings = settings,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    parser = argparse.ArgumentParser()
    parser.add_argument('--health', action='store_true')
    parser.add_argument('--once-json')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--max-reconnects', type=int, default=3)
    args = parser.parse_args(argv)

    if args.health:
        payload = build_health_payload(runtime_settings=runtime_settings)
        print(json.dumps(payload, ensure_ascii=False), file=output)
        return 0 if payload.get('ok') else 2

    if args.once_json:
        try:
            payload = load_json_payload(args.once_json)
            result = ingest_once_payload(payload, dry_run=args.dry_run, runtime_settings=runtime_settings)
        except Exception as exc:  # noqa: BLE001
            print(f'钉钉 Stream 单次调试失败：{exc.__class__.__name__}', file=error_output)
            return 1
        print(json.dumps(result, ensure_ascii=False), file=output)
        return 0

    return run_stream_forever(
        runtime_settings=runtime_settings,
        dry_run=args.dry_run,
        max_reconnects=max(0, int(args.max_reconnects)),
        stdout=output,
        stderr=error_output,
    )


if __name__ == '__main__':
    raise SystemExit(main())
