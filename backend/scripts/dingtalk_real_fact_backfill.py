from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping, TextIO

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.business_time import last_completed_production_business_date
from app.database import get_sessionmaker
from app.services.dingtalk_energy_ingest_service import DATE_KEYS, resolve_dingtalk_energy_business_date
from app.services.dingtalk_service import DingTalkDownloadedFile
from app.services.dingtalk_stream_gateway_service import ingest_dingtalk_stream_event


@dataclass(frozen=True)
class LocalBackfillFile:
    download_code: str
    file_name: str
    content: bytes
    content_type: str | None


class LocalBackfillDingTalkService:
    def __init__(self) -> None:
        self._files: dict[str, LocalBackfillFile] = {}

    def add_file(self, file: LocalBackfillFile) -> None:
        self._files[file.download_code] = file

    def download_robot_message_file(self, *, download_code: str) -> DingTalkDownloadedFile:
        file = self._files[download_code]
        return DingTalkDownloadedFile(
            download_url_host='local-backfill',
            content=file.content,
            content_type=file.content_type,
            size=len(file.content),
        )


def run_backfill(
    *,
    input_jsonl: str | Path,
    files_root: str | Path,
    days: int,
) -> dict[str, int]:
    root = Path(files_root).resolve()
    session_factory = get_sessionmaker()
    summary = {'accepted': 0, 'duplicates': 0, 'rejected': 0, 'file_text': 0, 'message_text': 0}
    local_file_service = LocalBackfillDingTalkService()
    cutoff = last_completed_production_business_date() - timedelta(days=max(1, int(days)) - 1)

    db = session_factory()
    try:
        for row in _read_jsonl(input_jsonl):
            try:
                mapped = _row_to_stream_payload(row, files_root=root, local_file_service=local_file_service)
                if mapped is None:
                    summary['rejected'] += 1
                    continue
                payload, uses_local_file = mapped
                business_date = resolve_dingtalk_energy_business_date(
                    dict(payload.get('data') or {}),
                    file_name=_payload_file_name(payload),
                )
                if business_date < cutoff:
                    summary['rejected'] += 1
                    continue
            except (OSError, ValueError):
                summary['rejected'] += 1
                continue

            result = ingest_dingtalk_stream_event(
                db,
                payload,
                dingtalk_service=local_file_service if uses_local_file else None,
            )

            if result.get('duplicate'):
                summary['duplicates'] += 1
            elif result.get('accepted'):
                summary['accepted'] += 1
            else:
                summary['rejected'] += 1
            if result.get('file_text'):
                summary['file_text'] += 1
            if result.get('message_text'):
                summary['message_text'] += 1
    finally:
        db.close()
    return summary


def _read_jsonl(path: str | Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        clean = line.strip()
        if not clean:
            continue
        payload = json.loads(clean)
        if not isinstance(payload, Mapping):
            raise ValueError('jsonl_row_must_be_object')
        rows.append(payload)
    return rows


def _row_to_stream_payload(
    row: Mapping[str, Any],
    *,
    files_root: Path,
    local_file_service: LocalBackfillDingTalkService,
) -> tuple[dict[str, Any], bool] | None:
    group_id = _first_text(
        row.get('conversationId'),
        row.get('openConversationId'),
        row.get('chatId'),
        row.get('group_id'),
        row.get('groupId'),
    )
    text = _first_text(row.get('message_text'), row.get('text'), row.get('content'))
    file_name = _first_text(row.get('fileName'), row.get('file_name'), row.get('name'))
    local_file_path = _first_text(row.get('localFilePath'), row.get('local_file_path'))
    data: dict[str, Any] = {
        'conversationId': group_id,
        'conversationType': _first_text(row.get('conversationType'), row.get('conversation_type')) or 'group',
        'messageId': _first_text(row.get('messageId'), row.get('message_id'), row.get('msgId')),
        'senderStaffId': _first_text(row.get('senderStaffId'), row.get('senderId'), row.get('sender_user_id')),
        'senderUnionId': _first_text(row.get('senderUnionId'), row.get('unionId')),
        'createTime': _first_text(row.get('createTime'), row.get('messageTime'), row.get('event_time')),
    }
    for key in DATE_KEYS:
        value = row.get(key)
        if value not in (None, ''):
            data[key] = value

    if local_file_path and file_name:
        resolved_path = _resolve_local_file(files_root, local_file_path)
        content = resolved_path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        download_code = f'local-backfill:{content_hash[:16]}'
        local_file_service.add_file(
            LocalBackfillFile(
                download_code=download_code,
                file_name=file_name,
                content=content,
                content_type=mimetypes.guess_type(file_name)[0],
            )
        )
        data.update(
            {
                'msgtype': 'file',
                'content': {
                    'fileName': file_name,
                    'downloadCode': download_code,
                    'fileId': _first_text(row.get('fileId'), row.get('file_id')) or content_hash,
                },
            }
        )
        return {'data': data}, True

    if text:
        data.update({'msgtype': 'text', 'text': {'content': text}})
        return {'data': data}, False

    return None


def _resolve_local_file(files_root: Path, local_file_path: str) -> Path:
    root = files_root.resolve()
    raw_path = Path(local_file_path)
    candidate = raw_path.resolve() if raw_path.is_absolute() else (root / raw_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError('local_file_path_outside_files_root')
    if not candidate.is_file():
        raise ValueError('local_file_not_found')
    return candidate


def _payload_file_name(payload: Mapping[str, Any]) -> str | None:
    data = payload.get('data')
    if not isinstance(data, Mapping):
        return None
    content = data.get('content')
    if isinstance(content, Mapping):
        return _first_text(content.get('fileName'), content.get('file_name'))
    return _first_text(data.get('fileName'), data.get('file_name'))


def _first_text(*values: Any) -> str | None:
    for value in values:
        clean = str(value or '').strip()
        if clean:
            return clean
    return None


def main(argv: list[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-jsonl', required=True)
    parser.add_argument('--files-root', required=True)
    parser.add_argument('--days', type=int, default=3)
    args = parser.parse_args(argv)

    try:
        summary = run_backfill(input_jsonl=args.input_jsonl, files_root=args.files_root, days=args.days)
    except Exception as exc:  # noqa: BLE001
        print(f'钉钉真实事实回填失败：{exc.__class__.__name__}', file=error_output)
        return 1
    print(json.dumps(summary, ensure_ascii=False), file=output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
