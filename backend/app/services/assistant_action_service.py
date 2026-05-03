from __future__ import annotations

from datetime import date
from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agents.base import AgentDecision
from app.core.scope import ScopeSummary, build_scope_summary
from app.models.master import Workshop
from app.models.production import MobileShiftReport
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


ACTION_REGISTRY: dict[str, ActionHandler] = {
    'call_validator': _call_validator,
    'call_reconciler': _call_reconciler,
    'call_reminder': _call_reminder,
    'call_aggregator': _call_aggregator,
}


def _require_admin_or_manager(user: User) -> None:
    role = getattr(user, 'role', '')
    if role not in {'admin', 'manager'} and not bool(getattr(user, 'is_manager', False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='仅管理员或管理者可处置')


def _row_matches_scope(scope: ScopeSummary, row) -> bool:
    if scope.is_admin or scope.data_scope_type == 'all':
        return True

    row_workshop_id = getattr(row, 'workshop_id', None)
    row_team_id = getattr(row, 'team_id', None)
    row_shift_id = getattr(row, 'shift_config_id', None)

    if scope.data_scope_type == 'assigned':
        if scope.assigned_shift_ids and row_shift_id is not None and int(row_shift_id) not in scope.assigned_shift_ids:
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
    shift_workshop_id = getattr(shift, 'workshop_id', None)
    return scope.workshop_id is not None and shift_workshop_id is not None and int(shift_workshop_id) == int(scope.workshop_id)


def _require_action_scope(db: Session, *, user: User, action: str, payload: dict[str, Any]) -> None:
    scope = build_scope_summary(user)
    if scope.is_admin or scope.data_scope_type == 'all':
        return

    if action in {'call_reconciler', 'call_aggregator'}:
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
