"""Read-only SQL Server stock-in preview.

This script checks whether SQL Server stock-in rows can support finished-goods
output / factory total output, without writing local tables or SQL Server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters.mes_adapter import MesSourceRecord
from app.adapters.sqlserver_mes_adapter import SqlServerMesAdapter, _run_pymssql_query
from app.config import settings
from app.core.business_time import (
    last_completed_production_business_date,
    production_business_window,
    resolve_production_business_date,
)
from app.core.redaction import redact_secret_text
from app.services.mes_sync_service import _stock_fields


_REQUIRED_FIELDS = (
    'batch_no',
    'contract_no',
    'customer_alias',
    'net_weight_kg',
    'net_weight_tons',
    'gross_weight_kg',
    'gross_weight_tons',
    'in_stock_date',
    'business_date',
    'status_name',
)


def _safe_hash(value: Any) -> dict[str, Any]:
    text = str(value or '').strip()
    digest = hashlib.sha1(text.encode('utf-8')).hexdigest()[:12] if text else ''
    return {'hash': digest, 'length': len(text)}


def _is_present(value: Any) -> bool:
    return value not in (None, '')


def _rate(present: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(present / total, 4)


def _sum_float(rows: list[dict[str, Any]], field_name: str) -> float | None:
    values: list[float] = []
    for row in rows:
        value = row.get(field_name)
        if value in (None, ''):
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return round(sum(values), 6)


def _weight_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    both_present = 0
    net_lte_gross = 0
    net_gt_gross = 0
    for row in rows:
        net_value = row.get('net_weight_tons')
        gross_value = row.get('gross_weight_tons')
        if net_value in (None, '') or gross_value in (None, ''):
            continue
        try:
            net_number = float(net_value)
            gross_number = float(gross_value)
        except (TypeError, ValueError):
            continue
        both_present += 1
        if net_number <= gross_number:
            net_lte_gross += 1
        else:
            net_gt_gross += 1
    return {
        'rows_with_both_weights': both_present,
        'net_lte_gross_count': net_lte_gross,
        'net_gt_gross_count': net_gt_gross,
        'has_net_gt_gross_anomaly': net_gt_gross > 0,
    }


def _business_date_key(value: Any) -> str | None:
    if value in (None, ''):
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _metadata_text(record: MesSourceRecord, key: str) -> str:
    value = record.metadata.get(key)
    return str(value).strip() if value not in (None, '') else ''


def _department_counts(items: list[MesSourceRecord], projections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source, projection in zip(items, projections, strict=False):
        key = (
            _metadata_text(source, 'FromDepartment'),
            _metadata_text(source, 'ToDepartment'),
            str(source.metadata.get('Status') or projection.get('status_name') or '').strip(),
        )
        item = grouped.setdefault(
            key,
            {
                'from_department': key[0],
                'to_department': key[1],
                'status': key[2],
                'row_count': 0,
                'net_weight_tons': 0.0,
            },
        )
        item['row_count'] += 1
        try:
            item['net_weight_tons'] += float(projection.get('net_weight_tons') or 0)
        except (TypeError, ValueError):
            pass
    rows = sorted(grouped.values(), key=lambda row: row['row_count'], reverse=True)
    for row in rows:
        row['net_weight_tons'] = round(row['net_weight_tons'], 6)
    return rows[:20]


def business_date_window_for_days(
    *,
    days: int,
    now: datetime | None = None,
    completed_only: bool = False,
) -> dict[str, Any]:
    bounded_days = max(1, min(int(days), 31))
    end_business_date = (
        last_completed_production_business_date(now)
        if completed_only
        else resolve_production_business_date(now)
    )
    start_business_date = end_business_date - timedelta(days=bounded_days - 1)
    start_at, _ = production_business_window(start_business_date)
    _, end_at = production_business_window(end_business_date)
    return {
        'days': bounded_days,
        'start_business_date': start_business_date,
        'end_business_date': end_business_date,
        'start_at': start_at.replace(tzinfo=None),
        'end_at': end_at.replace(tzinfo=None),
    }


def build_total_output_candidate_summary(rows: Iterable[Mapping[str, Any]], *, days: int) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    total_rows = 0
    total_net_weight_tons = 0.0
    for row in rows:
        row_count = int(float(row.get('row_count') or 1))
        net_weight_tons = float(row.get('net_weight_tons') or 0)
        total_rows += row_count
        total_net_weight_tons += net_weight_tons
        event_time = row.get('event_time')
        business_date = row.get('business_date') or (resolve_production_business_date(event_time) if event_time is not None else None)
        key = (
            _business_date_key(business_date) or '',
            str(row.get('from_department') or '').strip(),
            str(row.get('to_department') or '').strip(),
            str(row.get('status') or '').strip(),
        )
        item = grouped.setdefault(key, {
            'business_date': key[0],
            'from_department': key[1],
            'to_department': key[2],
            'status': key[3],
            'row_count': 0,
            'net_weight_tons': 0.0,
        })
        item['row_count'] += row_count
        item['net_weight_tons'] += net_weight_tons
    items = sorted(grouped.values(), key=lambda row: (row['business_date'], row['row_count']), reverse=True)
    for item in items:
        item['net_weight_tons'] = round(item['net_weight_tons'], 6)
    return {
        'days': days,
        'row_count': total_rows,
        'net_weight_tons': round(total_net_weight_tons, 6),
        'items': items,
    }


def build_stock_preview(rows: Iterable[MesSourceRecord], *, now: datetime | None = None) -> dict[str, Any]:
    synced_at = now or datetime.now(timezone.utc)
    items = list(rows)
    projections = [_stock_fields(row, synced_at) for row in items]
    field_rates: dict[str, dict[str, Any]] = {}
    for field_name in _REQUIRED_FIELDS:
        present = sum(1 for row in projections if _is_present(row.get(field_name)))
        field_rates[field_name] = {
            'present': present,
            'missing': len(projections) - present,
            'rate': _rate(present, len(projections)),
        }

    business_date_counts: dict[str, int] = {}
    for row in projections:
        key = _business_date_key(row.get('business_date'))
        if key:
            business_date_counts[key] = business_date_counts.get(key, 0) + 1

    in_stock_rate = field_rates['in_stock_date']['rate'] or 0
    net_rate = field_rates['net_weight_tons']['rate'] or 0
    gross_rate = field_rates['gross_weight_tons']['rate'] or 0
    has_weight = (field_rates['net_weight_tons']['present'] + field_rates['gross_weight_tons']['present']) > 0
    weight_quality = _weight_quality(projections)
    samples: list[dict[str, Any]] = []
    for source, projection in zip(items[:10], projections[:10], strict=False):
        samples.append({
            'source': _safe_hash(source.source_id),
            'present_fields': sorted(field for field in _REQUIRED_FIELDS if _is_present(projection.get(field))),
            'missing_fields': sorted(field for field in _REQUIRED_FIELDS if not _is_present(projection.get(field))),
            'business_date': _business_date_key(projection.get('business_date')),
            'has_net_weight': _is_present(projection.get('net_weight_tons')),
            'has_in_stock_date': _is_present(projection.get('in_stock_date')),
        })

    return {
        'mode': 'read_only_stock_preview',
        'source_table': 'WMS_InStockDetail',
        'sqlserver_count': len(items),
        'required_field_rates': field_rates,
        'weight_totals': {
            'net_weight_tons': _sum_float(projections, 'net_weight_tons'),
            'gross_weight_tons': _sum_float(projections, 'gross_weight_tons'),
        },
        'weight_quality': weight_quality,
        'department_counts': _department_counts(items, projections),
        'business_date_counts': business_date_counts,
        'candidate_total_output_filter': {
            'from_department_keywords': ['精整', '拉矫', '剪切'],
            'to_department': '成品库',
            'status': '1',
            'time_field': 'CreateDate',
            'weight_field': 'NetWeight',
        },
        'readiness': {
            'finished_goods_output_candidate': (
                len(items) > 0
                and in_stock_rate >= 0.95
                and max(net_rate, gross_rate) >= 0.95
                and not weight_quality['has_net_gt_gross_anomaly']
            ),
            'preferred_weight_field': 'net_weight_tons' if net_rate >= gross_rate else 'gross_weight_tons',
            'needs_unit_confirmation': has_weight,
            'needs_status_filter_confirmation': field_rates['status_name']['present'] > 0,
        },
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


def _read_total_output_candidate_summary(*, days: int, completed_only: bool = False) -> dict[str, Any]:
    window = business_date_window_for_days(days=days, completed_only=completed_only)
    rows = _run_pymssql_query(
        host=str(settings.MES_SQLSERVER_HOST or '').strip(),
        port=int(settings.MES_SQLSERVER_PORT),
        database=str(settings.MES_SQLSERVER_DATABASE or '').strip(),
        username=str(settings.MES_SQLSERVER_USERNAME or '').strip(),
        password=str(settings.MES_SQLSERVER_PASSWORD or ''),
        timeout_seconds=settings.MES_SQLSERVER_TIMEOUT_SECONDS,
        encrypt=settings.MES_SQLSERVER_ENCRYPT,
        query=(
            'SELECT TOP (5000) CreateDate AS event_time, '
            'FromDepartment AS from_department, ToDepartment AS to_department, Status AS status, NetWeight / 1000.0 AS net_weight_tons '
            'FROM WMS_InStockDetail '
            'WHERE CreateDate >= %s AND CreateDate < %s '
            "AND ToDepartment = N'成品库' AND Status = 1 "
            "AND (FromDepartment LIKE N'%精整%' OR FromDepartment LIKE N'%拉矫%' OR FromDepartment LIKE N'%剪切%') "
            'ORDER BY CreateDate DESC'
        ),
        params=(window['start_at'], window['end_at']),
    )
    summary = build_total_output_candidate_summary(rows, days=window['days'])
    summary['window'] = {
        'start_business_date': window['start_business_date'].isoformat(),
        'end_business_date': window['end_business_date'].isoformat(),
        'start_at': window['start_at'].isoformat(sep=' '),
        'end_at': window['end_at'].isoformat(sep=' '),
    }
    return summary


def inspect_mes_sqlserver_stock_preview(*, limit: int = 200, days: int = 7) -> dict[str, Any]:
    resolved_limit = max(1, min(int(limit), 1000))
    resolved_days = max(1, min(int(days), 31))
    payload: dict[str, Any] = {
        'status': 'unknown',
        'mode': 'read_only_stock_preview',
        'limit': resolved_limit,
        'days': resolved_days,
        'error': None,
    }
    try:
        rows = _build_adapter().list_stock_records(limit=resolved_limit)
        payload.update(build_stock_preview(rows))
        payload['total_output_candidate_summary'] = _read_total_output_candidate_summary(days=resolved_days)
        payload['status'] = 'success'
    except Exception as exc:  # noqa: BLE001 - diagnostic script reports class only
        payload['status'] = 'failed'
        payload['error'] = redact_secret_text(f'{exc.__class__.__name__}: {exc}')
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Preview SQL Server MES stock-in rows without writing any database.')
    parser.add_argument('--limit', type=int, default=200, help='Maximum SQL Server rows to sample.')
    parser.add_argument('--days', type=int, default=7, help='Days to aggregate for the finished-goods output candidate.')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    args = parser.parse_args(argv)

    payload = inspect_mes_sqlserver_stock_preview(limit=args.limit, days=args.days)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"Status: {payload['status']}")
        print(f"Mode: {payload['mode']}")
        print(f"SQL Server rows: {payload.get('sqlserver_count', 0)}")
        print(f"Finished-goods output candidate: {payload.get('readiness', {}).get('finished_goods_output_candidate')}")
        if payload.get('error'):
            print(f"Error: {payload['error']}")
    return 0 if payload.get('status') == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
