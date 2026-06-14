from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
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
    queue_outbox: bool = False
    source_payload: dict[str, Any] | None = None


def _ensure_agent_command_access(user: User) -> None:
    scope = build_scope_summary(user)
    if not (scope.is_admin or scope.is_manager or scope.is_reviewer):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Agent command access denied')


@router.post('/command')
def agent_command(
    payload: AgentCommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_agent_command_access(current_user)
    try:
        result = handle_agent_command(
            db,
            channel=payload.channel,
            group_id=payload.group_id,
            sender_external_id=payload.sender_external_id,
            text=payload.text,
            agent_code=payload.agent_code,
            trace_id=payload.trace_id,
            queue_outbox=payload.queue_outbox,
            source_payload=payload.source_payload,
            current_user=current_user,
        )
        db.commit()
    except AgentCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    return {
        'trace_id': result.trace_id,
        'status_color': result.status_color,
        'answer': result.answer,
        'rag': result.rag,
        'chat_inbox_id': result.chat_inbox_id,
        'agent_run_id': result.agent_run_id,
        'outbox_message_id': result.outbox_message_id,
    }
