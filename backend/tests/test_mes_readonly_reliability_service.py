from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.mes import MesMaterialRecord, MesStockRecord, MesSyncRunLog, MesWorkshopProcessRecord
from app.models.production import RealtimeEvent
from app.models.system import User
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
                    'event_time_field': 'OperateDate',
                    'window_start_at': f'{business_date.isoformat()}T07:50:00+08:00',
                    'window_end_at': f'{business_date.isoformat()}T07:50:00+08:00',
                }
            )
    results[-1].update(observed_row_count=0, projection_count=None, schema_columns=[])
    return results


def _machine_fact_checks(business_dates=BUSINESS_DATES) -> list[dict]:
    return [
        {
            'business_date': item.isoformat(),
            'status': 'pass',
            'source_status': 'ok',
            'data_source': 'mes_readonly',
            'record_count': 10,
            'complete_record_count': 8,
            'review_required_count': 2,
            'record_semantics': 'mes_process_start_end_not_physical_power',
        }
        for item in business_dates
    ]


def _persisted_fault_drills():
    events = []

    def publish(event_type, payload):
        event = {'id': len(events) + 1, 'event_type': event_type, 'payload': payload}
        events.append(event)
        return event

    return run_controlled_fault_drills(event_publisher=publish), events


def _evaluate(**overrides):
    fault_drills, _events = _persisted_fault_drills()
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
        'fault_drills': fault_drills,
        'machine_fact_checks': _machine_fact_checks(),
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
    assert no_data['event_time_field'] == 'OperateDate'
    assert no_data['window_start_at']
    assert no_data['window_end_at']


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
    drills, events = _persisted_fault_drills()

    assert {item['failure_kind'] for item in drills} == {
        'connection_failed',
        'query_timeout',
        'schema_changed',
    }
    assert all(item['status'] == 'pass' for item in drills)
    assert all(item['recovered'] is True for item in drills)
    assert all(item['mode'] == 'persistent_event_bus_no_vendor_call' for item in drills)
    assert all(item['events_persisted'] is True for item in drills)
    assert all(item['failed_event_id'] for item in drills)
    assert all(item['recovered_event_id'] for item in drills)
    assert [item['event_type'] for item in events] == [
        'mes_sync_failed',
        'mes_sync_recovered',
    ] * 3
    assert all('workflow_event' not in item['payload'] for item in events)
    assert events[0]['payload']['steps'][0]['action'] == 'check_mes_connection'


def test_gate_blocks_fault_drill_when_event_persistence_is_not_proven() -> None:
    drills = run_controlled_fault_drills(event_publisher=lambda _event_type, _payload: None)

    assert all(item['events_persisted'] is False for item in drills)
    assert all(item['status'] == 'blocked' for item in drills)
    result = _evaluate(fault_drills=drills)
    assert {item['code'] for item in result['blockers']} == {'controlled_fault_drill_failed'}


def test_gate_blocks_when_machine_operation_facts_cannot_use_direct_mes() -> None:
    checks = _machine_fact_checks()
    checks[0].update(
        status='blocked',
        source_status='failed',
        data_source='data_hub_projection',
        record_count=1,
        complete_record_count=1,
        review_required_count=0,
        reason='direct_mes_machine_fact_unavailable',
    )
    checks[2].update(
        status='no_data',
        record_count=0,
        complete_record_count=0,
        review_required_count=0,
        reason='source_query_succeeded_no_machine_rows',
    )

    result = _evaluate(machine_fact_checks=checks)

    assert {item['code'] for item in result['blockers']} == {
        'machine_operation_fact_unavailable',
    }
    assert result['machine_fact_checks'][0] == checks[0]


def test_machine_operation_fact_checks_keep_counts_without_raw_machine_rows(
    monkeypatch,
) -> None:
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(engine, tables=[User.__table__])
    db = sessionmaker(bind=engine, future=True)()
    db.add(
        User(
            username='audit-admin',
            password_hash='x',
            name='审计管理员',
            role='admin',
            data_scope_type='all',
            is_active=True,
        )
    )
    db.commit()

    def fake_read_machine_facts(
        _db,
        *,
        intent,
        business_date,
        command_text,
        current_user,
        mes_reader,
    ):
        assert intent == 'machine_operation'
        assert command_text == '机器生产起止明细'
        assert current_user.role == 'admin'
        assert mes_reader is not None
        return {
            'fact_status': 'partial',
            'record_count': 12,
            'complete_record_count': 9,
            'review_required_count': 3,
            'data_source': 'mes_readonly',
            'record_semantics': 'mes_process_start_end_not_physical_power',
            'source_status': {'mes': 'ok'},
            'top_operations': [
                {
                    'device_name': '不应进入审计产物',
                    'begin_at': business_date.isoformat(),
                }
            ],
        }

    monkeypatch.setattr(service, 'read_machine_facts', fake_read_machine_facts)

    checks = service._build_machine_operation_fact_checks(
        db,
        adapter=object(),
        business_dates=BUSINESS_DATES,
    )

    assert len(checks) == 3
    assert all(item['status'] == 'pass' for item in checks)
    assert all(item['complete_record_count'] == 9 for item in checks)
    assert all('top_operations' not in item for item in checks)
    assert '不应进入审计产物' not in str(checks)
    db.close()


def test_controlled_fault_drills_persist_database_events_without_workflow_dispatch(monkeypatch) -> None:
    from app.core import event_bus as event_bus_module
    from app.core.event_bus import DatabaseEventBus

    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(engine, tables=[RealtimeEvent.__table__])
    SessionLocal = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(
        event_bus_module,
        'event_bus',
        DatabaseEventBus(sessionmaker_factory=lambda: SessionLocal),
    )

    drills = run_controlled_fault_drills()

    with SessionLocal() as db:
        rows = db.query(RealtimeEvent).order_by(RealtimeEvent.id.asc()).all()
    assert all(item['status'] == 'pass' for item in drills)
    assert [item.event_type for item in rows] == ['mes_sync_failed', 'mes_sync_recovered'] * 3
    assert all(item.payload['controlled_audit'] is True for item in rows)
    assert all('workflow_event' not in item.payload for item in rows)


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
                'event_time_field': 'OperateDate',
                'window_start_at': _kwargs['start_at'].isoformat(),
                'window_end_at': _kwargs['end_at'].isoformat(),
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
    monkeypatch.setattr(
        service,
        '_build_machine_operation_fact_checks',
        lambda *_args, business_dates, **_kwargs: _machine_fact_checks(business_dates),
    )

    report = build_mes_readonly_reliability_report(
        db,
        adapter=Adapter(),
        business_dates=BUSINESS_DATES,
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone),
        fault_event_publisher=lambda event_type, payload: {
            'id': f'{event_type}:{payload["drill_id"]}',
            'event_type': event_type,
        },
    )

    assert report['status'] == 'pass'
    assert len(report['query_results']) == 15
    assert all(item['projection_count'] == 1 for item in report['query_results'])
    assert all(item['outcome'] == 'success' for item in report['sync_days'])
    assert all(item['status'] == 'pass' for item in report['machine_fact_checks'])
    db.close()


def test_successful_sync_dates_count_late_recovery_for_covered_business_window() -> None:
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(engine, tables=[MesSyncRunLog.__table__])
    db = sessionmaker(bind=engine, future=True)()
    timezone = ZoneInfo('Asia/Shanghai')
    db.add(
        MesSyncRunLog(
            cursor_key='coil_snapshots',
            started_at=datetime(2026, 7, 18, 8, 5, tzinfo=timezone),
            finished_at=datetime(2026, 7, 18, 8, 6, tzinfo=timezone),
            status='success',
            metadata_json={
                'window_started_at': '2026-07-17T07:50:00+08:00',
                'target_business_date': '2026-07-17',
            },
        )
    )
    db.commit()

    assert service._successful_sync_dates(db, [date(2026, 7, 17), date(2026, 7, 18)]) == ['2026-07-17']
    db.close()
