from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.mes import MesMaterialRecord, MesStockRecord, MesSyncRunLog, MesWorkshopProcessRecord
from app.services import mes_readonly_reliability_service as service
from app.services.mes_readonly_reliability_service import (
    build_mes_readonly_reliability_report,
    evaluate_mes_readonly_reliability,
    run_controlled_fault_drills,
)


BUSINESS_DATES = (date(2026, 7, 15), date(2026, 7, 16), date(2026, 7, 17))
QUERY_KEYS = (
    'workshop_process_records',
    'stock_records',
    'finished_inbound_records',
    'delivery_records',
    'material_records',
)


def _query_results() -> list[dict]:
    results = []
    for business_date in BUSINESS_DATES:
        for query_key in QUERY_KEYS:
            results.append(
                {
                    'business_date': business_date.isoformat(),
                    'query_key': query_key,
                    'source_path': f'sqlserver:{query_key}',
                    'query_status': 'success',
                    'observed_row_count': 1,
                    'projection_count': 1,
                    'schema_columns': ['Id', 'OperateDate'],
                }
            )
    results[-1].update(observed_row_count=0, projection_count=None, schema_columns=[])
    return results


def _evaluate(**overrides):
    inputs = {
        'business_dates': BUSINESS_DATES,
        'readonly_contract': {'status': 'pass', 'passed': True, 'issues': []},
        'permission_audit': {'status': 'pass', 'dangerous_permissions': []},
        'query_results': _query_results(),
        'successful_sync_dates': [item.isoformat() for item in BUSINESS_DATES],
        'sync_status': {
            'status': 'fresh',
            'lag_seconds': 30.0,
            'stale_threshold_seconds': 300.0,
            'last_run_status': 'success',
        },
        'fault_drills': run_controlled_fault_drills(),
    }
    inputs.update(overrides)
    return evaluate_mes_readonly_reliability(**inputs)


def test_gate_passes_three_dates_with_rows_or_explicit_no_data() -> None:
    result = _evaluate()

    assert result['status'] == 'pass'
    assert result['business_date_count'] == 3
    assert all(item['outcome'] in {'rows', 'query_succeeded_no_rows'} for item in result['query_results'])
    no_data = result['query_results'][-1]
    assert no_data['outcome'] == 'query_succeeded_no_rows'
    assert no_data['no_data_reason'] == 'source_query_returned_no_rows'
    assert no_data['fact_value'] is None
    assert no_data['projection_count'] is None


def test_gate_blocks_dangerous_permissions_projection_gap_and_stale_sync() -> None:
    query_results = _query_results()
    query_results[0]['projection_count'] = 0

    result = _evaluate(
        permission_audit={
            'status': 'blocked',
            'dangerous_permissions': [
                {'scope': 'database', 'resource': 'XTAL', 'permissions': ['UPDATE']},
            ],
        },
        query_results=query_results,
        sync_status={
            'status': 'stale',
            'lag_seconds': 901.0,
            'stale_threshold_seconds': 300.0,
            'last_run_status': 'success',
        },
    )

    assert {item['code'] for item in result['blockers']} == {
        'sqlserver_write_permission',
        'projection_missing_after_source_rows',
        'mes_sync_stale',
    }


def test_gate_blocks_a_missing_successful_sync_day() -> None:
    result = _evaluate(successful_sync_dates=[item.isoformat() for item in BUSINESS_DATES[:2]])

    assert result['status'] == 'blocked'
    assert {item['code'] for item in result['blockers']} == {'mes_sync_day_missing'}
    assert result['sync_days'][-1] == {
        'business_date': '2026-07-17',
        'outcome': 'missing_successful_sync',
    }


def test_gate_blocks_query_failure_and_redacts_secret_text() -> None:
    query_results = _query_results()
    query_results[0].update(
        query_status='failed',
        failure_kind='connection_failed',
        error='login failed password=raw-secret token=raw-token',
        observed_row_count=None,
        projection_count=None,
        schema_columns=[],
    )

    result = _evaluate(query_results=query_results)
    serialized = str(result)

    assert result['status'] == 'blocked'
    assert {item['code'] for item in result['blockers']} == {'mes_source_query_failed'}
    assert 'raw-secret' not in serialized
    assert 'raw-token' not in serialized
    assert result['query_results'][0]['error'] == 'login failed password=<redacted> token=<redacted>'


def test_permission_audit_failure_keeps_only_redacted_diagnostic() -> None:
    result = _evaluate(
        permission_audit={
            'status': 'blocked',
            'dangerous_permissions': [],
            'failure_kind': 'connection_failed',
            'error': 'server unavailable password=raw-secret',
        }
    )

    assert {item['code'] for item in result['blockers']} == {'sqlserver_permission_audit_failed'}
    assert result['permission_audit']['failure_kind'] == 'connection_failed'
    assert result['permission_audit']['error'] == 'server unavailable password=<redacted>'


def test_controlled_fault_drills_classify_and_recover_without_touching_mes() -> None:
    drills = run_controlled_fault_drills()

    assert {item['failure_kind'] for item in drills} == {
        'connection_failed',
        'query_timeout',
        'schema_changed',
    }
    assert all(item['status'] == 'pass' for item in drills)
    assert all(item['recovered'] is True for item in drills)
    assert all(item['mode'] == 'in_memory_no_vendor_call' for item in drills)


def test_builder_combines_source_probes_projection_counts_and_sync_days(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            MesWorkshopProcessRecord.__table__,
            MesStockRecord.__table__,
            MesMaterialRecord.__table__,
            MesSyncRunLog.__table__,
        ],
    )
    db = sessionmaker(bind=engine, future=True)()
    source_paths = {
        'workshop_process_records': 'sqlserver:workshop_process_records',
        'stock_records': 'sqlserver:stock_records',
        'finished_inbound_records': 'sqlserver:stock_header_records',
        'delivery_records': 'sqlserver:delivery_records',
        'material_records': 'sqlserver:material_records',
    }
    models = {
        'workshop_process_records': MesWorkshopProcessRecord,
        'stock_records': MesStockRecord,
        'finished_inbound_records': MesStockRecord,
        'delivery_records': MesStockRecord,
        'material_records': MesMaterialRecord,
    }
    timezone = ZoneInfo('Asia/Shanghai')
    for business_date in BUSINESS_DATES:
        for query_key in QUERY_KEYS:
            db.add(
                models[query_key](
                    source_id=f'{business_date}:{query_key}',
                    source_path=source_paths[query_key],
                    business_date=business_date,
                )
            )
        db.add(
            MesSyncRunLog(
                cursor_key='coil_snapshots',
                started_at=datetime.combine(business_date, datetime.min.time(), tzinfo=timezone).replace(hour=12),
                finished_at=datetime.combine(business_date, datetime.min.time(), tzinfo=timezone).replace(hour=12, minute=1),
                status='success',
            )
        )
    db.commit()

    class Adapter:
        def audit_effective_readonly_permissions(self):
            return {'status': 'pass', 'dangerous_permissions': []}

        def probe_readonly_window(self, query_key, **_kwargs):
            return {
                'query_key': query_key,
                'source_path': source_paths[query_key],
                'source_table': query_key,
                'query_status': 'success',
                'observed_row_count': 1,
                'schema_columns': ['Id'],
                'query_sha256': 'a' * 64,
            }

    monkeypatch.setattr(
        service,
        'latest_sync_status',
        lambda *_args, **_kwargs: {
            'status': 'fresh',
            'lag_seconds': 10.0,
            'stale_threshold_seconds': 300.0,
            'last_run_status': 'success',
        },
    )

    report = build_mes_readonly_reliability_report(
        db,
        adapter=Adapter(),
        business_dates=BUSINESS_DATES,
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone),
    )

    assert report['status'] == 'pass'
    assert len(report['query_results']) == 15
    assert all(item['projection_count'] == 1 for item in report['query_results'])
    assert all(item['outcome'] == 'success' for item in report['sync_days'])
    db.close()
