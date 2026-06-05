from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User


router = APIRouter(tags=['templates'])


@router.get('/templates/{workshop_type}', name='template-detail')
def get_template(
    workshop_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = workshop_type, db, current_user
    raise HTTPException(status_code=status.HTTP_410_GONE, detail='模板中心已停用，填报端使用固定模板')
