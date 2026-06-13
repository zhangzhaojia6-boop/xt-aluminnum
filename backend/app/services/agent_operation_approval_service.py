from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentOperationApproval, CommunicationChannel


class AgentOperationApprovalError(RuntimeError):
    pass


SUPPORTED_OPERATION_TYPES = {'supplement_production', 'publish_daily_report'}


def request_operation_preview(
    db: Session,
    *,
    operation_type: str,
    requester_user_id: int,
    channel_key: str,
    allowed_user_ids: set[int] | list[int] | tuple[int, ...],
    preview_payload: dict,
    trace_id: str | None = None,
) -> AgentOperationApproval:
    clean_operation = str(operation_type or '').strip()
    if clean_operation not in SUPPORTED_OPERATION_TYPES:
        raise AgentOperationApprovalError('unsupported_operation_type')
    if int(requester_user_id) not in _allowed_set(allowed_user_ids):
        raise AgentOperationApprovalError('requester_not_allowed')
    if not preview_payload:
        raise AgentOperationApprovalError('preview_payload_required')

    channel = _get_active_channel(db, channel_key)
    safe_preview = {
        'operation_type': clean_operation,
        'payload': dict(preview_payload),
        'requires_confirmation': True,
        'metric_write_allowed': False,
        'report_publish_allowed': False,
        'channel_scope': {
            'target_type': channel.target_type,
            'target_key': channel.target_key,
            'workshop_id': channel.workshop_id,
            'team_id': channel.team_id,
        },
    }
    approval = AgentOperationApproval(
        operation_type=clean_operation,
        status='pending_confirmation',
        requester_user_id=int(requester_user_id),
        channel_id=channel.id,
        preview_payload=safe_preview,
        result_payload={
            'actual_write': False,
            'execution_status': 'not_executed',
        },
        trace_id=trace_id or uuid4().hex,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


def confirm_operation(
    db: Session,
    approval_id: int,
    *,
    approver_user_id: int,
    allowed_user_ids: set[int] | list[int] | tuple[int, ...],
    confirmation_text: str | None = None,
) -> AgentOperationApproval:
    approval = _get_approval(db, approval_id)
    if int(approver_user_id) not in _allowed_set(allowed_user_ids):
        raise AgentOperationApprovalError('approver_not_allowed')
    if approval.status != 'pending_confirmation':
        raise AgentOperationApprovalError('approval_not_pending')

    approval.status = 'confirmed'
    approval.approver_user_id = int(approver_user_id)
    approval.result_payload = {
        **(approval.result_payload or {}),
        'actual_write': False,
        'execution_status': 'confirmed_waiting_execution',
        'confirmation_text': confirmation_text,
    }
    db.commit()
    db.refresh(approval)
    return approval


def execute_confirmed_operation(
    db: Session,
    approval_id: int,
    *,
    executor=None,
    dry_run: bool = True,
) -> AgentOperationApproval:
    approval = _get_approval(db, approval_id)
    if approval.status != 'confirmed':
        raise AgentOperationApprovalError('operation_not_confirmed')

    if dry_run:
        approval.status = 'dry_run_executed'
        approval.result_payload = {
            **(approval.result_payload or {}),
            'execution_mode': 'dry_run',
            'execution_status': 'dry_run_executed',
            'actual_write': False,
        }
        db.commit()
        db.refresh(approval)
        return approval

    if executor is None:
        raise AgentOperationApprovalError('executor_required')

    result = executor(dict(approval.preview_payload or {}))
    approval.status = 'executed'
    approval.result_payload = {
        **(approval.result_payload or {}),
        'execution_mode': 'real',
        'execution_status': 'executed',
        'actual_write': True,
        'executor_result': dict(result or {}),
    }
    db.commit()
    db.refresh(approval)
    return approval


def _get_active_channel(db: Session, channel_key: str) -> CommunicationChannel:
    channel = (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_key == str(channel_key).strip(),
            CommunicationChannel.channel_type == 'dingtalk_group',
            CommunicationChannel.is_active.is_(True),
        )
        .first()
    )
    if channel is None:
        raise AgentOperationApprovalError('channel_not_found')
    if channel.target_type not in {'management', 'workshop'}:
        raise AgentOperationApprovalError('channel_scope_not_allowed')
    return channel


def _get_approval(db: Session, approval_id: int) -> AgentOperationApproval:
    approval = db.get(AgentOperationApproval, int(approval_id))
    if approval is None:
        raise AgentOperationApprovalError('approval_not_found')
    return approval


def _allowed_set(values: set[int] | list[int] | tuple[int, ...]) -> set[int]:
    return {int(value) for value in values}
