from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
from app.models.system import User
from app.services import agent_knowledge_service, agent_management_overview_service


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
