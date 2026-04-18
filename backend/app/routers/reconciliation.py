from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.schemas.reconciliation import (
    ReconciliationActionRequest,
    ReconciliationGenerateRequest,
    ReconciliationItemOut,
)
from app.services import reconciliation_service

router = APIRouter(tags=['reconciliation'])


@router.post('/generate', response_model=list[ReconciliationItemOut])
def generate_reconciliation(
    body: ReconciliationGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReconciliationItemOut]:
    try:
        items = reconciliation_service.generate_reconciliation(
            db,
            business_date=body.business_date,
            reconciliation_type=body.reconciliation_type,
            operator=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [ReconciliationItemOut.model_validate(item) for item in items]


@router.get('/items', response_model=list[ReconciliationItemOut])
def list_items(
    business_date: date | None = None,
    reconciliation_type: str | None = None,
    status: str | None = None,
    field_name: str | None = None,
    item_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReconciliationItemOut]:
    _ = current_user
    items = reconciliation_service.list_items(
        db,
        business_date=business_date,
        reconciliation_type=reconciliation_type,
        status=status,
        field_name=field_name,
        item_id=item_id,
    )
    return [ReconciliationItemOut.model_validate(item) for item in items]


def _update_item(
    *,
    item_id: int,
    action: str,
    body: ReconciliationActionRequest,
    db: Session,
    current_user: User,
) -> ReconciliationItemOut:
    try:
        entity = reconciliation_service.update_item_status(
            db,
            item_id=item_id,
            action=action,
            operator=current_user,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ReconciliationItemOut.model_validate(entity)


@router.post('/items/{item_id}/confirm', response_model=ReconciliationItemOut)
def confirm_item(
    item_id: int,
    body: ReconciliationActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReconciliationItemOut:
    return _update_item(item_id=item_id, action='confirm', body=body, db=db, current_user=current_user)


@router.post('/items/{item_id}/ignore', response_model=ReconciliationItemOut)
def ignore_item(
    item_id: int,
    body: ReconciliationActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReconciliationItemOut:
    return _update_item(item_id=item_id, action='ignore', body=body, db=db, current_user=current_user)


@router.post('/items/{item_id}/correct', response_model=ReconciliationItemOut)
def correct_item(
    item_id: int,
    body: ReconciliationActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReconciliationItemOut:
    if not body.note:
        raise HTTPException(status_code=400, detail='resolve_note is required')
    return _update_item(item_id=item_id, action='correct', body=body, db=db, current_user=current_user)
