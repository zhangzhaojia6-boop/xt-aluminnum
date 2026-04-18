from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.schemas.work_orders import (
    FieldAmendmentCreate,
    FieldAmendmentOut,
    WorkOrderCreate,
    WorkOrderDetailOut,
    WorkOrderEntryCreate,
    WorkOrderEntryOut,
    WorkOrderEntrySubmitRequest,
    WorkOrderEntryUpdate,
    WorkOrderListItemOut,
    WorkOrderUpdate,
)
from app.services import work_order_service


router = APIRouter(tags=['work_orders'])


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _normalize_idempotency_key(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(str(value).strip()))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='X-Idempotency-Key must be a UUID') from exc


@router.post('/work-orders/', response_model=WorkOrderDetailOut, name='work-orders-create')
def create_work_order(
    body: WorkOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkOrderDetailOut:
    payload = work_order_service.create_work_order(
        db,
        payload=body.model_dump(exclude_none=True),
        operator=current_user,
        ip_address=_request_ip(request),
        user_agent=request.headers.get('user-agent'),
    )
    return WorkOrderDetailOut(**payload)


@router.get('/work-orders/{tracking_card_no}', response_model=WorkOrderDetailOut, name='work-order-detail')
def get_work_order(
    tracking_card_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkOrderDetailOut:
    payload = work_order_service.get_work_order_by_tracking_card(
        db,
        tracking_card_no=tracking_card_no,
        current_user=current_user,
    )
    return WorkOrderDetailOut(**payload)


@router.patch('/work-orders/{work_order_id}', response_model=WorkOrderDetailOut, name='work-order-update')
def update_work_order(
    work_order_id: int,
    body: WorkOrderUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkOrderDetailOut:
    payload = work_order_service.update_work_order(
        db,
        work_order_id=work_order_id,
        payload=body.model_dump(exclude_unset=True),
        operator=current_user,
        ip_address=_request_ip(request),
        user_agent=request.headers.get('user-agent'),
    )
    return WorkOrderDetailOut(**payload)


@router.get('/work-orders/', response_model=list[WorkOrderListItemOut], name='work-orders-list')
def list_work_orders(
    workshop_id: int | None = None,
    business_date: date | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkOrderListItemOut]:
    rows = work_order_service.list_work_orders(
        db,
        current_user=current_user,
        workshop_id=workshop_id,
        business_date=business_date,
        status=status,
    )
    return [WorkOrderListItemOut(**item) for item in rows]


@router.post('/work-orders/{work_order_id}/entries', response_model=WorkOrderEntryOut, name='work-order-entry-create')
def create_work_order_entry(
    work_order_id: int,
    body: WorkOrderEntryCreate,
    request: Request,
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkOrderEntryOut:
    payload = work_order_service.add_entry(
        db,
        work_order_id=work_order_id,
        payload=body.model_dump(exclude_none=True),
        operator=current_user,
        idempotency_key=_normalize_idempotency_key(x_idempotency_key),
        ip_address=_request_ip(request),
        user_agent=request.headers.get('user-agent'),
    )
    return WorkOrderEntryOut(**payload)


@router.patch('/work-orders/entries/{entry_id}', response_model=WorkOrderEntryOut, name='work-order-entry-update')
def update_work_order_entry(
    entry_id: int,
    body: WorkOrderEntryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkOrderEntryOut:
    payload = work_order_service.update_entry(
        db,
        entry_id=entry_id,
        payload=body.model_dump(exclude_unset=True),
        operator=current_user,
        override_reason=body.override_reason,
        ip_address=_request_ip(request),
        user_agent=request.headers.get('user-agent'),
    )
    return WorkOrderEntryOut(**payload)


@router.post('/work-orders/entries/{entry_id}/submit', response_model=WorkOrderEntryOut, name='work-order-entry-submit')
def submit_work_order_entry(
    entry_id: int,
    request: Request,
    body: WorkOrderEntrySubmitRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkOrderEntryOut:
    payload = work_order_service.submit_entry(
        db,
        entry_id=entry_id,
        operator=current_user,
        override_reason=body.override_reason if body else None,
        ip_address=_request_ip(request),
        user_agent=request.headers.get('user-agent'),
    )
    return WorkOrderEntryOut(**payload)


@router.post('/amendments/', response_model=FieldAmendmentOut, name='field-amendment-create')
def create_field_amendment(
    body: FieldAmendmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldAmendmentOut:
    payload = work_order_service.request_amendment(
        db,
        payload=body.model_dump(exclude_none=True),
        operator=current_user,
    )
    return FieldAmendmentOut(**payload)


@router.patch('/amendments/{amendment_id}/approve', response_model=FieldAmendmentOut, name='field-amendment-approve')
def approve_field_amendment(
    amendment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FieldAmendmentOut:
    payload = work_order_service.approve_amendment(db, amendment_id=amendment_id, operator=current_user)
    return FieldAmendmentOut(**payload)
