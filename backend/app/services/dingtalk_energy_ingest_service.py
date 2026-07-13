from __future__ import annotations

import base64
import binascii
from datetime import date
from pathlib import Path
import re
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.core.business_time import last_completed_production_business_date, local_now
from app.core.redaction import redact_secret_text
from app.models.agent_communication import MultimodalEvidence


MAX_INLINE_DINGTALK_FILE_BYTES = 10 * 1024 * 1024
INLINE_FILE_KEYS = (
    'fileContentBase64',
    'file_content_base64',
    'fileBase64',
    'file_base64',
    'contentBase64',
    'content_base64',
)
DATE_KEYS = ('business_date', 'businessDate', 'report_date', 'reportDate', 'target_date', 'targetDate', 'date')
EXCEL_SUFFIXES = {'.xls', '.xlsx', '.xlsm'}


def _clean_text(value: Any) -> str:
    return str(value or '').strip()


def _payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ''):
            return value
    return None


def _parse_date_text(value: Any) -> date | None:
    text = _clean_text(value).replace('/', '-')
    if not text:
        return None
    match = re.search(r'(?P<year>20\d{2})-(?P<month>\d{1,2})-(?P<day>\d{1,2})', text)
    if match:
        return date(int(match.group('year')), int(match.group('month')), int(match.group('day')))
    return None


def _date_from_file_name(file_name: str) -> date | None:
    current_year = local_now().year
    patterns = (
        r'(?P<year>20\d{2})[-_年\.](?P<month>\d{1,2})[-_月\.](?P<day>\d{1,2})',
        r'(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日',
    )
    for pattern in patterns:
        match = re.search(pattern, file_name)
        if match:
            year = int(match.groupdict().get('year') or current_year)
            return date(year, int(match.group('month')), int(match.group('day')))
    return None


def resolve_dingtalk_energy_business_date(
    payload: dict[str, Any],
    *,
    file_name: str | None = None,
    fallback_to_last_completed: bool = True,
) -> date | None:
    for key in DATE_KEYS:
        parsed = _parse_date_text(payload.get(key))
        if parsed is not None:
            return parsed
    parsed = _date_from_file_name(_clean_text(file_name))
    if parsed is not None:
        return parsed
    if fallback_to_last_completed:
        return last_completed_production_business_date()
    return None


def _inline_file_bytes(payload: dict[str, Any]) -> tuple[bytes | None, str | None]:
    raw_value = _payload_value(payload, *INLINE_FILE_KEYS)
    if raw_value in (None, ''):
        return None, None
    raw_text = _clean_text(raw_value)
    if ',' in raw_text and raw_text.lower().startswith('data:'):
        raw_text = raw_text.split(',', 1)[1]
    try:
        content = base64.b64decode(raw_text, validate=True)
    except (binascii.Error, ValueError):
        return None, 'invalid_base64_file_content'
    if not content:
        return None, 'empty_file_content'
    if len(content) > MAX_INLINE_DINGTALK_FILE_BYTES:
        return None, 'file_too_large'
    return content, None


def _safe_file_name(file_name: str) -> str:
    name = Path(file_name).name.strip() or 'dingtalk-evidence.xlsx'
    safe = re.sub(r'[^0-9A-Za-z._\-\u4e00-\u9fff]+', '_', name).strip('._')
    return safe or 'dingtalk-evidence.xlsx'


def _stored_file_path(*, business_date: date, trace_id: str, file_name: str) -> Path:
    root = settings.upload_dir_path / 'dingtalk-evidence' / business_date.isoformat()
    root.mkdir(parents=True, exist_ok=True)
    trace = re.sub(r'[^0-9A-Za-z._-]+', '_', _clean_text(trace_id))[:48] or 'trace'
    return root / f'{trace}_{_safe_file_name(file_name)}'


def _is_excel_file(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in EXCEL_SUFFIXES


def _load_energy_import_module():
    from scripts import dry_run_energy_import

    return dry_run_energy_import


def _attach_ingest_result(db: Session, evidence: MultimodalEvidence, result: dict[str, Any]) -> dict[str, Any]:
    evidence_payload = dict(evidence.payload or {})
    evidence_payload['energy_ingest'] = result
    evidence.payload = evidence_payload
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return result


def ingest_dingtalk_energy_file(
    db: Session,
    *,
    payload: dict[str, Any],
    evidence: MultimodalEvidence,
    trace_id: str,
) -> dict[str, Any]:
    file_name = _clean_text(_payload_value(payload, 'fileName', 'file_name', 'name')) or 'dingtalk-evidence.xlsx'
    content, content_error = _inline_file_bytes(payload)
    if content_error:
        return _attach_ingest_result(db, evidence, {'status': 'blocked', 'reason': content_error})
    if content is None:
        return _attach_ingest_result(db, evidence, {'status': 'skipped', 'reason': 'no_inline_file_content'})
    if not _is_excel_file(file_name):
        return _attach_ingest_result(db, evidence, {'status': 'skipped', 'reason': 'not_excel_file'})

    business_date = resolve_dingtalk_energy_business_date(payload, file_name=file_name)
    if business_date is None:  # pragma: no cover - default resolver mode always returns a date
        business_date = last_completed_production_business_date()
    stored_path = _stored_file_path(business_date=business_date, trace_id=trace_id, file_name=file_name)
    stored_path.write_bytes(content)

    module = _load_energy_import_module()
    file_text = file_name.lower()
    is_gas = any(token in file_text for token in ('天然气', '气耗', 'gas'))
    try:
        stage_payload = module.stage_daily_energy_import(
            db=db,
            report_date=business_date,
            electricity_file=None if is_gas else stored_path,
            gas_file=stored_path if is_gas else None,
            commit=True,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _attach_ingest_result(
            db,
            evidence,
            {
                'status': 'blocked',
                'reason': 'energy_import_failed',
                'business_date': business_date.isoformat(),
                'stored_file': str(stored_path),
                'detail': redact_secret_text(str(exc)),
            },
        )
    batch_id = (stage_payload.get('staging_write') or {}).get('batch_id')
    result: dict[str, Any] = {
        'status': 'staged' if batch_id else 'blocked',
        'business_date': business_date.isoformat(),
        'stored_file': str(stored_path),
        'parse': stage_payload.get('parse'),
        'totals': stage_payload.get('totals'),
        'blocking_issues': stage_payload.get('blocking_issues') or [],
        'batch_id': batch_id,
    }
    if not batch_id:
        return _attach_ingest_result(db, evidence, result)

    try:
        promoted = module.promote_daily_energy_batch(db, batch_id=int(batch_id), commit=True)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        result.update({'status': 'blocked', 'reason': 'energy_promote_failed', 'detail': redact_secret_text(str(exc))})
        return _attach_ingest_result(db, evidence, result)
    result.update(
        {
            'status': 'promoted' if promoted.get('committed') else 'blocked',
            'record_rows_written': promoted.get('record_rows_written', 0),
            'blocking_issues': promoted.get('blocking_issues') or [],
        }
    )
    return _attach_ingest_result(db, evidence, result)
