from __future__ import annotations

from datetime import date
from hashlib import sha256
from typing import Callable, Iterable, Any

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentEvent, AgentOperationApproval
from app.models.reports import DailyReport
from app.models.system import User
from app.services import agent_operation_approval_service as approval_service
from app.services.dingtalk_daily_report import push_daily_report_to_dingtalk


class AgentDesignatedOperationError(RuntimeError):
    pass


DailyReportPublisher = Callable[..., dict[str, Any]]


def request_supplement_production_preview(
    db: Session,
    *,
    requester_user_id: int,
    channel_key: str,
    allowed_user_ids: set[int] | list[int] | tuple[int, ...],
    payload: dict,
    trace_id: str | None = None,
) -> AgentOperationApproval:
    _ensure_allowed(requester_user_id, allowed_user_ids, 'requester_not_allowed')
    business_date = _parse_business_date(payload.get('business_date'))
    tons = _parse_positive_tons(payload.get('tons'))
    workshop_name = _required_text(payload.get('workshop_name'), 'workshop_name_required')
    reason = _required_text(payload.get('reason'), 'reason_required')

    preview_payload = {
        'business_date': business_date.isoformat(),
        'workshop_name': workshop_name,
        'tons': tons,
        'reason': reason,
        'source_type': str(payload.get('source_type') or 'designated_manual_supplement'),
        'source_ref': payload.get('source_ref'),
        'write_target': 'agent_events.production_supplement_requested',
        'changes_core_production_tables': False,
        'changes_mes_original_data': False,
        'requires_manual_apply': True,
    }
    return _request_preview(
        db,
        operation_type='supplement_production',
        requester_user_id=requester_user_id,
        channel_key=channel_key,
        allowed_user_ids=allowed_user_ids,
        preview_payload=preview_payload,
        trace_id=trace_id,
    )


def request_publish_daily_report_preview(
    db: Session,
    *,
    requester_user_id: int,
    channel_key: str,
    allowed_user_ids: set[int] | list[int] | tuple[int, ...],
    report_id: int,
    recipient_user_ids: Iterable[int] | None = None,
    trace_id: str | None = None,
) -> AgentOperationApproval:
    _ensure_allowed(requester_user_id, allowed_user_ids, 'requester_not_allowed')
    report = _get_report(db, report_id)
    body = _required_text(report.final_text_summary, 'report_body_required')
    if report.quality_gate_status == 'blocked':
        raise AgentDesignatedOperationError('report_quality_blocked')

    recipients = [int(item) for item in recipient_user_ids] if recipient_user_ids is not None else None
    preview_payload = {
        'report_id': report.id,
        'report_date': report.report_date.isoformat(),
        'report_type': report.report_type,
        'preview_text': body,
        'final_text_sha256': _text_hash(body),
        'recipient_user_ids': recipients,
        'report_publish_allowed_after_confirmation': True,
    }
    return _request_preview(
        db,
        operation_type='publish_daily_report',
        requester_user_id=requester_user_id,
        channel_key=channel_key,
        allowed_user_ids=allowed_user_ids,
        preview_payload=preview_payload,
        trace_id=trace_id,
    )


def confirm_designated_operation(
    db: Session,
    approval_id: int,
    *,
    approver_user_id: int,
    allowed_user_ids: set[int] | list[int] | tuple[int, ...],
    confirmation_text: str | None = None,
) -> AgentOperationApproval:
    _ensure_allowed(approver_user_id, allowed_user_ids, 'approver_not_allowed')
    try:
        return approval_service.confirm_operation(
            db,
            approval_id,
            approver_user_id=approver_user_id,
            allowed_user_ids=allowed_user_ids,
            confirmation_text=confirmation_text,
        )
    except approval_service.AgentOperationApprovalError as exc:
        raise AgentDesignatedOperationError(str(exc)) from exc


def execute_designated_operation(
    db: Session,
    approval_id: int,
    *,
    executor_user_id: int,
    allowed_user_ids: set[int] | list[int] | tuple[int, ...],
    dry_run: bool = True,
    daily_report_publisher: DailyReportPublisher | None = None,
) -> AgentOperationApproval:
    _ensure_allowed(executor_user_id, allowed_user_ids, 'executor_not_allowed')
    approval = _get_approval(db, approval_id)
    operator = _get_user(db, executor_user_id)

    def executor(_preview: dict) -> dict[str, Any]:
        if approval.operation_type == 'supplement_production':
            return _record_supplement_event(db, approval=approval, operator=operator)
        if approval.operation_type == 'publish_daily_report':
            return _publish_daily_report(
                db,
                approval=approval,
                operator=operator,
                daily_report_publisher=daily_report_publisher or push_daily_report_to_dingtalk,
            )
        raise AgentDesignatedOperationError('unsupported_operation_type')

    try:
        return approval_service.execute_confirmed_operation(
            db,
            approval_id,
            executor=executor,
            dry_run=dry_run,
        )
    except approval_service.AgentOperationApprovalError as exc:
        raise AgentDesignatedOperationError(str(exc)) from exc


def _request_preview(
    db: Session,
    *,
    operation_type: str,
    requester_user_id: int,
    channel_key: str,
    allowed_user_ids: set[int] | list[int] | tuple[int, ...],
    preview_payload: dict,
    trace_id: str | None,
) -> AgentOperationApproval:
    try:
        return approval_service.request_operation_preview(
            db,
            operation_type=operation_type,
            requester_user_id=requester_user_id,
            channel_key=channel_key,
            allowed_user_ids=allowed_user_ids,
            preview_payload=preview_payload,
            trace_id=trace_id,
        )
    except approval_service.AgentOperationApprovalError as exc:
        raise AgentDesignatedOperationError(str(exc)) from exc


def _record_supplement_event(db: Session, *, approval: AgentOperationApproval, operator: User) -> dict[str, Any]:
    payload = _preview_payload(approval)
    business_date = _parse_business_date(payload.get('business_date'))
    event = AgentEvent(
        event_type='production_supplement_requested',
        severity='warning',
        status='pending_manual_apply',
        scope_type='factory',
        source_type='agent_designated_operation',
        source_ref=str(approval.trace_id or approval.id),
        business_date=business_date,
        payload={
            **payload,
            'source_approval_id': approval.id,
            'operator_user_id': operator.id,
            'changes_core_production_tables': False,
            'changes_mes_original_data': False,
        },
    )
    db.add(event)
    db.flush()
    return {
        'write_target': 'agent_events',
        'event_id': event.id,
        'event_status': event.status,
        'changes_core_production_tables': False,
        'changes_mes_original_data': False,
    }


def _publish_daily_report(
    db: Session,
    *,
    approval: AgentOperationApproval,
    operator: User,
    daily_report_publisher: DailyReportPublisher,
) -> dict[str, Any]:
    payload = _preview_payload(approval)
    report = _get_report(db, int(payload.get('report_id') or 0))
    body = _required_text(report.final_text_summary, 'report_body_required')
    if _text_hash(body) != payload.get('final_text_sha256'):
        raise AgentDesignatedOperationError('report_preview_changed')
    try:
        return dict(
            daily_report_publisher(
                db=db,
                report_id=report.id,
                operator=operator,
                recipient_user_ids=payload.get('recipient_user_ids'),
            )
            or {}
        )
    except AgentDesignatedOperationError:
        raise
    except Exception as exc:
        raise AgentDesignatedOperationError(f'publish_failed:{exc}') from exc


def _preview_payload(approval: AgentOperationApproval) -> dict[str, Any]:
    preview = approval.preview_payload if isinstance(approval.preview_payload, dict) else {}
    payload = preview.get('payload')
    if not isinstance(payload, dict):
        raise AgentDesignatedOperationError('preview_payload_required')
    return dict(payload)


def _get_approval(db: Session, approval_id: int) -> AgentOperationApproval:
    approval = db.get(AgentOperationApproval, int(approval_id))
    if approval is None:
        raise AgentDesignatedOperationError('approval_not_found')
    return approval


def _get_report(db: Session, report_id: int) -> DailyReport:
    report = db.get(DailyReport, int(report_id))
    if report is None:
        raise AgentDesignatedOperationError('report_not_found')
    return report


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise AgentDesignatedOperationError('executor_not_found')
    return user


def _ensure_allowed(user_id: int, allowed_user_ids: set[int] | list[int] | tuple[int, ...], code: str) -> None:
    if int(user_id) not in {int(item) for item in allowed_user_ids}:
        raise AgentDesignatedOperationError(code)


def _parse_business_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or '').strip())
    except ValueError as exc:
        raise AgentDesignatedOperationError('business_date_required') from exc


def _parse_positive_tons(value: Any) -> float:
    try:
        tons = float(value)
    except (TypeError, ValueError) as exc:
        raise AgentDesignatedOperationError('tons_required') from exc
    if tons <= 0:
        raise AgentDesignatedOperationError('tons_required')
    return tons


def _required_text(value: Any, code: str) -> str:
    text = str(value or '').strip()
    if not text:
        raise AgentDesignatedOperationError(code)
    return text


def _text_hash(value: str) -> str:
    return sha256(value.encode('utf-8')).hexdigest()
