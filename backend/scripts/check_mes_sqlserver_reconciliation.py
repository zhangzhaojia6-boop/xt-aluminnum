"""Read-only SQL Server to local MES projection reconciliation.

This script never writes to SQL Server or the local database. It samples the
SQL Server adapter output and compares it with local `mes_coil_snapshots` rows
so cutover readiness can be tracked with evidence instead of guesswork.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

from sqlalchemy import bindparam, inspect, text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters.mes_adapter import CoilSnapshot
from app.adapters.sqlserver_mes_adapter import SqlServerMesAdapter
from app.config import settings
from app.core.redaction import redact_secret_text
from app.database import get_sessionmaker
from app.utils.tracking_cards import tracking_card_lookup_key


MES_COIL_SNAPSHOT_TABLE = 'mes_coil_snapshots'
_LOCAL_PROJECTION_COLUMNS = (
    'coil_id',
    'mes_product_id',
    'tracking_card_no',
    'batch_no',
    'contract_no',
    'current_workshop',
    'current_process',
    'alloy_grade',
    'spec_display',
    'process_route_text',
)


_FIELD_COMPARISONS = {
    'batch_no': ('batch_no', lambda row: getattr(row, 'batch_no', None)),
    'contract_no': ('contract_no', lambda row: getattr(row, 'contract_no', None)),
    'current_workshop': ('workshop_code', lambda row: getattr(row, 'current_workshop', None)),
    'current_process': ('process_code', lambda row: getattr(row, 'current_process', None)),
    'alloy_grade': ('metadata.Alloy', lambda row: getattr(row, 'alloy_grade', None)),
    'spec_display': ('metadata.Specification', lambda row: getattr(row, 'spec_display', None)),
    'process_route_text': ('metadata.ProcessRoute', lambda row: getattr(row, 'process_route_text', None)),
}


def _value_from_sql(row: CoilSnapshot, path: str) -> Any:
    if path.startswith('metadata.'):
        return row.metadata.get(path.split('.', 1)[1])
    return getattr(row, path, None)


def _norm(value: Any) -> str:
    return str(value or '').strip().upper()


def _safe_card(value: Any) -> dict[str, Any]:
    text = str(value or '').strip()
    digest = hashlib.sha1(text.encode('utf-8')).hexdigest()[:12] if text else ''
    return {'hash': digest, 'length': len(text)}


def _identity_key(value: Any) -> str:
    return str(value or '').strip().upper()


def _sql_lookup_keys(row: CoilSnapshot) -> list[str]:
    keys: list[str] = []
    for value in (
        row.coil_id,
        row.metadata.get('Id'),
        row.metadata.get('ProductId'),
        row.metadata.get('ProductID'),
    ):
        text = _identity_key(value)
        if not text:
            continue
        keys.append(f'ID:{text}')
        if not text.startswith('MES:'):
            keys.append(f'ID:MES:{text}')
    card_key = tracking_card_lookup_key(row.tracking_card_no)
    if card_key:
        keys.append(f'CARD:{card_key}')
    return keys


def _local_lookup_keys(row: Any) -> list[str]:
    keys: list[str] = []
    for value in (
        getattr(row, 'coil_id', None),
        getattr(row, 'mes_product_id', None),
    ):
        text = _identity_key(value)
        if not text:
            continue
        keys.append(f'ID:{text}')
        if not text.startswith('MES:'):
            keys.append(f'ID:MES:{text}')
    card_key = tracking_card_lookup_key(getattr(row, 'tracking_card_no', None))
    if card_key:
        keys.append(f'CARD:{card_key}')
    return keys


def _rate(matched: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(matched / total, 4)


def local_projection_columns(available_columns: Iterable[str]) -> list[str]:
    available = set(available_columns)
    return [column for column in _LOCAL_PROJECTION_COLUMNS if column in available]


def build_reconciliation_report(sql_rows: Iterable[CoilSnapshot], local_rows: Iterable[Any]) -> dict[str, Any]:
    sql_items = list(sql_rows)
    local_by_key: dict[str, Any] = {}
    for row in local_rows:
        for key in _local_lookup_keys(row):
            local_by_key.setdefault(key, row)
    matched_pairs: list[tuple[CoilSnapshot, Any]] = []
    missing_local_samples: list[dict[str, Any]] = []
    for row in sql_items:
        local = next((local_by_key[key] for key in _sql_lookup_keys(row) if key in local_by_key), None)
        if local is None:
            if len(missing_local_samples) < 10:
                missing_local_samples.append({
                    'tracking_card': _safe_card(row.tracking_card_no),
                    'workshop': row.workshop_code,
                    'process': row.process_code,
                })
            continue
        matched_pairs.append((row, local))

    field_rates: dict[str, dict[str, Any]] = {}
    mismatch_samples: list[dict[str, Any]] = []
    for field_name, (sql_path, local_reader) in _FIELD_COMPARISONS.items():
        comparable = 0
        matched = 0
        mismatched = 0
        for sql_row, local_row in matched_pairs:
            sql_value = _value_from_sql(sql_row, sql_path)
            local_value = local_reader(local_row)
            if sql_value in (None, '') or local_value in (None, ''):
                continue
            comparable += 1
            if _norm(sql_value) == _norm(local_value):
                matched += 1
            else:
                mismatched += 1
                if len(mismatch_samples) < 10:
                    mismatch_samples.append({
                        'tracking_card': _safe_card(sql_row.tracking_card_no),
                        'field': field_name,
                        'sql_present': bool(sql_value),
                        'local_present': bool(local_value),
                    })
        field_rates[field_name] = {
            'comparable': comparable,
            'matched': matched,
            'mismatched': mismatched,
            'rate': _rate(matched, comparable),
        }

    return {
        'mode': 'read_only',
        'sqlserver_count': len(sql_items),
        'local_match_count': len(matched_pairs),
        'missing_local_count': len(sql_items) - len(matched_pairs),
        'match_rate': _rate(len(matched_pairs), len(sql_items)),
        'field_rates': field_rates,
        'missing_local_samples': missing_local_samples,
        'field_mismatch_samples': mismatch_samples,
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


def inspect_mes_sqlserver_reconciliation(*, limit: int = 200) -> dict[str, Any]:
    resolved_limit = max(1, min(int(limit), 1000))
    payload: dict[str, Any] = {
        'status': 'unknown',
        'mode': 'read_only',
        'limit': resolved_limit,
        'local_projection': {
            'table_exists': None,
            'row_count': None,
            'selected_columns': [],
        },
        'error': None,
    }
    try:
        sql_rows = _build_adapter().list_dispatch(limit=resolved_limit)
        cards = [row.tracking_card_no for row in sql_rows if row.tracking_card_no]
        if not cards:
            payload.update(build_reconciliation_report(sql_rows, []))
            payload['status'] = 'success'
            return payload
        session_factory = get_sessionmaker()
        with session_factory() as db:
            inspector = inspect(db.get_bind())
            table_exists = inspector.has_table(MES_COIL_SNAPSHOT_TABLE)
            payload['local_projection']['table_exists'] = table_exists
            if not table_exists:
                local_rows = []
            else:
                available_columns = [column['name'] for column in inspector.get_columns(MES_COIL_SNAPSHOT_TABLE)]
                selected_columns = local_projection_columns(available_columns)
                payload['local_projection']['selected_columns'] = selected_columns
                count_row = db.execute(text(f'SELECT COUNT(*) AS row_count FROM {MES_COIL_SNAPSHOT_TABLE}')).mappings().first()
                payload['local_projection']['row_count'] = count_row.get('row_count') if count_row else 0
                if 'tracking_card_no' not in selected_columns:
                    local_rows = []
                else:
                    columns_sql = ', '.join(selected_columns)
                    stmt = text(
                        f'SELECT {columns_sql} FROM {MES_COIL_SNAPSHOT_TABLE} WHERE tracking_card_no IN :cards'
                    ).bindparams(bindparam('cards', expanding=True))
                    local_rows = [SimpleNamespace(**dict(row)) for row in db.execute(stmt, {'cards': cards}).mappings().all()]
            db.rollback()
        payload.update(build_reconciliation_report(sql_rows, local_rows))
        payload['status'] = 'success'
    except Exception as exc:  # noqa: BLE001 - diagnostic script reports class only
        payload['status'] = 'failed'
        payload['error'] = redact_secret_text(f'{exc.__class__.__name__}: {exc}')
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Read-only SQL Server to local MES projection reconciliation.')
    parser.add_argument('--limit', type=int, default=200, help='Maximum SQL Server rows to sample.')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    args = parser.parse_args(argv)

    payload = inspect_mes_sqlserver_reconciliation(limit=args.limit)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"Status: {payload['status']}")
        print(f"Mode: {payload['mode']}")
        print(f"SQL Server rows: {payload.get('sqlserver_count', 0)}")
        print(f"Local matches: {payload.get('local_match_count', 0)}")
        print(f"Match rate: {payload.get('match_rate')}")
        if payload.get('error'):
            print(f"Error: {payload['error']}")
    return 0 if payload.get('status') == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
