from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.base import AgentAction, AgentDecision
from app.database import Base
from app.models.master import Equipment, Workshop
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import assistant_action_service


class _FakeDB:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True


class _FakeQuery:
    def __init__(self, row) -> None:
        self.row = row

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.row


class _FakeScopedDB(_FakeDB):
    def __init__(self, *, report=None, shift=None) -> None:
        super().__init__()
        self.report = report
        self.shift = shift

    def query(self, model):
        model_name = getattr(model, '__name__', '')
        if model_name == 'MobileShiftReport':
            return _FakeQuery(self.report)
        if model_name == 'ShiftConfig':
            return _FakeQuery(self.shift)
        return _FakeQuery(None)


def _build_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'assistant-action.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            ShiftConfig.__table__,
            User.__table__,
            Equipment.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            ShiftProductionData.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True)()


def test_execute_action_promotes_pending_assignment_draft_and_aggregates(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda *args, **kwargs: None,
    )
    try:
        workshop = Workshop(id=1, code='LZ2050', name='2050冷轧车间', workshop_type='cold_roll')
        shift = ShiftConfig(
            id=3,
            code='N',
            name='夜班',
            shift_type='night',
            start_time=time(0, 0),
            end_time=time(8, 0),
            is_cross_day=False,
            sort_order=3,
            is_active=True,
        )
        manager = User(
            id=9,
            username='manager',
            password_hash='x',
            name='管理者',
            role='manager',
            data_scope_type='all',
            is_manager=True,
            is_active=True,
        )
        machine = Equipment(
            id=101,
            code='LZ2050-01',
            name='2050轧机',
            workshop_id=workshop.id,
            equipment_type='rolling_mill',
            operational_status='running',
            is_active=True,
        )
        work_order = WorkOrder(id=501, tracking_card_no='PENDING-001', process_route_code='mobile', overall_status='created')
        entry = WorkOrderEntry(
            id=701,
            work_order_id=work_order.id,
            workshop_id=workshop.id,
            machine_id=None,
            shift_id=shift.id,
            business_date=date(2026, 5, 6),
            input_weight=100000,
            output_weight=96000,
            scrap_weight=4000,
            entry_type='mobile_coil',
            entry_status='draft',
        )
        db.add_all([workshop, shift, manager, machine, work_order, entry])
        db.commit()

        result = assistant_action_service.execute_action(
            db=db,
            user=manager,
            action_payload={
                'action': 'promote_draft_entry',
                'target_type': 'work_order_entry',
                'target_id': entry.id,
            },
        )

        db.refresh(entry)
        assert result['decisions'][0]['action'] == 'auto_confirm'
        assert entry.entry_status == 'submitted'
        assert entry.machine_id == machine.id
        assert entry.submitted_at is not None
        assert entry.extra_payload['pending_assignment_action']['action'] == 'promote_draft_entry'
        # mobile_coil_agg dual-write retired — no aggregate row expected
        assert db.query(ShiftProductionData).count() == 0
    finally:
        db.close()


def test_execute_action_requires_machine_when_candidates_are_ambiguous(tmp_path, monkeypatch) -> None:
    db = _build_session(tmp_path)
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda *args, **kwargs: None,
    )
    try:
        workshop = Workshop(id=1, code='LZ2050', name='2050冷轧车间', workshop_type='cold_roll')
        shift = ShiftConfig(
            id=3,
            code='N',
            name='夜班',
            shift_type='night',
            start_time=time(0, 0),
            end_time=time(8, 0),
            is_cross_day=False,
            sort_order=3,
            is_active=True,
        )
        manager = User(
            id=9,
            username='manager',
            password_hash='x',
            name='管理者',
            role='manager',
            data_scope_type='all',
            is_manager=True,
        )
        machines = [
            Equipment(id=101, code='LZ2050-01', name='1#机', workshop_id=1, equipment_type='rolling_mill', operational_status='running', is_active=True),
            Equipment(id=102, code='LZ2050-02', name='2#机', workshop_id=1, equipment_type='rolling_mill', operational_status='running', is_active=True),
        ]
        work_order = WorkOrder(id=501, tracking_card_no='PENDING-002', process_route_code='mobile', overall_status='created')
        entry = WorkOrderEntry(
            id=701,
            work_order_id=work_order.id,
            workshop_id=workshop.id,
            machine_id=None,
            shift_id=shift.id,
            business_date=date(2026, 5, 6),
            input_weight=100000,
            output_weight=96000,
            entry_type='mobile_coil',
            entry_status='draft',
        )
        db.add_all([workshop, shift, manager, *machines, work_order, entry])
        db.commit()

        with pytest.raises(HTTPException) as exc:
            assistant_action_service.execute_action(
                db=db,
                user=manager,
                action_payload={
                    'action': 'promote_draft_entry',
                    'target_type': 'work_order_entry',
                    'target_id': entry.id,
                },
            )

        assert exc.value.status_code == 400
        assert exc.value.detail == '请选择机列'
        db.refresh(entry)
        assert entry.entry_status == 'draft'
        assert db.query(ShiftProductionData).count() == 0
    finally:
        db.close()


def test_execute_action_routes_to_registered_agent_and_logs(monkeypatch) -> None:
    events = []
    db = _FakeDB()

    def fake_handler(*, db, payload):
        assert isinstance(db, _FakeDB)
        assert payload['target_id'] == '2026-05-03'
        return [
            AgentDecision(
                agent_name='reconciler',
                action=AgentAction.AUTO_RECONCILE,
                target_type='business_date',
                target_id=20260503,
                reason='ok',
            )
        ]

    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {'call_reconciler': fake_handler})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda event_name, **fields: events.append((event_name, fields)),
    )

    result = assistant_action_service.execute_action(
        db=db,
        user=SimpleNamespace(id=7, role='manager', data_scope_type='all'),
        action_payload={'action': 'call_reconciler', 'target_type': 'business_date', 'target_id': '2026-05-03'},
    )

    assert result['decisions'][0]['action'] == 'auto_reconcile'
    assert db.committed is True
    assert events[0][0] == 'assistant_action_invoked'
    assert events[0][1]['user_id'] == 7
    assert events[0][1]['success'] is True


def test_execute_action_rejects_implicit_global_manager_without_scope(monkeypatch) -> None:
    called = False

    def fake_handler(*, db, payload):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {'call_reconciler': fake_handler})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda *args, **kwargs: None,
    )

    with pytest.raises(HTTPException) as exc:
        assistant_action_service.execute_action(
            db=_FakeDB(),
            user=SimpleNamespace(id=7, role='manager'),
            action_payload={'action': 'call_reconciler', 'target_type': 'business_date', 'target_id': '2026-05-03'},
        )

    assert exc.value.status_code == 403
    assert called is False


def test_execute_action_rejects_non_manager_and_logs(monkeypatch) -> None:
    events = []
    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda event_name, **fields: events.append((event_name, fields)),
    )

    with pytest.raises(HTTPException) as exc:
        assistant_action_service.execute_action(
            db='db',
            user=SimpleNamespace(id=8, role='team_leader'),
            action_payload={'action': 'call_reconciler', 'target_type': 'business_date', 'target_id': '2026-05-03'},
        )

    assert exc.value.status_code == 403
    assert events[0][0] == 'assistant_action_invoked'
    assert events[0][1]['success'] is False


def test_execute_action_rejects_scoped_manager_outside_report(monkeypatch) -> None:
    called = False
    db = _FakeScopedDB(report=SimpleNamespace(id=91, workshop_id=2, team_id=20, shift_config_id=3))

    def fake_handler(*, db, payload):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {'call_validator': fake_handler})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda *args, **kwargs: None,
    )

    with pytest.raises(HTTPException) as exc:
        assistant_action_service.execute_action(
            db=db,
            user=SimpleNamespace(
                id=7,
                role='manager',
                workshop_id=1,
                team_id=None,
                data_scope_type='self_workshop',
                is_manager=True,
            ),
            action_payload={'action': 'call_validator', 'target_type': 'mobile_shift_report', 'target_id': 91},
        )

    assert exc.value.status_code == 403
    assert called is False
    assert db.committed is False


def test_execute_action_rejects_scoped_manager_global_date_action(monkeypatch) -> None:
    called = False

    def fake_handler(*, db, payload):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {'call_reconciler': fake_handler})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda *args, **kwargs: None,
    )

    with pytest.raises(HTTPException) as exc:
        assistant_action_service.execute_action(
            db=_FakeDB(),
            user=SimpleNamespace(
                id=7,
                role='manager',
                workshop_id=1,
                team_id=None,
                data_scope_type='self_workshop',
                is_manager=True,
            ),
            action_payload={'action': 'call_reconciler', 'target_type': 'business_date', 'target_id': '2026-05-03'},
        )

    assert exc.value.status_code == 403
    assert called is False


def test_execute_action_rejects_assigned_manager_unassigned_shift_reminder(monkeypatch) -> None:
    called = False
    db = _FakeScopedDB(shift=SimpleNamespace(id=5, workshop_id=1))

    def fake_handler(*, db, payload):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(assistant_action_service, 'ACTION_REGISTRY', {'call_reminder': fake_handler})
    monkeypatch.setattr(
        assistant_action_service.pilot_observability_service,
        'log_pilot_event',
        lambda *args, **kwargs: None,
    )

    with pytest.raises(HTTPException) as exc:
        assistant_action_service.execute_action(
            db=db,
            user=SimpleNamespace(
                id=7,
                role='manager',
                workshop_id=1,
                team_id=None,
                data_scope_type='assigned',
                assigned_shift_ids=[1],
                is_manager=True,
            ),
            action_payload={
                'action': 'call_reminder',
                'target_type': 'shift_config',
                'target_id': 5,
                'target_date': '2026-05-03',
            },
        )

    assert exc.value.status_code == 403
    assert called is False
