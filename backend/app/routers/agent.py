from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.redaction import redact_secret_text
from app.core.scope import build_scope_summary, can_request_workshop_scope
from app.models.agent_communication import CommunicationChannel
from app.models.system import User
from app.services.agent_command_service import AgentCommandError, handle_agent_command


router = APIRouter(tags=['agent'])


class AgentCommandRequest(BaseModel):
    channel: str = 'internal'
    group_id: str | None = None
    sender_external_id: str | None = None
    text: str
    agent_code: str | None = None
    trace_id: str | None = None
    workshop: str | None = None
    machine_code: str | None = None
    queue_outbox: bool = False
    source_payload: dict[str, Any] | None = None


def _ensure_agent_command_access(user: User) -> None:
    scope = build_scope_summary(user)
    if not (scope.is_admin or scope.is_manager or scope.is_reviewer):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Agent command access denied')


def _ensure_agent_command_channel_scope_access(user: User, db: Session, payload: AgentCommandRequest) -> None:
    group_id = str(payload.group_id or '').strip()
    if not group_id:
        return

    channel = (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_type == (str(payload.channel or '').strip() or 'internal'),
            CommunicationChannel.channel_key == group_id,
            CommunicationChannel.is_active.is_(True),
        )
        .first()
    )
    if channel is None or channel.workshop_id is None:
        return

    scope = build_scope_summary(user)
    if scope.is_admin or scope.data_scope_type == 'all':
        return
    if scope.workshop_id is not None and int(scope.workshop_id) == int(channel.workshop_id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='Agent command channel scope denied',
    )


def _ensure_agent_command_requested_workshop_access(user: User, db: Session, payload: AgentCommandRequest) -> None:
    if can_request_workshop_scope(user, db, payload.workshop):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='Agent command workshop scope denied',
    )


@router.post('/command')
def agent_command(
    payload: AgentCommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_agent_command_access(current_user)
    _ensure_agent_command_requested_workshop_access(current_user, db, payload)
    _ensure_agent_command_channel_scope_access(current_user, db, payload)
    try:
        result = handle_agent_command(
            db,
            channel=payload.channel,
            group_id=payload.group_id,
            sender_external_id=payload.sender_external_id,
            text=payload.text,
            agent_code=payload.agent_code,
            trace_id=payload.trace_id,
            workshop=payload.workshop,
            machine_code=payload.machine_code,
            queue_outbox=payload.queue_outbox,
            source_payload=payload.source_payload,
            current_user=current_user,
        )
        db.commit()
    except AgentCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=redact_secret_text(str(exc))) from exc
    except Exception:
        db.rollback()
        raise

    return {
        'trace_id': result.trace_id,
        'status_color': result.status_color,
        'intent': result.intent,
        'facts': result.facts,
        'answer': result.answer,
        'rag': result.rag,
        'chat_inbox_id': result.chat_inbox_id,
        'agent_run_id': result.agent_run_id,
        'outbox_message_id': result.outbox_message_id,
    }
