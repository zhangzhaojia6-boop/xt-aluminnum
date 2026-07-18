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
from app.core.business_time import local_now, production_business_window, resolve_production_business_date
from app.core.redaction import redact_secret_text
from app.models.mes import MesMaterialRecord, MesStockRecord, MesSyncRunLog, MesWorkshopProcessRecord
from app.services.mes_sync_service import SYNC_CURSOR_KEY, _run_with_adapter_retries, latest_sync_status


_PROJECTION_SOURCES: dict[str, tuple[type, tuple[str, ...]]] = {
    'workshop_process_records': (MesWorkshopProcessRecord, ('sqlserver:workshop_process_records',)),
    'stock_records': (MesStockRecord, ('sqlserver:stock_records',)),
    'finished_inbound_records': (MesStockRecord, ('sqlserver:stock_header_records',)),
    'delivery_records': (MesStockRecord, ('sqlserver:delivery_records', 'sqlserver:delivery_stock_records')),
    'material_records': (MesMaterialRecord, ('sqlserver:material_records',)),
}
_FAULT_ACTION_BY_KIND = {
    'connection_failed': 'check_mes_connection',
    'query_timeout': 'check_mes_timeout',
    'schema_changed': 'check_mes_schema',
    'read_failed': 'check_mes_source',
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
        'event_time_field': str(item.get('event_time_field') or ''),
        'window_start_at': str(item.get('window_start_at') or ''),
        'window_end_at': str(item.get('window_end_at') or ''),
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


def _persisted_event_id(event: object, *, expected_type: str) -> str | None:
    if not isinstance(event, Mapping):
        return None
    event_id = event.get('id')
    if event_id in (None, '') or str(event.get('event_type') or '') != expected_type:
        return None
    return str(event_id)


def run_controlled_fault_drills(*, event_publisher=None) -> list[dict[str, Any]]:
    if event_publisher is None:
        from app.tasks.mes_sync import _publish_sync_event

        event_publisher = _publish_sync_event
    cases = (
        ('disconnect', ConnectionError('server unavailable')),
        ('timeout', TimeoutError('query timed out')),
        ('schema_change', RuntimeError("Invalid column name 'Phase3Probe'")),
    )
    drills = []
    for drill_id, error in cases:
        operation_attempts = 0

        def operation():
            nonlocal operation_attempts
            operation_attempts += 1
            if operation_attempts == 1:
                raise error
            return True

        try:
            _result, attempts, failure_kind = _run_with_adapter_retries(
                operation,
                sleep_before_retry=lambda _seconds: None,
            )
            recovered = attempts > 1
        except Exception as exc:  # noqa: BLE001
            attempts = int(getattr(exc, 'attempt_count', operation_attempts) or operation_attempts)
            failure_kind = str(getattr(exc, 'failure_kind', '') or classify_sqlserver_failure(exc))
            recovered = False

        failed_step = {
            'cursor_key': f'controlled_audit:{drill_id}',
            'status': 'failed',
            'attempt_count': 1,
            'failure_kind': failure_kind,
            'recovered': False,
            'action': _FAULT_ACTION_BY_KIND.get(failure_kind, 'check_mes_source'),
        }
        failed_event = event_publisher(
            'mes_sync_failed',
            {
                'controlled_audit': True,
                'drill_id': drill_id,
                'steps': [failed_step],
            },
        )
        recovered_event = None
        if recovered:
            recovered_event = event_publisher(
                'mes_sync_recovered',
                {
                    'controlled_audit': True,
                    'drill_id': drill_id,
                    'steps': [
                        {
                            **failed_step,
                            'status': 'success',
                            'attempt_count': attempts,
                            'recovered': True,
                        }
                    ],
                },
            )
        failed_event_id = _persisted_event_id(failed_event, expected_type='mes_sync_failed')
        recovered_event_id = _persisted_event_id(recovered_event, expected_type='mes_sync_recovered')
        events_persisted = bool(failed_event_id and recovered_event_id)
        drills.append(
            {
                'drill_id': drill_id,
                'failure_kind': failure_kind,
                'mode': 'persistent_event_bus_no_vendor_call',
                'attempt_count': attempts,
                'recovered': recovered,
                'events_persisted': events_persisted,
                'failed_event_id': failed_event_id,
                'recovered_event_id': recovered_event_id,
                'status': 'pass' if recovered and events_persisted else 'blocked',
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
        'schema_results': list(permission_audit.get('schema_results') or []),
        'dangerous_database_roles': list(permission_audit.get('dangerous_database_roles') or []),
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
            'events_persisted': bool(item.get('events_persisted')),
            'failed_event_id': str(item.get('failed_event_id') or ''),
            'recovered_event_id': str(item.get('recovered_event_id') or ''),
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
    if any(
        item['status'] != 'pass' or not item['recovered'] or not item['events_persisted']
        for item in safe_fault_drills
    ):
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
    if not business_dates:
        return []
    earliest_start = min(production_business_window(item)[0] for item in business_dates)
    run_logs = (
        db.query(MesSyncRunLog)
        .filter(MesSyncRunLog.cursor_key == SYNC_CURSOR_KEY)
        .filter(MesSyncRunLog.status == 'success')
        .filter(MesSyncRunLog.started_at >= earliest_start)
        .order_by(MesSyncRunLog.started_at.asc())
        .all()
    )
    successful_labels = set()
    for run_log in run_logs:
        metadata = run_log.metadata_json if isinstance(run_log.metadata_json, dict) else {}
        raw_target = metadata.get('target_business_date')
        try:
            target = date.fromisoformat(str(raw_target)) if raw_target else None
        except ValueError:
            target = None
        if target is None:
            raw_window_start = metadata.get('window_started_at')
            try:
                reference_at = datetime.fromisoformat(str(raw_window_start)) if raw_window_start else run_log.started_at
            except (TypeError, ValueError):
                reference_at = run_log.started_at
            target = resolve_production_business_date(local_now(reference_at))
        successful_labels.add(target.isoformat())
    return [item.isoformat() for item in business_dates if item.isoformat() in successful_labels]


def build_mes_readonly_reliability_report(
    db: Session,
    *,
    adapter: SqlServerMesAdapter,
    business_dates: Sequence[date],
    now: datetime,
    run_fault_drills: bool = True,
    fault_event_publisher=None,
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
        fault_drills=(
            run_controlled_fault_drills(event_publisher=fault_event_publisher)
            if run_fault_drills
            else ()
        ),
    )
