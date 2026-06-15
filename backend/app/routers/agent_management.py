from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.redaction import is_sensitive_key, redact_secret_text
from app.core.scope import build_scope_summary
from app.models.system import User
from app.services import agent_communication_service, agent_knowledge_service, agent_management_overview_service


router = APIRouter(tags=['agent-management'])


class KnowledgeAnswerRequest(BaseModel):
    question: str


def _ensure_agent_management_access(user: User) -> None:
    if not build_scope_summary(user).is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Agent management access denied')


@router.get('/overview')
def overview(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_agent_management_access(current_user)
    return agent_management_overview_service.build_agent_management_overview(db, limit=limit)


@router.get('/knowledge')
def knowledge_entries(current_user: User = Depends(get_current_user)) -> dict:
    _ensure_agent_management_access(current_user)
    items = agent_knowledge_service.list_knowledge_entries()
    return {'total': len(items), 'items': items}


@router.post('/knowledge/answer')
def knowledge_answer(
    payload: KnowledgeAnswerRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    _ensure_agent_management_access(current_user)
    question = str(payload.question or '').strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='question required')
    return agent_knowledge_service.answer_question(question)


@router.post('/outbox/{outbox_message_id}/dispatch')
def dispatch_outbox_message(
    outbox_message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_agent_management_access(current_user)
    try:
        outcome = agent_communication_service.dispatch_outbox_message(db, outbox_message_id)
    except agent_communication_service.AgentCommunicationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=redact_secret_text(str(exc))) from exc
    return {
        'outbox_message_id': outcome.outbox_message_id,
        'status': outcome.status,
        'detail': redact_secret_text(outcome.detail),
    }


@router.post('/outbox/dry-run-smoke')
def dry_run_smoke(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_agent_management_access(current_user)
    outcome = agent_communication_service.run_dry_run_smoke_test(db)
    return {
        'outbox_message_id': outcome.outbox_message_id,
        'status': outcome.status,
        'detail': outcome.detail,
        'log_total': outcome.log_total,
        'channel': {
            'id': outcome.channel_id,
            'name': outcome.channel_name,
            'channel_type': outcome.channel_type,
            'channel_key_masked': _mask_key(outcome.channel_key),
            'dry_run': True,
        },
    }


@router.get('/outbox/{outbox_message_id}/logs')
def outbox_message_logs(
    outbox_message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _ensure_agent_management_access(current_user)
    items = agent_communication_service.list_external_logs(db, outbox_message_id=outbox_message_id)
    return {
        'total': len(items),
        'items': [
            {
                'id': item.id,
                'outbox_message_id': item.outbox_message_id,
                'channel_type': item.channel_type,
                'channel_key_masked': _mask_key(item.channel_key),
                'status': item.status,
                'detail': redact_secret_text(item.detail or ''),
                'provider_message_id': item.provider_message_id,
                'response_payload': _sanitize_external_payload(item.response_payload),
                'created_at': item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
    }


def _mask_key(value: str | None) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    if len(raw) <= 6:
        return f'{raw[:1]}***'
    return f'{raw[:4]}***{raw[-2:]}'


def _sanitize_external_payload(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if is_sensitive_key(key):
                result[key] = '***'
            else:
                result[key] = _sanitize_external_payload(item)
        return result
    if isinstance(value, list):
        return [_sanitize_external_payload(item) for item in value]
    return value
