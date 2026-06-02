from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentDecision
from app.core.field_lock import get_fields_to_lock
from app.core.scope import ScopeSummary, build_scope_summary
from app.models.master import Equipment, Workshop
from app.models.production import MobileShiftReport, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import pilot_observability_service


ActionHandler = Callable[..., list[AgentDecision]]


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='处置日期不正确')


def _parse_int(value: Any, *, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{field_name}不正确')


def _decision_out(decision: AgentDecision) -> dict:
    return {
        'agent_name': decision.agent_name,
        'action': decision.action.value,
        'target_type': decision.target_type,
        'target_id': decision.target_id,
        'reason': decision.reason,
        'details': decision.details,
        'timestamp': decision.timestamp.isoformat(),
    }


def _commit_if_possible(db: Session) -> None:
    commit = getattr(db, 'commit', None)
    if callable(commit):
        commit()


def _rollback_if_possible(db: Session) -> None:
    rollback = getattr(db, 'rollback', None)
    if callable(rollback):
        rollback()


def _workshop_code_for_report(db: Session, report: MobileShiftReport) -> str | None:
    if not getattr(report, 'workshop_id', None):
        return None
    workshop = db.query(Workshop).filter(Workshop.id == report.workshop_id).first()
    return str(workshop.code) if workshop and workshop.code else None


def _call_validator(*, db: Session, payload: dict[str, Any]) -> list[AgentDecision]:
    from app.agents.validator import validator_agent

    report_id = _parse_int(payload.get('report_id') or payload.get('target_id'), field_name='report_id')
    report = db.query(MobileShiftReport).filter(MobileShiftReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='填报记录不存在')
    report_data = {
        'attendance_count': report.attendance_count,
        'input_weight': report.input_weight,
        'output_weight': report.output_weight,
        'scrap_weight': report.scrap_weight,
        'electricity_daily': report.electricity_daily,
        'gas_daily': report.gas_daily,
    }
    return validator_agent.execute(
        db=db,
        report_id=report_id,
        report_data=report_data,
        workshop_code=_workshop_code_for_report(db, report),
    )


def _call_reconciler(*, db: Session, payload: dict[str, Any]) -> list[AgentDecision]:
    from app.agents.reconciler import reconciler_agent

    target_date = _parse_date(payload.get('target_date') or payload.get('target_id'))
    return reconciler_agent.execute(db=db, target_date=target_date)


def _call_reminder(*, db: Session, payload: dict[str, Any]) -> list[AgentDecision]:
    from app.agents.reminder import reminder_agent

    target_date = _parse_date(payload.get('target_date') or payload.get('business_date') or payload.get('date'))
    shift_config_id = payload.get('shift_config_id')
    if shift_config_id is None and payload.get('target_type') == 'shift_config':
        shift_config_id = payload.get('target_id')
    return reminder_agent.execute(
        db=db,
        target_date=target_date,
        shift_config_id=_parse_int(shift_config_id, field_name='shift_config_id') if shift_config_id is not None else None,
    )


def _call_aggregator(*, db: Session, payload: dict[str, Any]) -> list[AgentDecision]:
    from app.agents.aggregator import aggregator_agent

    target_date = _parse_date(payload.get('target_date') or payload.get('target_id'))
    return aggregator_agent.execute(db=db, target_date=target_date)


def _active_machine_candidates(db: Session, *, workshop_id: int) -> list[Equipment]:
    rows = (
        db.query(Equipment)
        .filter(
            Equipment.workshop_id == workshop_id,
            Equipment.is_active.is_(True),
            Equipment.operational_status == 'running',
        )
        .order_by(Equipment.sort_order.asc(), Equipment.id.asc())
        .all()
    )
    return [
        item
        for item in rows
        if str(item.equipment_type or '').strip().lower() not in {'virtual_workshop_qr', 'virtual_role_qr'}
    ]


def _resolve_target_machine(db: Session, *, entry: WorkOrderEntry, raw_machine_id: Any) -> Equipment:
    if raw_machine_id is not None:
        machine_id = _parse_int(raw_machine_id, field_name='machine_id')
        machine = db.get(Equipment, machine_id)
        if machine is None or not machine.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='机列不存在')
        if int(machine.workshop_id) != int(entry.workshop_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='机列不属于该车间')
        if str(machine.equipment_type or '').strip().lower() in {'virtual_workshop_qr', 'virtual_role_qr'}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='不能绑定虚拟入口')
        return machine

    candidates = _active_machine_candidates(db, workshop_id=entry.workshop_id)
    if len(candidates) == 1:
        return candidates[0]
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='请选择机列')


def _promote_draft_entry(*, db: Session, payload: dict[str, Any]) -> list[AgentDecision]:
    entry_id = _parse_int(payload.get('entry_id') or payload.get('target_id'), field_name='entry_id')
    entry = db.query(WorkOrderEntry).filter(WorkOrderEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='填报记录不存在')
    if entry.entry_status != 'draft':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='仅草稿可提升')

    if entry.machine_id is None:
        machine = _resolve_target_machine(db, entry=entry, raw_machine_id=payload.get('machine_id'))
        entry.machine_id = machine.id
    else:
        machine = db.get(Equipment, entry.machine_id)

    if entry.shift_id is None:
        raw_shift_id = payload.get('shift_id') or payload.get('shift_config_id')
        if raw_shift_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='请选择班次')
        shift_id = _parse_int(raw_shift_id, field_name='shift_id')
        if db.get(ShiftConfig, shift_id) is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='班次不存在')
        entry.shift_id = shift_id

    entry.entry_status = 'submitted'
    entry.submitted_at = datetime.now(timezone.utc)
    locked_fields = set(entry.locked_fields or [])
    locked_fields.update(get_fields_to_lock('work_order_entries', 'machine_operator'))
    entry.locked_fields = sorted(locked_fields)
    extra_payload = dict(entry.extra_payload or {})
    extra_payload['pending_assignment_action'] = {
        'action': 'promote_draft_entry',
        'machine_id': entry.machine_id,
        'shift_id': entry.shift_id,
        'promoted_at': entry.submitted_at.isoformat(),
    }
    entry.extra_payload = extra_payload
    db.flush()

    from app.services.mobile_report.summary import _aggregate_coil_to_shift

    _aggregate_coil_to_shift(
        db,
        business_date=entry.business_date,
        shift_id=entry.shift_id,
        workshop_id=entry.workshop_id,
        machine_id=entry.machine_id,
    )

    return [
        AgentDecision(
            agent_name='assistant_action',
            action=AgentAction.AUTO_CONFIRM,
            target_type='work_order_entry',
            target_id=entry.id,
            reason='promote_draft_entry',
            details={
                'machine_id': entry.machine_id,
                'machine_name': machine.name if machine is not None else None,
                'shift_id': entry.shift_id,
                'business_date': entry.business_date.isoformat(),
            },
        )
    ]


ACTION_REGISTRY: dict[str, ActionHandler] = {
    'call_validator': _call_validator,
    'call_reconciler': _call_reconciler,
    'call_reminder': _call_reminder,
    'call_aggregator': _call_aggregator,
    'promote_draft_entry': _promote_draft_entry,
}
GLOBAL_ACTIONS = {'call_reconciler', 'call_aggregator'}
ACTION_MANAGER_ROLES = {'admin', 'manager', 'factory_director', 'senior_manager'}


def _require_admin_or_manager(user: User) -> None:
    role = getattr(user, 'role', '')
    if role not in ACTION_MANAGER_ROLES and not bool(getattr(user, 'is_manager', False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='仅管理员或管理者可处置')


def _raw_data_scope_type(user: User) -> str:
    return str(getattr(user, 'data_scope_type', '') or '').strip().lower()


def _has_explicit_global_action_scope(user: User, scope: ScopeSummary) -> bool:
    role = str(getattr(user, 'role', '') or '').strip()
    if scope.is_admin or role in {'factory_director', 'senior_manager'}:
        return True
    return _raw_data_scope_type(user) == 'all' and (role == 'manager' or bool(getattr(user, 'is_manager', False)))


def _row_matches_scope(scope: ScopeSummary, row) -> bool:
    if scope.is_admin or scope.data_scope_type == 'all':
        return True

    row_workshop_id = getattr(row, 'workshop_id', None)
    row_team_id = getattr(row, 'team_id', None)
    row_shift_id = getattr(row, 'shift_config_id', None)
    if row_shift_id is None:
        row_shift_id = getattr(row, 'shift_id', None)

    if scope.data_scope_type == 'assigned':
        if row_shift_id is None or int(row_shift_id) not in scope.assigned_shift_ids:
            return False
    if scope.workshop_id is not None and row_workshop_id is not None and int(row_workshop_id) != int(scope.workshop_id):
        return False
    if scope.data_scope_type == 'self_team' and scope.team_id is not None:
        return row_team_id is not None and int(row_team_id) == int(scope.team_id)
    return scope.workshop_id is not None and row_workshop_id is not None


def _report_in_scope(db: Session, *, report_id: int, scope: ScopeSummary) -> bool:
    report = db.query(MobileShiftReport).filter(MobileShiftReport.id == report_id).first()
    if report is None:
        return True
    return _row_matches_scope(scope, report)


def _shift_in_scope(db: Session, *, shift_config_id: int, scope: ScopeSummary) -> bool:
    shift = db.query(ShiftConfig).filter(ShiftConfig.id == shift_config_id).first()
    if shift is None:
        return True
    if scope.is_admin or scope.data_scope_type == 'all':
        return True
    if scope.data_scope_type == 'assigned' and int(shift_config_id) not in scope.assigned_shift_ids:
        return False
    shift_workshop_id = getattr(shift, 'workshop_id', None)
    return scope.workshop_id is not None and shift_workshop_id is not None and int(shift_workshop_id) == int(scope.workshop_id)


def _entry_in_scope(db: Session, *, entry_id: int, scope: ScopeSummary) -> bool:
    entry = db.query(WorkOrderEntry).filter(WorkOrderEntry.id == entry_id).first()
    if entry is None:
        return True
    return _row_matches_scope(scope, entry)


def _require_action_scope(db: Session, *, user: User, action: str, payload: dict[str, Any]) -> None:
    scope = build_scope_summary(user)
    if scope.is_admin or _has_explicit_global_action_scope(user, scope):
        return
    if scope.data_scope_type == 'all':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='当前账号未绑定处置范围')

    if action in GLOBAL_ACTIONS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='当前账号无权执行全厂处置')

    if action == 'call_validator':
        report_id = _parse_int(payload.get('report_id') or payload.get('target_id'), field_name='report_id')
        if not _report_in_scope(db, report_id=report_id, scope=scope):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='当前账号无权处置该记录')
        return

    if action == 'call_reminder':
        shift_config_id = payload.get('shift_config_id')
        if shift_config_id is None and payload.get('target_type') == 'shift_config':
            shift_config_id = payload.get('target_id')
        if shift_config_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='当前账号无权执行全厂催报')
        if not _shift_in_scope(db, shift_config_id=_parse_int(shift_config_id, field_name='shift_config_id'), scope=scope):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='当前账号无权处置该班次')
        return

    if action == 'promote_draft_entry':
        entry_id = _parse_int(payload.get('entry_id') or payload.get('target_id'), field_name='entry_id')
        if not _entry_in_scope(db, entry_id=entry_id, scope=scope):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='当前账号无权处置该填报记录')


def execute_action(*, db: Session, user: User, action_payload: dict[str, Any]) -> dict[str, Any]:
    action = str(action_payload.get('action') or '').strip()
    target_type = str(action_payload.get('target_type') or '').strip()
    target_id = action_payload.get('target_id')
    success = False
    error_text = ''

    try:
        _require_admin_or_manager(user)
        handler = ACTION_REGISTRY.get(action)
        if handler is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='未知处置动作')
        _require_action_scope(db, user=user, action=action, payload=action_payload)
        decisions = handler(db=db, payload=action_payload)
        _commit_if_possible(db)
        success = True
        return {'decisions': [_decision_out(decision) for decision in decisions]}
    except Exception as exc:
        _rollback_if_possible(db)
        error_text = getattr(exc, 'detail', None) or str(exc)
        raise
    finally:
        pilot_observability_service.log_pilot_event(
            'assistant_action_invoked',
            user_id=getattr(user, 'id', None),
            action=action,
            target_type=target_type,
            target_id=target_id,
            success=success,
            error=error_text,
        )
