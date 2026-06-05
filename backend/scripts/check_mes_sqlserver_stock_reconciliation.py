"""Read-only SQL Server stock-in to local projection reconciliation.

This command compares SQL Server finished-goods stock-in candidates with the
local `mes_stock_records` projection. It never writes SQL Server or local DB.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping

from sqlalchemy import inspect, text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.business_time import resolve_production_business_date
from app.core.redaction import redact_secret_text
from app.database import get_sessionmaker
from app.models.mes import MesStockRecord
from scripts.check_mes_sqlserver_stock_preview import (
    _read_total_output_candidate_summary,
    build_total_output_candidate_summary,
    business_date_window_for_days,
)


MES_STOCK_RECORD_TABLE = 'mes_stock_records'
_LOCAL_STOCK_COLUMNS = (
    'business_date',
    'in_stock_date',
    'net_weight_tons',
    'status_name',
    'source_payload',
)
_OUTPUT_FROM_DEPARTMENT_KEYWORDS = ('精整', '拉矫', '剪切')


def _row_get(row: Any, key: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(key)
    return getattr(row, key, None)


def _payload_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _text(value: Any) -> str:
    return str(value or '').strip()


def _float(value: Any) -> float | None:
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _status_key(value: Any) -> str:
    text_value = _text(value)
    if text_value.endswith('.0'):
        text_value = text_value[:-2]
    return text_value


def _business_date_key(value: Any) -> str:
    if value in (None, ''):
        return ''
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _is_total_output_candidate(*, from_department: str, to_department: str, status: Any) -> bool:
    return (
        to_department == '成品库'
        and _status_key(status) == '1'
        and any(keyword in from_department for keyword in _OUTPUT_FROM_DEPARTMENT_KEYWORDS)
    )


def build_local_stock_summary(rows: Iterable[Any], *, days: int) -> dict[str, Any]:
    candidate_rows: list[dict[str, Any]] = []
    for row in rows:
        payload = _payload_mapping(_row_get(row, 'source_payload'))
        from_department = _text(payload.get('FromDepartment') or _row_get(row, 'from_department'))
        to_department = _text(payload.get('ToDepartment') or _row_get(row, 'to_department'))
        status = payload.get('Status') if 'Status' in payload else _row_get(row, 'status_name')
        if not _is_total_output_candidate(from_department=from_department, to_department=to_department, status=status):
            continue
        net_weight = _float(_row_get(row, 'net_weight_tons'))
        if net_weight is None:
            continue
        business_date = _row_get(row, 'business_date')
        if business_date in (None, '') and _row_get(row, 'in_stock_date') is not None:
            business_date = resolve_production_business_date(_row_get(row, 'in_stock_date'))
        candidate_rows.append({
            'business_date': business_date,
            'from_department': from_department,
            'to_department': to_department,
            'status': _status_key(status),
            'row_count': 1,
            'net_weight_tons': net_weight,
        })
    return build_total_output_candidate_summary(candidate_rows, days=days)


def _date_totals(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in summary.get('items') or []:
        business_date = _business_date_key(item.get('business_date'))
        if not business_date:
            continue
        bucket = grouped.setdefault(business_date, {'business_date': business_date, 'row_count': 0, 'net_weight_tons': 0.0})
        bucket['row_count'] += int(float(item.get('row_count') or 0))
        bucket['net_weight_tons'] += float(item.get('net_weight_tons') or 0)
    for item in grouped.values():
        item['net_weight_tons'] = round(item['net_weight_tons'], 6)
    return grouped


def _delta_rate(delta_tons: float, sql_tons: float) -> float | None:
    if sql_tons == 0:
        return None
    return round(delta_tons / sql_tons, 6)


def build_stock_reconciliation_report(sql_summary: Mapping[str, Any], local_summary: Mapping[str, Any], *, days: int) -> dict[str, Any]:
    sql_by_date = _date_totals(sql_summary)
    local_by_date = _date_totals(local_summary)
    business_dates = sorted(sql_by_date, reverse=True)
    local_only_business_dates = sorted(set(local_by_date) - set(sql_by_date), reverse=True)
    comparisons: list[dict[str, Any]] = []
    for business_date in business_dates:
        sql_item = sql_by_date.get(business_date, {'row_count': 0, 'net_weight_tons': 0.0})
        local_item = local_by_date.get(business_date, {'row_count': 0, 'net_weight_tons': 0.0})
        sql_tons = float(sql_item.get('net_weight_tons') or 0)
        local_tons = float(local_item.get('net_weight_tons') or 0)
        delta_tons = round(sql_tons - local_tons, 6)
        rate = _delta_rate(abs(delta_tons), sql_tons)
        comparisons.append({
            'business_date': business_date,
            'sqlserver_rows': int(sql_item.get('row_count') or 0),
            'local_rows': int(local_item.get('row_count') or 0),
            'sqlserver_net_weight_tons': round(sql_tons, 6),
            'local_net_weight_tons': round(local_tons, 6),
            'delta_tons': delta_tons,
            'abs_delta_rate': rate,
            'within_one_percent': rate is not None and rate <= 0.01,
        })

    reasons: list[str] = []
    if int(sql_summary.get('row_count') or 0) <= 0:
        reasons.append('sqlserver_candidate_empty')
    if int(local_summary.get('row_count') or 0) <= 0:
        reasons.append('local_projection_empty')
    comparable_dates = [item for item in comparisons if item['sqlserver_rows'] > 0 and item['local_rows'] > 0]
    if len(comparable_dates) < 7:
        reasons.append('needs_at_least_7_business_dates')
    if any(item['sqlserver_rows'] > 0 and not item['within_one_percent'] for item in comparable_dates):
        reasons.append('business_date_delta_gt_one_percent')

    local_compared_rows = sum(int(local_by_date.get(item, {}).get('row_count') or 0) for item in business_dates)
    local_compared_tons = sum(float(local_by_date.get(item, {}).get('net_weight_tons') or 0) for item in business_dates)
    return {
        'mode': 'read_only_stock_reconciliation',
        'days': days,
        'sqlserver': {
            'row_count': int(sql_summary.get('row_count') or 0),
            'net_weight_tons': round(float(sql_summary.get('net_weight_tons') or 0), 6),
            'business_date_count': len(sql_by_date),
        },
        'local_projection': {
            'row_count': local_compared_rows,
            'net_weight_tons': round(local_compared_tons, 6),
            'business_date_count': len(local_by_date),
            'total_cached_row_count': int(local_summary.get('row_count') or 0),
            'total_cached_net_weight_tons': round(float(local_summary.get('net_weight_tons') or 0), 6),
            'local_only_business_dates': local_only_business_dates,
        },
        'business_date_comparison': comparisons,
        'ready_for_cutover': not reasons,
        'reasons': reasons,
    }


def local_stock_projection_columns(available_columns: Iterable[str]) -> list[str]:
    available = set(available_columns)
    return [column for column in _LOCAL_STOCK_COLUMNS if column in available]


def _read_local_stock_summary(*, days: int) -> tuple[dict[str, Any], dict[str, Any]]:
    payload: dict[str, Any] = {
        'table_exists': None,
        'row_count': None,
        'selected_columns': [],
        'missing_columns': [],
        'model_declared': MesStockRecord.__tablename__ == MES_STOCK_RECORD_TABLE,
        'expected_migration': '0034_mes_mvc_extended_sources',
        'action_required': 'none',
    }
    session_factory = get_sessionmaker()
    with session_factory() as db:
        inspector = inspect(db.get_bind())
        table_exists = inspector.has_table(MES_STOCK_RECORD_TABLE)
        payload['table_exists'] = table_exists
        if not table_exists:
            payload['action_required'] = 'run_migration'
            db.rollback()
            return payload, {'days': days, 'row_count': 0, 'net_weight_tons': 0.0, 'items': []}

        available_columns = [column['name'] for column in inspector.get_columns(MES_STOCK_RECORD_TABLE)]
        selected_columns = local_stock_projection_columns(available_columns)
        payload['selected_columns'] = selected_columns
        payload['missing_columns'] = [column for column in _LOCAL_STOCK_COLUMNS if column not in selected_columns]
        count_row = db.execute(text(f'SELECT COUNT(*) AS row_count FROM {MES_STOCK_RECORD_TABLE}')).mappings().first()
        payload['row_count'] = count_row.get('row_count') if count_row else 0
        if 'source_payload' not in selected_columns or 'net_weight_tons' not in selected_columns:
            payload['action_required'] = 'run_migration'
            db.rollback()
            return payload, {'days': days, 'row_count': 0, 'net_weight_tons': 0.0, 'items': []}

        columns_sql = ', '.join(selected_columns)
        if 'business_date' in selected_columns:
            window = business_date_window_for_days(days=days, now=datetime.now(timezone.utc), completed_only=True)
            stmt = text(
                f'SELECT {columns_sql} FROM {MES_STOCK_RECORD_TABLE} '
                'WHERE business_date >= :start_date AND business_date <= :end_date LIMIT 5000'
            )
            rows = [
                SimpleNamespace(**dict(row))
                for row in db.execute(
                    stmt,
                    {
                        'start_date': window['start_business_date'],
                        'end_date': window['end_business_date'],
                    },
                ).mappings().all()
            ]
        else:
            stmt = text(f'SELECT {columns_sql} FROM {MES_STOCK_RECORD_TABLE} LIMIT 5000')
            rows = [SimpleNamespace(**dict(row)) for row in db.execute(stmt).mappings().all()]
        db.rollback()
    return payload, build_local_stock_summary(rows, days=days)


def inspect_mes_sqlserver_stock_reconciliation(*, days: int = 7) -> dict[str, Any]:
    resolved_days = max(1, min(int(days), 31))
    payload: dict[str, Any] = {
        'status': 'unknown',
        'mode': 'read_only_stock_reconciliation',
        'days': resolved_days,
        'local_projection_table': {},
        'error': None,
    }
    try:
        sql_summary = _read_total_output_candidate_summary(days=resolved_days, completed_only=True)
        local_table_payload, local_summary = _read_local_stock_summary(days=resolved_days)
        payload['local_projection_table'] = local_table_payload
        payload.update(build_stock_reconciliation_report(sql_summary, local_summary, days=resolved_days))
        payload['status'] = 'success'
    except Exception as exc:  # noqa: BLE001 - diagnostic script reports class only
        payload['status'] = 'failed'
        payload['error'] = redact_secret_text(f'{exc.__class__.__name__}: {exc}')
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Read-only SQL Server stock-in to local projection reconciliation.')
    parser.add_argument('--days', type=int, default=7, help='Business-day window to compare.')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    args = parser.parse_args(argv)

    payload = inspect_mes_sqlserver_stock_reconciliation(days=args.days)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"Status: {payload['status']}")
        print(f"Mode: {payload['mode']}")
        print(f"Ready for cutover: {payload.get('ready_for_cutover')}")
        if payload.get('reasons'):
            print(f"Reasons: {', '.join(payload['reasons'])}")
        if payload.get('error'):
            print(f"Error: {payload['error']}")
    return 0 if payload.get('status') == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
