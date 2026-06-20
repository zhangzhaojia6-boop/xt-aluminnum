from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.hermes_data_audit import HermesCorrectionAction, HermesDataAuditRun
from app.models.system import User

try:
    from app.routers.hermes_data_audit import get_hermes_data_audit_service
except ModuleNotFoundError:  # pragma: no cover - expected before implementation
    get_hermes_data_audit_service = None


ROUTER_TABLES = [
    User.__table__,
    HermesDataAuditRun.__table__,
    HermesCorrectionAction.__table__,
]


class FakeHermesDataAuditService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.create_run_calls: list[dict] = []
        self.apply_calls: list[dict] = []

    def create_run(
        self,
        *,
        business_date: date,
        fields: list[str] | None,
        mes_query_keys: list[str] | None = None,
        created_by_id: int | None = None,
    ) -> HermesDataAuditRun:
        self.create_run_calls.append(
            {
                'business_date': business_date,
                'fields': list(fields or []),
                'mes_query_keys': list(mes_query_keys or []),
                'created_by_id': created_by_id,
            }
        )
        run = HermesDataAuditRun(
            run_key=f'run-{business_date.isoformat()}-{len(self.create_run_calls)}',
            business_date=business_date,
            status='completed',
            source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
            source_errors={},
            mes_snapshot={'records_count_by_source': {'workshop_process_records': 2}},
            hub_snapshot={'field_count': 1},
            output_skill_snapshot={'parsed': {'total_output': 12.5}},
            diffs={'total_output': {'status': 'matched', 'values': {'mes': 12.5, 'hub': 12.5, 'output_skill': 12.5}}},
            suggested_actions=[],
            match_rate=Decimal('1.0000'),
            created_by_id=created_by_id,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def apply_corrections(
        self,
        *,
        audit_run_id: int,
        actions: list[dict],
        dry_run: bool = True,
        applied_by_id: int | None = None,
    ) -> dict:
        self.apply_calls.append(
            {
                'audit_run_id': audit_run_id,
                'actions': list(actions),
                'dry_run': dry_run,
                'applied_by_id': applied_by_id,
            }
        )
        run = self.db.get(HermesDataAuditRun, audit_run_id)
        if run is None:
            raise LookupError(f'Hermes data audit run {audit_run_id} not found')

        for payload in actions:
            action = HermesCorrectionAction(
                audit_run_id=audit_run_id,
                idempotency_key=str(payload.get('idempotency_key') or f'action-{len(self.apply_calls)}'),
                action_type=str(payload.get('action_type') or 'mapping_alias_upsert'),
                risk_level=str(payload.get('risk_level') or 'low'),
                target_table=str(payload.get('target_table') or 'master_code_aliases'),
                target_key=str(payload.get('target_key') or 'workshop:精整'),
                field_name=str(payload.get('field_name')) if payload.get('field_name') is not None else None,
                before_value=payload.get('before_value') or {'alias_code': 'old'},
                after_value=payload.get('after_value') or {'alias_code': 'new'},
                evidence=payload.get('evidence') or {'reason': 'test'},
                rollback_payload=payload.get('rollback_payload') or {'restore_before_value': {'alias_code': 'old'}},
                status='dry_run' if dry_run else 'applied',
                applied_by_id=None if dry_run else applied_by_id,
            )
            self.db.add(action)

        run.status = 'correction_blocked' if dry_run else 'corrected'
        self.db.commit()
        return {
            'audit_run_id': audit_run_id,
            'apply_enabled': False if dry_run else True,
            'reason': 'apply_disabled' if dry_run else None,
            'created_count': len(actions),
            'dry_run_count': len(actions) if dry_run else 0,
            'applied_count': 0 if dry_run else len(actions),
            'blocked_count': 0 if not dry_run else len(actions),
            'skipped_count': 0,
            'failed_count': 0,
            'action_statuses': [
                {
                    'idempotency_key': str(payload.get('idempotency_key') or f'action-{index + 1}'),
                    'status': 'dry_run' if dry_run else 'applied',
                }
                for index, payload in enumerate(actions)
            ],
        }


def _make_engine():
    return create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )


def _make_user(role: str) -> User:
    return User(id=1, username=role, password_hash='x', name='User', role=role, is_active=True)


def _install_overrides(*, db: Session, user_role: str, service: FakeHermesDataAuditService | None = None):
    def fake_get_db():
        yield db

    def fake_get_user() -> User:
        return _make_user(user_role)

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    if get_hermes_data_audit_service is not None and service is not None:
        app.dependency_overrides[get_hermes_data_audit_service] = lambda: service
    return previous_overrides


def _install_db_override_only(*, db: Session):
    def fake_get_db():
        yield db

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides.pop(get_current_user, None)
    if get_hermes_data_audit_service is not None:
        app.dependency_overrides.pop(get_hermes_data_audit_service, None)
    return previous_overrides


def _restore_overrides(previous_overrides) -> None:
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_admin_can_create_hermes_data_audit_run_returns_envelope() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    service = FakeHermesDataAuditService(db)
    previous_overrides = _install_overrides(db=db, user_role='admin', service=service)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/hermes/data-audit/runs',
            json={'business_date': '2026-06-18', 'fields': ['total_output'], 'mes_query_keys': ['stock_records']},
        )
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload['business_date'] == '2026-06-18'
    assert payload['source_health']['mes']['status'] == 'ok'
    assert payload['decision_gate']['can_apply'] is False
    assert service.create_run_calls[0]['created_by_id'] == 1


def test_non_admin_cannot_create_hermes_data_audit_run() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    service = FakeHermesDataAuditService(db)
    previous_overrides = _install_overrides(db=db, user_role='manager', service=service)

    try:
        client = TestClient(app)
        response = client.post('/api/v1/hermes/data-audit/runs', json={'business_date': '2026-06-18'})
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 403


def test_logged_in_user_can_get_hermes_data_audit_run() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-get-1',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'missing'},
        source_errors={'output_skill': 'output_skill_source_missing'},
        mes_snapshot={'records_count_by_source': {'stock_records': 3}},
        hub_snapshot={'field_count': 2},
        output_skill_snapshot={'parsed': {}},
        diffs={'total_output': {'status': 'output_skill_missing', 'values': {'mes': 10, 'hub': 10}}},
        suggested_actions=[],
        match_rate=Decimal('0.0000'),
        created_by_id=1,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    previous_overrides = _install_overrides(db=db, user_role='user')

    try:
        client = TestClient(app)
        response = client.get(f'/api/v1/hermes/data-audit/runs/{run.id}')
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == run.id
    assert payload['headline_status'] == 'completed'
    assert payload['source_health']['output_skill']['status'] == 'missing'


def test_get_hermes_data_audit_run_hides_apply_gate_after_applied_action(monkeypatch) -> None:
    monkeypatch.setenv('HERMES_DATA_AUDIT_APPLY_ENABLED', 'true')
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-corrected-applied',
        business_date=date(2026, 6, 18),
        status='corrected',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={'records_count_by_source': {'stock_records': 3}},
        hub_snapshot={'field_count': 1},
        output_skill_snapshot={'parsed': {'total_output': 10}},
        diffs={'total_output': {'status': 'hub_mismatch', 'values': {'mes': 10, 'hub': 8, 'output_skill': 10}}},
        suggested_actions=[],
        match_rate=Decimal('0.5000'),
        created_by_id=1,
    )
    db.add(run)
    db.flush()
    db.add(
        HermesCorrectionAction(
            audit_run_id=run.id,
            idempotency_key='applied:1',
            action_type='mapping_alias_upsert',
            risk_level='low',
            target_table='master_code_aliases',
            target_key='workshop:精整',
            before_value={'alias_code': '精整车间'},
            after_value={'alias_code': '精整'},
            evidence={'reason': 'matched'},
            status='applied',
            rollback_payload={'restore_before_value': {'alias_code': '精整车间'}},
        )
    )
    db.commit()
    previous_overrides = _install_overrides(db=db, user_role='user')

    try:
        client = TestClient(app)
        response = client.get(f'/api/v1/hermes/data-audit/runs/{run.id}')
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload['decision_gate']['can_apply'] is False
    assert payload['decision_gate']['reason'] == 'rerun_audit_required'
    assert payload['recommended_next_step'] == 'rerun_audit_to_verify'


def test_get_hermes_data_audit_run_blocks_apply_when_corrected_run_keeps_residual_suggestion(monkeypatch) -> None:
    monkeypatch.setenv('HERMES_DATA_AUDIT_APPLY_ENABLED', 'true')
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-corrected-residual-suggestion',
        business_date=date(2026, 6, 18),
        status='corrected',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={'records_count_by_source': {'stock_records': 3}},
        hub_snapshot={'field_count': 1},
        output_skill_snapshot={'parsed': {'total_output': 10}},
        diffs={'total_output': {'status': 'hub_mismatch', 'values': {'mes': 10, 'hub': 8, 'output_skill': 10}}},
        suggested_actions=[
            {
                'idempotency_key': 'suggested-after-corrected:1',
                'action_type': 'mapping_alias_upsert',
                'risk_level': 'low',
                'target_table': 'master_code_aliases',
                'target_key': 'workshop:拉矫',
                'rollback_payload': {'restore_before_value': {'alias_code': '拉矫车间'}},
            }
        ],
        match_rate=Decimal('0.5000'),
        created_by_id=1,
    )
    db.add(run)
    db.flush()
    db.add(
        HermesCorrectionAction(
            audit_run_id=run.id,
            idempotency_key='applied-before-rerun:1',
            action_type='mapping_alias_upsert',
            risk_level='low',
            target_table='master_code_aliases',
            target_key='workshop:精整',
            before_value={'alias_code': '精整车间'},
            after_value={'alias_code': '精整'},
            evidence={'reason': 'matched'},
            status='applied',
            rollback_payload={'restore_before_value': {'alias_code': '精整车间'}},
        )
    )
    db.commit()
    previous_overrides = _install_overrides(db=db, user_role='user')

    try:
        client = TestClient(app)
        response = client.get(f'/api/v1/hermes/data-audit/runs/{run.id}')
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    correction_action_keys = {item['idempotency_key'] for item in payload['correction_actions']}
    assert 'applied-before-rerun:1' in correction_action_keys
    assert 'suggested-after-corrected:1' in correction_action_keys
    assert payload['decision_gate']['can_apply'] is False
    assert payload['decision_gate']['reason'] == 'rerun_audit_required'
    assert payload['recommended_next_step'] == 'rerun_audit_to_verify'


def test_get_hermes_data_audit_run_does_not_mark_failed_action_as_ready_to_apply(monkeypatch) -> None:
    monkeypatch.setenv('HERMES_DATA_AUDIT_APPLY_ENABLED', 'true')
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-completed-failed',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={'records_count_by_source': {'stock_records': 3}},
        hub_snapshot={'field_count': 1},
        output_skill_snapshot={'parsed': {'total_output': 10}},
        diffs={'total_output': {'status': 'hub_mismatch', 'values': {'mes': 10, 'hub': 8, 'output_skill': 10}}},
        suggested_actions=[],
        match_rate=Decimal('0.5000'),
        created_by_id=1,
    )
    db.add(run)
    db.flush()
    db.add(
        HermesCorrectionAction(
            audit_run_id=run.id,
            idempotency_key='failed:1',
            action_type='mapping_alias_upsert',
            risk_level='low',
            target_table='master_code_aliases',
            target_key='workshop:精整',
            before_value={'alias_code': '精整车间'},
            after_value={'alias_code': '精整'},
            evidence={'reason': 'matched'},
            status='failed',
            rollback_payload={'restore_before_value': {'alias_code': '精整车间'}},
        )
    )
    db.commit()
    previous_overrides = _install_overrides(db=db, user_role='user')

    try:
        client = TestClient(app)
        response = client.get(f'/api/v1/hermes/data-audit/runs/{run.id}')
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload['decision_gate']['can_apply'] is False
    assert payload['decision_gate']['reason'] == 'no_pending_correction_actions'
    assert payload['decision_gate']['reason'] != 'ready_to_apply'


def test_get_hermes_data_audit_run_keeps_pending_suggestion_when_failed_row_exists(monkeypatch) -> None:
    monkeypatch.setenv('HERMES_DATA_AUDIT_APPLY_ENABLED', 'true')
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-completed-mixed-state',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={'records_count_by_source': {'stock_records': 3}},
        hub_snapshot={'field_count': 1},
        output_skill_snapshot={'parsed': {'total_output': 10}},
        diffs={'total_output': {'status': 'hub_mismatch', 'values': {'mes': 10, 'hub': 8, 'output_skill': 10}}},
        suggested_actions=[
            {
                'idempotency_key': 'suggested:1',
                'action_type': 'mapping_alias_upsert',
                'risk_level': 'low',
                'target_table': 'master_code_aliases',
                'target_key': 'workshop:拉矫',
                'before_value': {'alias_code': '拉矫车间'},
                'after_value': {
                    'entity_type': 'workshop',
                    'canonical_code': '拉矫',
                    'alias_code': '拉矫车间',
                    'alias_name': '拉矫车间',
                    'source_type': 'hermes',
                    'is_active': True,
                },
                'evidence': {'reason': 'matched', 'field': 'alias_code'},
                'rollback_payload': {'restore_before_value': {'alias_code': '拉矫车间'}},
            }
        ],
        match_rate=Decimal('0.5000'),
        created_by_id=1,
    )
    db.add(run)
    db.flush()
    db.add(
        HermesCorrectionAction(
            audit_run_id=run.id,
            idempotency_key='failed:1',
            action_type='mapping_alias_upsert',
            risk_level='low',
            target_table='master_code_aliases',
            target_key='workshop:精整',
            before_value={'alias_code': '精整车间'},
            after_value={'alias_code': '精整'},
            evidence={'reason': 'matched'},
            status='failed',
            rollback_payload={'restore_before_value': {'alias_code': '精整车间'}},
        )
    )
    db.commit()
    previous_overrides = _install_overrides(db=db, user_role='user')

    try:
        client = TestClient(app)
        response = client.get(f'/api/v1/hermes/data-audit/runs/{run.id}')
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    correction_action_keys = {item['idempotency_key'] for item in payload['correction_actions']}
    assert 'failed:1' in correction_action_keys
    assert 'suggested:1' in correction_action_keys
    assert payload['decision_gate']['reason'] != 'no_pending_correction_actions'
    assert payload['decision_gate']['can_apply'] is True
    assert payload['decision_gate']['reason'] == 'ready_to_apply'


def test_get_hermes_data_audit_run_blocks_incomplete_correction_audit_payload(monkeypatch) -> None:
    monkeypatch.setenv('HERMES_DATA_AUDIT_APPLY_ENABLED', 'true')
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-incomplete-audit-payload',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={'records_count_by_source': {'stock_records': 3}},
        hub_snapshot={'field_count': 1},
        output_skill_snapshot={'parsed': {'total_output': 10}},
        diffs={'total_output': {'status': 'hub_mismatch', 'values': {'mes': 10, 'hub': 8, 'output_skill': 10}}},
        suggested_actions=[
            {
                'idempotency_key': 'incomplete:1',
                'action_type': 'mapping_alias_upsert',
                'risk_level': 'low',
                'target_table': 'master_code_aliases',
                'target_key': 'workshop:精整',
                'field_name': 'alias_code',
                'before_value': {'alias_code': '精整车间'},
                'after_value': {
                    'entity_type': 'workshop',
                    'canonical_code': '精整',
                    'alias_code': '精整车间',
                    'alias_name': '精整车间',
                    'source_type': 'hermes',
                    'is_active': True,
                },
                'evidence': {'reason': 'match mes', 'field': 'alias_code'},
            }
        ],
        match_rate=Decimal('0.5000'),
        created_by_id=1,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    previous_overrides = _install_overrides(db=db, user_role='user')

    try:
        client = TestClient(app)
        response = client.get(f'/api/v1/hermes/data-audit/runs/{run.id}')
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload['decision_gate']['can_apply'] is False
    assert payload['decision_gate']['reason'] == 'incomplete_correction_audit_payload'
    assert payload['decision_gate']['reason'] != 'ready_to_apply'
    assert 'before_value' not in payload['correction_actions'][0]
    assert 'after_value' not in payload['correction_actions'][0]
    assert 'evidence' not in payload['correction_actions'][0]
    assert 'rollback_payload' not in payload['correction_actions'][0]


def test_get_hermes_data_audit_run_returns_404_when_missing() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    previous_overrides = _install_overrides(db=db, user_role='manager')

    try:
        client = TestClient(app)
        response = client.get('/api/v1/hermes/data-audit/runs/999')
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 404


def test_admin_can_apply_hermes_data_audit_corrections() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-apply-1',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={'records_count_by_source': {'stock_records': 3}},
        hub_snapshot={'field_count': 2},
        output_skill_snapshot={'parsed': {'total_output': 10}},
        diffs={'total_output': {'status': 'hub_mismatch', 'values': {'mes': 10, 'hub': 8, 'output_skill': 10}}},
        suggested_actions=[
            {
                'idempotency_key': 'alias:1',
                'action_type': 'mapping_alias_upsert',
                'risk_level': 'low',
                'target_table': 'master_code_aliases',
                'target_key': 'workshop:精整',
                'field_name': 'alias_code',
                'before_value': {'alias_code': '精整车间'},
                'after_value': {
                    'entity_type': 'workshop',
                    'canonical_code': '精整',
                    'alias_code': '精整车间',
                    'alias_name': '精整车间',
                    'source_type': 'hermes',
                    'is_active': True,
                },
                'evidence': {'reason': 'match mes', 'field': 'alias_code'},
                'rollback_payload': {'restore_before_value': {'alias_code': '精整车间'}},
            }
        ],
        match_rate=Decimal('0.0000'),
        created_by_id=1,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    service = FakeHermesDataAuditService(db)
    previous_overrides = _install_overrides(db=db, user_role='admin', service=service)

    try:
        client = TestClient(app)
        response = client.post(
            f'/api/v1/hermes/data-audit/runs/{run.id}/corrections',
            json={
                'actions': [
                    {
                        'idempotency_key': 'alias:1',
                        'action_type': 'daily_report_recalculate',
                        'target_table': 'daily_report_runs',
                    }
                ],
                'dry_run': False,
            },
        )
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload['apply_summary']['applied_count'] == 1
    assert payload['decision_gate']['can_apply'] is False
    assert payload['recommended_next_step'] == 'rerun_audit_to_verify'
    assert service.apply_calls[0]['applied_by_id'] == 1
    assert service.apply_calls[0]['actions'] == [run.suggested_actions[0]]


def test_get_hermes_data_audit_run_blocks_executor_unsupported_suggestion(monkeypatch) -> None:
    monkeypatch.setenv('HERMES_DATA_AUDIT_APPLY_ENABLED', 'true')
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-unsupported-suggestion',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={'records_count_by_source': {'stock_records': 3}},
        hub_snapshot={'field_count': 1},
        output_skill_snapshot={'parsed': {'total_output': 10}},
        diffs={'total_output': {'status': 'hub_mismatch', 'values': {'mes': 10, 'hub': 8, 'output_skill': 10}}},
        suggested_actions=[
            {
                'idempotency_key': 'manual-reconcile:1',
                'action_type': 'mapping_reconciliation_run',
                'risk_level': 'low',
                'target_table': 'data_hub_snapshot',
                'target_key': '2026-06-18',
                'before_value': {'business_date': '2026-06-18', 'status': 'pending'},
                'after_value': {'business_date': '2026-06-18', 'status': 'suggested'},
                'evidence': {'reason': 'needs reconcile', 'field': 'business_date'},
                'rollback_payload': {'restore_before_value': {'business_date': '2026-06-18'}},
            }
        ],
        match_rate=Decimal('0.5000'),
        created_by_id=1,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    previous_overrides = _install_overrides(db=db, user_role='user')

    try:
        client = TestClient(app)
        response = client.get(f'/api/v1/hermes/data-audit/runs/{run.id}')
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload['decision_gate']['can_apply'] is False
    assert payload['decision_gate']['reason'] == 'executor_not_supported'
    assert payload['decision_gate']['reason'] != 'ready_to_apply'


def test_apply_hermes_data_audit_corrections_requires_action_selection() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-empty-actions',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={},
        hub_snapshot={},
        output_skill_snapshot={},
        diffs={},
        suggested_actions=[],
        match_rate=Decimal('1.0000'),
        created_by_id=1,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    service = FakeHermesDataAuditService(db)
    previous_overrides = _install_overrides(db=db, user_role='admin', service=service)

    try:
        client = TestClient(app)
        response = client.post(f'/api/v1/hermes/data-audit/runs/{run.id}/corrections', json={})
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 400
    assert response.json()['detail']['reason'] == 'no_actions_selected'


def test_apply_hermes_data_audit_corrections_rejects_unknown_forged_action_payload() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-unknown-forged-action',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={},
        hub_snapshot={},
        output_skill_snapshot={},
        diffs={},
        suggested_actions=[],
        match_rate=Decimal('1.0000'),
        created_by_id=1,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    service = FakeHermesDataAuditService(db)
    previous_overrides = _install_overrides(db=db, user_role='admin', service=service)

    try:
        client = TestClient(app)
        response = client.post(
            f'/api/v1/hermes/data-audit/runs/{run.id}/corrections',
            json={
                'actions': [
                    {
                        'action_type': 'mapping_alias_upsert',
                        'risk_level': 'low',
                        'target_table': 'master_code_aliases',
                        'target_key': 'workshop:精整',
                        'before_value': {'alias_code': '精整车间'},
                        'after_value': {'alias_code': '精整'},
                        'evidence': {'reason': 'forged'},
                        'rollback_payload': {'restore_before_value': {'alias_code': '精整车间'}},
                    }
                ],
                'dry_run': False,
            },
        )
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 400
    assert response.json()['detail']['reason'] == 'unknown_correction_action'
    assert service.apply_calls == []


def test_non_admin_cannot_apply_hermes_data_audit_corrections() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    run = HermesDataAuditRun(
        run_key='run-no-admin',
        business_date=date(2026, 6, 18),
        status='completed',
        source_status={'mes': 'ok', 'hub': 'ok', 'output_skill': 'ok'},
        source_errors={},
        mes_snapshot={},
        hub_snapshot={},
        output_skill_snapshot={},
        diffs={},
        suggested_actions=[],
        match_rate=Decimal('1.0000'),
        created_by_id=1,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    service = FakeHermesDataAuditService(db)
    previous_overrides = _install_overrides(db=db, user_role='manager', service=service)

    try:
        client = TestClient(app)
        response = client.post(
            f'/api/v1/hermes/data-audit/runs/{run.id}/corrections',
            json={'actions': [{'idempotency_key': 'alias:1'}], 'dry_run': False},
        )
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code == 403


def test_anonymous_get_hermes_data_audit_run_requires_authentication() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    previous_overrides = _install_db_override_only(db=db)

    try:
        client = TestClient(app)
        response = client.get('/api/v1/hermes/data-audit/runs/1')
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code in {401, 403}


def test_anonymous_apply_hermes_data_audit_corrections_requires_authentication() -> None:
    engine = _make_engine()
    Base.metadata.create_all(engine, tables=ROUTER_TABLES)
    db = Session(engine)
    previous_overrides = _install_db_override_only(db=db)

    try:
        client = TestClient(app)
        response = client.post('/api/v1/hermes/data-audit/runs/1/corrections', json={})
    finally:
        _restore_overrides(previous_overrides)
        db.close()

    assert response.status_code in {401, 403}
