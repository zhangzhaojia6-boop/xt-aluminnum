from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.services import team_lead_service


router = APIRouter(tags=['team-lead'])


def _require_team_lead_access(current_user: User) -> None:
    if getattr(current_user, 'role', '') not in {'team_leader', 'deputy_leader', 'admin'}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='仅班长可访问')


@router.get('/overview')
def get_team_lead_overview(
    date_value: date = Query(alias='date'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_team_lead_access(current_user)
    return team_lead_service.build_overview(db, leader_user=current_user, target_date=date_value)

