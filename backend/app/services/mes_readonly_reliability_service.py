from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.adapters.sqlserver_mes_adapter import (
    SqlServerMesAdapter,
    audit_sqlserver_readonly_contract,
    classify_sqlserver_failure,
)
from app.core.business_time import production_business_window
from app.core.redaction import redact_secret_text
from app.models.mes import MesMaterialRecord, MesStockRecord, MesSyncRunLog, MesWorkshopProcessRecord
from app.services.mes_sync_service import SYNC_CURSOR_KEY, latest_sync_status


_PROJECTION_SOURCES: dict[str, tuple[type, tuple[str, ...]]] = {
    'workshop_process_records': (MesWorkshopProcessRecord, ('sqlserver:workshop_process_records',)),
    'stock_records': (MesStockRecord, ('sqlserver:stock_records',)),
    'finished_inbound_records': (MesStockRecord, ('sqlserver:stock_header_records',)),
    'delivery_records': (MesStockRecord, ('sqlserver:delivery_records', 'sqlserver:delivery_stock_records')),
    'material_records': (MesMaterialRecord, ('sqlserver:material_records',)),
}


def _blocker(code: str, **details: Any) -> dict[str, Any]:
    return {'code': code, **details}


def _safe_error(value: object) -> str:
    return redact_secret_text(value)[:240]


def _schema_sha256(columns: Sequence[str]) -> str:
    canonical = json.dumps(sorted(str(item) for item in columns), ensure_ascii=True, separators=(',', ':'))
    return sha256(canonical.encode('utf-8')).hexdigest()


def _sanitize_query_result(item: Mapping[str, Any]) -> dict[str, Any]:
    query_status = str(item.get('query_status') or 'failed')
    observed = item.get('observed_row_count')
    if query_status != 'success':
        outcome = 'query_failed'
        no_data_reason = None
        fact_value = None
    elif int(observed or 0) > 0:
        outcome = 'rows'
        no_data_reason = None
        fact_value = 'present'
    else:
        outcome = 'query_succeeded_no_rows'
        no_data_reason = 'source_query_returned_no_rows'
        fact_value = None
    columns = sorted({str(value) for value in item.get('schema_columns') or []})
    result = {
        'business_date': str(item.get('business_date') or ''),
        'query_key': str(item.get('query_key') or ''),
        'effective_query_key': str(item.get('effective_query_key') or item.get('query_key') or ''),
        'source_path': str(item.get('source_path') or ''),
        'source_table': str(item.get('source_table') or ''),
        'query_status': query_status,
        'outcome': outcome,
        'observed_row_count': int(observed) if observed is not None else None,
        'observation_limit': int(item.get('observation_limit') or 1),
        'projection_count': item.get('projection_count') if outcome == 'rows' else None,
        'schema_columns': columns,
        'schema_sha256': _schema_sha256(columns),
        'query_sha256': str(item.get('query_sha256') or ''),
        'no_data_reason': no_data_reason,
        'fact_value': fact_value,
    }
    if query_status != 'success':
        result['failure_kind'] = str(item.get('failure_kind') or 'read_failed')
        result['error'] = _safe_error(item.get('error') or 'read_failed')
    return result


def run_controlled_fault_drills() -> list[dict[str, Any]]:
    cases = (
        ('disconnect', ConnectionError('server unavailable')),
        ('timeout', TimeoutError('query timed out')),
        ('schema_change', RuntimeError("Invalid column name 'Phase3Probe'")),
    )
    drills = []
    for drill_id, error in cases:
        attempts = 0
        recovered = False
        failure_kind = ''
        while attempts < 2:
            attempts += 1
            try:
                if attempts == 1:
                    raise error
                recovered = True
                break
            except Exception as exc:  # noqa: BLE001
                failure_kind = classify_sqlserver_failure(exc)
        drills.append(
            {
                'drill_id': drill_id,
                'failure_kind': failure_kind,
                'mode': 'in_memory_no_vendor_call',
                'attempt_count': attempts,
                'recovered': recovered,
                'status': 'pass' if recovered else 'blocked',
            }
        )
    return drills


def evaluate_mes_readonly_reliability(
    *,
    business_dates: Sequence[date],
    readonly_contract: Mapping[str, Any],
    permission_audit: Mapping[str, Any],
    query_results: Iterable[Mapping[str, Any]],
    successful_sync_dates: Iterable[str],
    sync_status: Mapping[str, Any],
    fault_drills: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    date_labels = [item.isoformat() for item in business_dates]
    sanitized_queries = [_sanitize_query_result(item) for item in query_results]
    successful = {str(item) for item in successful_sync_dates}
    sync_days = [
        {
            'business_date': item,
            'outcome': 'success' if item in successful else 'missing_successful_sync',
        }
        for item in date_labels
    ]
    safe_sync_status = {
        'status': str(sync_status.get('status') or 'unknown'),
        'lag_seconds': sync_status.get('lag_seconds'),
        'stale_threshold_seconds': sync_status.get('stale_threshold_seconds'),
        'last_run_status': str(sync_status.get('last_run_status') or 'unknown'),
        'last_synced_at': sync_status.get('last_synced_at'),
    }
    safe_permission_audit = {
        'status': str(permission_audit.get('status') or 'blocked'),
        'database_dangerous_permissions': list(permission_audit.get('database_dangerous_permissions') or []),
        'object_results': list(permission_audit.get('object_results') or []),
        'dangerous_permissions': list(permission_audit.get('dangerous_permissions') or []),
        'failure_kind': str(permission_audit.get('failure_kind') or ''),
        'error': _safe_error(permission_audit.get('error')) if permission_audit.get('error') else None,
    }
    safe_fault_drills = [
        {
            'drill_id': str(item.get('drill_id') or ''),
            'failure_kind': str(item.get('failure_kind') or ''),
            'mode': str(item.get('mode') or ''),
            'attempt_count': int(item.get('attempt_count') or 0),
            'recovered': bool(item.get('recovered')),
            'status': str(item.get('status') or 'blocked'),
        }
        for item in fault_drills
    ]

    blockers = []
    if len(date_labels) != 3:
        blockers.append(_blocker('business_date_count_invalid', expected=3, actual=len(date_labels)))
    if not bool(readonly_contract.get('passed')):
        blockers.append(_blocker('sqlserver_query_contract_failed'))
    if safe_permission_audit['dangerous_permissions']:
        blockers.append(_blocker('sqlserver_write_permission'))
    elif safe_permission_audit['status'] != 'pass':
        blockers.append(_blocker('sqlserver_permission_audit_failed'))
    for item in sanitized_queries:
        if item['outcome'] == 'query_failed':
            blockers.append(
                _blocker(
                    'mes_source_query_failed',
                    business_date=item['business_date'],
                    query_key=item['query_key'],
                    failure_kind=item.get('failure_kind'),
                )
            )
        elif item['outcome'] == 'rows' and int(item.get('projection_count') or 0) == 0:
            blockers.append(
                _blocker(
                    'projection_missing_after_source_rows',
                    business_date=item['business_date'],
                    query_key=item['query_key'],
                )
            )
    for item in sync_days:
        if item['outcome'] != 'success':
            blockers.append(_blocker('mes_sync_day_missing', business_date=item['business_date']))
    if safe_sync_status['status'] == 'stale':
        blockers.append(_blocker('mes_sync_stale'))
    elif safe_sync_status['status'] != 'fresh':
        blockers.append(_blocker('mes_sync_unhealthy', status=safe_sync_status['status']))
    if any(item['status'] != 'pass' or not item['recovered'] for item in safe_fault_drills):
        blockers.append(_blocker('controlled_fault_drill_failed'))

    return {
        'status': 'pass' if not blockers else 'blocked',
        'business_dates': date_labels,
        'business_date_count': len(date_labels),
        'readonly_contract': {
            'status': str(readonly_contract.get('status') or 'blocked'),
            'passed': bool(readonly_contract.get('passed')),
            'query_count': int(readonly_contract.get('query_count') or 0),
            'contract_sha256': str(readonly_contract.get('contract_sha256') or ''),
            'issues': [str(item) for item in readonly_contract.get('issues') or []],
        },
        'permission_audit': safe_permission_audit,
        'query_results': sanitized_queries,
        'sync_days': sync_days,
        'sync_status': safe_sync_status,
        'fault_drills': safe_fault_drills,
        'blockers': blockers,
    }


def _projection_count(db: Session, *, query_key: str, business_date: date) -> int:
    model, source_paths = _PROJECTION_SOURCES[query_key]
    return int(
        db.query(func.count(model.id))
        .filter(model.business_date == business_date)
        .filter(model.source_path.in_(source_paths))
        .scalar()
        or 0
    )


def _successful_sync_dates(db: Session, business_dates: Sequence[date]) -> list[str]:
    successful = []
    for business_date in business_dates:
        start_at, end_at = production_business_window(business_date)
        count = int(
            db.query(func.count(MesSyncRunLog.id))
            .filter(MesSyncRunLog.cursor_key == SYNC_CURSOR_KEY)
            .filter(MesSyncRunLog.status == 'success')
            .filter(MesSyncRunLog.started_at >= start_at)
            .filter(MesSyncRunLog.started_at < end_at)
            .scalar()
            or 0
        )
        if count > 0:
            successful.append(business_date.isoformat())
    return successful


def build_mes_readonly_reliability_report(
    db: Session,
    *,
    adapter: SqlServerMesAdapter,
    business_dates: Sequence[date],
    now: datetime,
    run_fault_drills: bool = True,
) -> dict[str, Any]:
    readonly_contract = audit_sqlserver_readonly_contract()
    try:
        permission_audit = adapter.audit_effective_readonly_permissions()
    except Exception as exc:  # noqa: BLE001
        permission_audit = {
            'status': 'blocked',
            'dangerous_permissions': [],
            'failure_kind': classify_sqlserver_failure(exc),
            'error': _safe_error(exc),
        }

    query_results = []
    for business_date in business_dates:
        start_at, end_at = production_business_window(business_date)
        for query_key in _PROJECTION_SOURCES:
            try:
                probe = adapter.probe_readonly_window(query_key, start_at=start_at, end_at=end_at)
                has_rows = int(probe.get('observed_row_count') or 0) > 0
                query_results.append(
                    {
                        **probe,
                        'business_date': business_date.isoformat(),
                        'projection_count': _projection_count(
                            db,
                            query_key=query_key,
                            business_date=business_date,
                        )
                        if has_rows
                        else None,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                query_results.append(
                    {
                        'business_date': business_date.isoformat(),
                        'query_key': query_key,
                        'source_path': f'sqlserver:{query_key}',
                        'query_status': 'failed',
                        'observed_row_count': None,
                        'projection_count': None,
                        'schema_columns': [],
                        'failure_kind': classify_sqlserver_failure(exc),
                        'error': _safe_error(exc),
                    }
                )

    return evaluate_mes_readonly_reliability(
        business_dates=business_dates,
        readonly_contract=readonly_contract,
        permission_audit=permission_audit,
        query_results=query_results,
        successful_sync_dates=_successful_sync_dates(db, business_dates),
        sync_status=latest_sync_status(db, now=now),
        fault_drills=run_controlled_fault_drills() if run_fault_drills else (),
    )
