from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.services import assistant_action_service


router = APIRouter(tags=['assistant-actions'])


class AssistantActionIn(BaseModel):
    action: str
    target_type: str
    target_id: int | str | None = None
    label: str | None = None
    reason: str | None = None
    target_date: str | None = None
    business_date: str | None = None
    machine_id: int | str | None = None
    shift_id: int | str | None = None
    shift_config_id: int | str | None = None
    report_id: int | str | None = None
    entry_id: int | str | None = None


@router.post('/assistant/actions')
def execute_assistant_action(
    payload: AssistantActionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return assistant_action_service.execute_action(
        db=db,
        user=current_user,
        action_payload=payload.model_dump(exclude_none=True),
    )
