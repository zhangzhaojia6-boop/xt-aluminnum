"""Read-only SQL Server projection preview.

This script previews what SQL Server rows would look like after the existing
MES projection logic, without writing local tables and without modifying SQL
Server. It is the safe step before shadow sync.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters.mes_adapter import CoilSnapshot
from app.adapters.sqlserver_mes_adapter import SqlServerMesAdapter
from app.config import settings
from app.core.redaction import redact_secret_text
from app.services.mes_sync_service import _projection_fields


_REQUIRED_FIELDS = (
    'coil_id',
    'tracking_card_no',
    'batch_no',
    'contract_no',
    'material_code',
    'customer_alias',
    'alloy_grade',
    'spec_display',
    'feeding_weight',
    'current_workshop',
    'current_process',
    'next_workshop',
    'next_process',
    'process_route_text',
    'in_stock_date',
)


def _safe_card(value: Any) -> dict[str, Any]:
    text = str(value or '').strip()
    digest = hashlib.sha1(text.encode('utf-8')).hexdigest()[:12] if text else ''
    return {'hash': digest, 'length': len(text)}


def _is_present(value: Any) -> bool:
    return value not in (None, '')


def _rate(present: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(present / total, 4)


def build_projection_preview(rows: Iterable[CoilSnapshot], *, now: datetime | None = None) -> dict[str, Any]:
    synced_at = now or datetime.now(timezone.utc)
    items = list(rows)
    projections = [_projection_fields(row, synced_at) | {'tracking_card_no': row.tracking_card_no, 'batch_no': row.batch_no, 'contract_no': row.contract_no} for row in items]
    field_rates: dict[str, dict[str, Any]] = {}
    for field_name in _REQUIRED_FIELDS:
        present = sum(1 for row in projections if _is_present(row.get(field_name)))
        field_rates[field_name] = {
            'present': present,
            'missing': len(projections) - present,
            'rate': _rate(present, len(projections)),
        }
    samples: list[dict[str, Any]] = []
    for source, projection in zip(items[:10], projections[:10], strict=False):
        samples.append({
            'tracking_card': _safe_card(source.tracking_card_no),
            'present_fields': sorted(field for field in _REQUIRED_FIELDS if _is_present(projection.get(field))),
            'missing_fields': sorted(field for field in _REQUIRED_FIELDS if not _is_present(projection.get(field))),
            'workshop_present': _is_present(projection.get('current_workshop')),
            'process_present': _is_present(projection.get('current_process')),
        })
    return {
        'mode': 'read_only_projection_preview',
        'sqlserver_count': len(items),
        'required_field_rates': field_rates,
        'samples': samples,
    }


def _build_adapter() -> SqlServerMesAdapter:
    return SqlServerMesAdapter(
        host=str(settings.MES_SQLSERVER_HOST or '').strip(),
        port=int(settings.MES_SQLSERVER_PORT),
        database=str(settings.MES_SQLSERVER_DATABASE or '').strip(),
        username=str(settings.MES_SQLSERVER_USERNAME or '').strip(),
        password=str(settings.MES_SQLSERVER_PASSWORD or ''),
        timeout_seconds=settings.MES_SQLSERVER_TIMEOUT_SECONDS,
        encrypt=settings.MES_SQLSERVER_ENCRYPT,
    )


def inspect_mes_sqlserver_projection_preview(*, limit: int = 200) -> dict[str, Any]:
    resolved_limit = max(1, min(int(limit), 1000))
    payload: dict[str, Any] = {
        'status': 'unknown',
        'mode': 'read_only_projection_preview',
        'limit': resolved_limit,
        'error': None,
    }
    try:
        rows = _build_adapter().list_dispatch(limit=resolved_limit)
        payload.update(build_projection_preview(rows))
        payload['status'] = 'success'
    except Exception as exc:  # noqa: BLE001 - diagnostic script reports class only
        payload['status'] = 'failed'
        payload['error'] = redact_secret_text(f'{exc.__class__.__name__}: {exc}')
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Preview SQL Server MES projection without writing any database.')
    parser.add_argument('--limit', type=int, default=200, help='Maximum SQL Server rows to sample.')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    args = parser.parse_args(argv)

    payload = inspect_mes_sqlserver_projection_preview(limit=args.limit)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"Status: {payload['status']}")
        print(f"Mode: {payload['mode']}")
        print(f"SQL Server rows: {payload.get('sqlserver_count', 0)}")
        if payload.get('error'):
            print(f"Error: {payload['error']}")
    return 0 if payload.get('status') == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
