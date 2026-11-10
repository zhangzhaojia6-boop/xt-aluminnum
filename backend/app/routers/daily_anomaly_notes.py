from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.permissions import get_current_manager_user
from app.models.system import User
from app.services.report import daily_anomaly_note_service

router = APIRouter(tags=['daily-anomaly-notes'])


class AnomalyNoteIn(BaseModel):
    content: str


@router.get('/{business_date}')
def read_anomaly_note(
    business_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> dict:
    return daily_anomaly_note_service.read_anomaly_note(db, user=current_user, business_date=business_date)


@router.put('/{business_date}')
def save_anomaly_note(
    business_date: date,
    payload: AnomalyNoteIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return daily_anomaly_note_service.save_anomaly_note(
        db,
        user=current_user,
        business_date=business_date,
        content=payload.content,
    )
