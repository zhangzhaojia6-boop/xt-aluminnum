from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
import mimetypes
import re
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping, TextIO

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.business_time import last_completed_production_business_date  # noqa: E402
from app.database import get_sessionmaker  # noqa: E402
from app.models.agent_communication import MultimodalEvidence  # noqa: E402
from app.services.dingtalk_energy_ingest_service import (  # noqa: E402
    DATE_KEYS,
    resolve_dingtalk_energy_business_date,
)
from app.services.dingtalk_service import DingTalkDownloadedFile  # noqa: E402
from app.services.dingtalk_stream_gateway_service import ingest_dingtalk_stream_event  # noqa: E402
from app.services.dingtalk_verified_fact_extractor import (  # noqa: E402
    extract_verified_file_fact_updates,
    extract_verified_text_fact_updates,
)


SOURCE_TRANSPORT = 'dws_history_backfill'
MACHINE_ONLY_MODE = 'machine-only'
OWNER_VERIFIED_MODE = 'owner-verified-dws-history'
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
RUN_ID_RE = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')


@dataclass(frozen=True)
class LocalBackfillFile:
    download_code: str
    file_name: str
    content: bytes
    content_type: str | None


@dataclass(frozen=True)
class OwnerVerifiedContract:
    group_id: str
    message_id: str
    sender_user_id: str
    sender_identity_type: str
    event_time: str
    business_date: date
    content_sha256: str
    fact_updates: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class PreparedOwnerVerifiedRow:
    payload: dict[str, Any]
    uses_local_file: bool
    verification: OwnerVerifiedContract


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
    confirmation_mode: str = MACHINE_ONLY_MODE,
    confirmation_run_id: str | None = None,
) -> dict[str, int]:
    if confirmation_mode not in {MACHINE_ONLY_MODE, OWNER_VERIFIED_MODE}:
        raise ValueError('unsupported_confirmation_mode')
    if confirmation_mode == OWNER_VERIFIED_MODE and not RUN_ID_RE.fullmatch(str(confirmation_run_id or '')):
        raise ValueError('invalid_confirmation_run_id')
    root = Path(files_root).resolve()
    session_factory = get_sessionmaker()
    summary = {'accepted': 0, 'duplicates': 0, 'rejected': 0, 'file_text': 0, 'message_text': 0}
    if confirmation_mode == OWNER_VERIFIED_MODE:
        summary.update({'confirmed': 0, 'already_confirmed': 0, 'confirmation_rejected': 0, 'committed': 0})
    local_file_service = LocalBackfillDingTalkService()
    cutoff = last_completed_production_business_date() - timedelta(days=max(1, int(days)) - 1)

    db = session_factory()
    try:
        rows = _read_jsonl(input_jsonl)
        if confirmation_mode == OWNER_VERIFIED_MODE:
            return _run_owner_verified_backfill(
                db,
                rows=rows,
                files_root=root,
                cutoff=cutoff,
                local_file_service=local_file_service,
                confirmation_run_id=str(confirmation_run_id),
                summary=summary,
            )
        for row in rows:
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
                source_transport=SOURCE_TRANSPORT,
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


def _run_owner_verified_backfill(
    db,
    *,
    rows: list[Mapping[str, Any]],
    files_root: Path,
    cutoff: date,
    local_file_service: LocalBackfillDingTalkService,
    confirmation_run_id: str,
    summary: dict[str, int],
) -> dict[str, int]:
    prepared: list[PreparedOwnerVerifiedRow] = []
    for row in rows:
        try:
            verification = _owner_verified_contract(row, files_root=files_root)
            mapped = _row_to_stream_payload(row, files_root=files_root, local_file_service=local_file_service)
            if mapped is None:
                raise ValueError('owner_verified_content_unavailable')
            payload, uses_local_file = mapped
            report_date = resolve_dingtalk_energy_business_date(
                dict(payload.get('data') or {}),
                file_name=_payload_file_name(payload),
                fallback_to_last_completed=False,
            )
            if report_date is not None and report_date < cutoff:
                raise ValueError('owner_verified_business_date_outside_window')
            prepared.append(
                PreparedOwnerVerifiedRow(
                    payload=payload,
                    uses_local_file=uses_local_file,
                    verification=verification,
                )
            )
        except (OSError, ValueError):
            summary['rejected'] += 1
            summary['confirmation_rejected'] += 1
    if summary['confirmation_rejected']:
        return summary

    try:
        for item in prepared:
            result = ingest_dingtalk_stream_event(
                db,
                item.payload,
                dingtalk_service=local_file_service if item.uses_local_file else None,
                source_transport=SOURCE_TRANSPORT,
                commit=False,
                process_energy=False,
            )
            if not result.get('accepted'):
                summary['rejected'] += 1
                summary['confirmation_rejected'] += 1
                break
            summary['accepted'] += 1
            if result.get('duplicate'):
                summary['duplicates'] += 1
            if result.get('file_text'):
                summary['file_text'] += 1
            if result.get('message_text'):
                summary['message_text'] += 1
            confirmation_result = _confirm_owner_verified_evidence(
                db,
                evidence_id=result.get('evidence_id'),
                verification=item.verification,
                confirmation_run_id=confirmation_run_id,
            )
            if confirmation_result == 'confirmed':
                summary['confirmed'] += 1
            elif confirmation_result == 'already_confirmed':
                summary['already_confirmed'] += 1
            else:
                summary['confirmation_rejected'] += 1
                break
        if summary['confirmation_rejected']:
            db.rollback()
            summary['confirmed'] = 0
            return summary
        db.commit()
        summary['committed'] = 1
        return summary
    except Exception:
        db.rollback()
        raise


def _owner_verified_contract(row: Mapping[str, Any], *, files_root: Path) -> OwnerVerifiedContract:
    group_id = _first_text(
        row.get('conversationId'),
        row.get('openConversationId'),
        row.get('chatId'),
        row.get('group_id'),
        row.get('groupId'),
    )
    message_id = _first_text(row.get('messageId'), row.get('message_id'), row.get('msgId'))
    sender_user_id, sender_identity_type = _sender_identity(row)
    event_time = _first_text(row.get('createTime'), row.get('messageTime'), row.get('event_time'))
    business_date_text = _first_text(*(row.get(key) for key in DATE_KEYS))
    expected_hash = str(row.get('content_sha256') or '').strip().lower()
    if not all((group_id, message_id, sender_user_id, event_time, business_date_text)):
        raise ValueError('owner_verified_lineage_incomplete')
    if _parse_event_time(event_time) is None:
        raise ValueError('owner_verified_event_time_invalid')
    try:
        business_date = date.fromisoformat(str(business_date_text)[:10])
    except ValueError as exc:
        raise ValueError('owner_verified_business_date_invalid') from exc
    if not SHA256_RE.fullmatch(expected_hash):
        raise ValueError('owner_verified_content_hash_invalid')

    text = _first_text(row.get('message_text'), row.get('text'), row.get('content'))
    file_name = _first_text(row.get('fileName'), row.get('file_name'), row.get('name'))
    local_file_path = _first_text(row.get('localFilePath'), row.get('local_file_path'))
    fact_updates: dict[str, dict[str, Any]] = {}
    if local_file_path and file_name:
        content = _resolve_local_file(files_root, local_file_path).read_bytes()
        if not _first_text(row.get('fileId'), row.get('file_id')):
            raise ValueError('owner_verified_file_id_missing')
        actual_hash = hashlib.sha256(content).hexdigest()
        fact_updates = extract_verified_file_fact_updates(
            file_name=file_name,
            content=content,
            business_date=business_date,
            file_sha256=actual_hash,
        )
    elif text and not local_file_path and not file_name:
        actual_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        fact_updates = extract_verified_text_fact_updates(
            text=text,
            business_date=business_date,
            content_sha256=actual_hash,
        )
    else:
        raise ValueError('owner_verified_content_ambiguous')
    if actual_hash != expected_hash:
        raise ValueError('owner_verified_content_hash_mismatch')
    return OwnerVerifiedContract(
        group_id=group_id,
        message_id=message_id,
        sender_user_id=sender_user_id,
        sender_identity_type=sender_identity_type,
        event_time=event_time,
        business_date=business_date,
        content_sha256=expected_hash,
        fact_updates=fact_updates,
    )


def _confirm_owner_verified_evidence(
    db,
    *,
    evidence_id: Any,
    verification: OwnerVerifiedContract,
    confirmation_run_id: str,
) -> str:
    try:
        evidence_id_value = int(evidence_id)
    except (TypeError, ValueError):
        return 'rejected'
    evidence = db.get(MultimodalEvidence, evidence_id_value)
    if evidence is None:
        return 'rejected'
    payload = dict(evidence.payload) if isinstance(evidence.payload, dict) else {}
    stored_text = _first_text(payload.get('message_text'), payload.get('file_text'), payload.get('attachment_text'))
    stored_hash = str(payload.get('file_hash') or '').strip().lower()
    if not stored_hash and stored_text:
        stored_hash = hashlib.sha256(stored_text.encode('utf-8')).hexdigest()
    required_matches = (
        str(payload.get('source_transport') or '') == SOURCE_TRANSPORT,
        str(payload.get('trace_id') or '') == verification.message_id,
        str(payload.get('messageId') or payload.get('message_id') or '') == verification.message_id,
        str(payload.get('group_id') or '') == verification.group_id,
        str(payload.get('dingtalk_sender_id') or payload.get('senderStaffId') or '') == verification.sender_user_id,
        str(payload.get('sender_identity_type') or payload.get('senderIdentityType') or '')
        == verification.sender_identity_type,
        str(payload.get('business_date') or '') == verification.business_date.isoformat(),
        str(payload.get('event_time') or payload.get('dingtalk_message_time') or '') == verification.event_time,
        str(payload.get('parse_status') or '') == 'text_captured',
        stored_hash == verification.content_sha256,
    )
    if not all(required_matches):
        return 'rejected'

    owner_verification = {
        'mode': 'owner_verified_dws_history',
        'run_id': confirmation_run_id,
        'content_sha256': verification.content_sha256,
    }
    if evidence.confirmation_status == 'confirmed':
        existing_verification = payload.get('owner_verification')
        if (
            isinstance(existing_verification, Mapping)
            and existing_verification.get('mode') == owner_verification['mode']
            and existing_verification.get('content_sha256') == owner_verification['content_sha256']
        ):
            return 'already_confirmed'
        return 'rejected'
    payload['conversation_id'] = verification.group_id
    payload['sender_identity_type'] = verification.sender_identity_type
    payload['owner_verification'] = owner_verification
    if verification.fact_updates:
        payload['fact_updates'] = verification.fact_updates
    evidence.payload = payload
    evidence.confirmation_status = 'confirmed'
    return 'confirmed'


def _sender_identity(row: Mapping[str, Any]) -> tuple[str | None, str | None]:
    staff_id = _first_text(row.get('senderStaffId'), row.get('senderId'), row.get('sender_user_id'))
    if staff_id:
        return staff_id, 'staff_id'
    open_id = _first_text(row.get('senderOpenDingTalkId'), row.get('sender_open_dingtalk_id'))
    if open_id:
        return open_id, 'open_dingtalk_id'
    return None, None


def _parse_event_time(value: str) -> datetime | None:
    clean = str(value or '').strip()
    if not clean:
        return None
    try:
        numeric = float(clean)
    except ValueError:
        numeric = None
    if numeric is not None:
        if abs(numeric) >= 10**11:
            numeric /= 1000
        try:
            return datetime.fromtimestamp(numeric)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(clean.replace('Z', '+00:00'))
    except ValueError:
        return None


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
    sender_user_id, sender_identity_type = _sender_identity(row)
    data: dict[str, Any] = {
        'conversationId': group_id,
        'conversationType': _first_text(row.get('conversationType'), row.get('conversation_type')) or 'group',
        'messageId': _first_text(row.get('messageId'), row.get('message_id'), row.get('msgId')),
        'senderStaffId': sender_user_id,
        'senderIdentityType': sender_identity_type,
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
    parser.add_argument(
        '--confirmation-mode',
        choices=(MACHINE_ONLY_MODE, OWNER_VERIFIED_MODE),
        default=MACHINE_ONLY_MODE,
    )
    parser.add_argument('--confirmation-run-id')
    args = parser.parse_args(argv)

    try:
        summary = run_backfill(
            input_jsonl=args.input_jsonl,
            files_root=args.files_root,
            days=args.days,
            confirmation_mode=args.confirmation_mode,
            confirmation_run_id=args.confirmation_run_id,
        )
    except Exception as exc:  # noqa: BLE001
        print(f'钉钉真实事实回填失败：{exc.__class__.__name__}', file=error_output)
        return 1
    print(json.dumps(summary, ensure_ascii=False), file=output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
