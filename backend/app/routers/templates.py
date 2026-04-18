from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.workshop_templates import get_workshop_template
from app.models.system import User
from app.schemas.templates import WorkshopTemplateOut


router = APIRouter(tags=['templates'])


@router.get('/templates/{workshop_type}', response_model=WorkshopTemplateOut, name='template-detail')
def get_template(
    workshop_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkshopTemplateOut:
    payload = get_workshop_template(workshop_type, user_role=current_user.role, db=db)
    return WorkshopTemplateOut(**payload)
