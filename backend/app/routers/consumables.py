from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.services import consumable_service


router = APIRouter(tags=['consumables'])


class ConsumableUpsertRequest(BaseModel):
    workshop_id: int = Field(..., gt=0)
    business_date: date
    payload: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


@router.get('/consumables/workshops')
def list_workshops_with_consumables(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _ = current_user
    return {'items': consumable_service.list_workshops_with_consumables(db)}


@router.get('/consumables/daily')
def get_daily_consumable_log(
    workshop_id: int = Query(..., gt=0),
    business_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _ = current_user
    return consumable_service.get_daily_log(
        db,
        workshop_id=workshop_id,
        business_date=business_date,
    )


@router.post('/consumables/daily')
def upsert_daily_consumable_log(
    body: ConsumableUpsertRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return consumable_service.upsert_daily_log(
        db,
        workshop_id=body.workshop_id,
        business_date=body.business_date,
        payload=body.payload,
        note=body.note,
        current_user=current_user,
    )
