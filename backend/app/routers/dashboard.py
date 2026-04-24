from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.permissions import assert_manager_dashboard_access, get_current_manager_user
from app.core.rate_limit import enforce_request_rate_limit
from app.core.scope import build_scope_summary
from app.schemas.dashboard import DeliveryStatusOut, FactoryDashboardResponse, WorkshopDashboardResponse
from app.models.system import User
from app.services import report_service

router = APIRouter(tags=['dashboard'])


def _ensure_reviewer_or_manager(current_user: User):
    summary = build_scope_summary(current_user)
    if not (summary.is_admin or summary.is_reviewer or summary.is_manager):
        raise HTTPException(status_code=403, detail='Dashboard access denied')
    return summary


def _ensure_global_dashboard_scope(current_user: User):
    summary = _ensure_reviewer_or_manager(current_user)
    if summary.is_admin or summary.is_manager:
        return summary
    if summary.data_scope_type == 'all':
        return summary
    if summary.workshop_id is None and not summary.assigned_shift_ids:
        return summary
    raise HTTPException(status_code=403, detail='Global dashboard requires manager or global review scope')


@router.get('/factory-director', response_model=FactoryDashboardResponse, response_model_exclude_none=True)
def factory_director_dashboard(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    return report_service.build_factory_dashboard(db, target_date=target_date or date.today())


@router.get('/workshop-director', response_model=WorkshopDashboardResponse, response_model_exclude_none=True)
def workshop_director_dashboard(
    request: Request,
    target_date: date | None = None,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    selected_workshop_id = workshop_id or current_user.workshop_id
    summary = assert_manager_dashboard_access(current_user, workshop_id=selected_workshop_id)
    if not summary.is_admin and summary.data_scope_type != 'all':
        if summary.workshop_id is not None and selected_workshop_id != summary.workshop_id:
            raise HTTPException(status_code=403, detail='Dashboard scope denied')
        selected_workshop_id = summary.workshop_id if summary.workshop_id is not None else selected_workshop_id
    return report_service.build_workshop_dashboard(
        db,
        target_date=target_date or date.today(),
        workshop_id=selected_workshop_id,
    )


@router.get('/statistics')
def statistics_dashboard(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return report_service.build_statistics_dashboard(db, target_date=target_date or date.today())


@router.get('/delivery-status', response_model=DeliveryStatusOut, response_model_exclude_none=True)
def delivery_status(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    _ensure_global_dashboard_scope(current_user)
    return report_service.build_delivery_status(db, target_date=target_date or date.today())


@router.get('/factory', response_model=FactoryDashboardResponse, response_model_exclude_none=True)
def factory_dashboard_alias(
    request: Request,
    target_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    return report_service.build_factory_dashboard(db, target_date=target_date or date.today())


@router.get('/workshop', response_model=WorkshopDashboardResponse, response_model_exclude_none=True)
def workshop_dashboard_alias(
    request: Request,
    target_date: date | None = None,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='dashboard', limit=30, window_seconds=60)
    selected_workshop_id = workshop_id or current_user.workshop_id
    summary = assert_manager_dashboard_access(current_user, workshop_id=selected_workshop_id)
    if not summary.is_admin and summary.data_scope_type != 'all':
        if summary.workshop_id is not None and selected_workshop_id != summary.workshop_id:
            raise HTTPException(status_code=403, detail='Dashboard scope denied')
        selected_workshop_id = summary.workshop_id if summary.workshop_id is not None else selected_workshop_id
    return report_service.build_workshop_dashboard(
        db,
        target_date=target_date or date.today(),
        workshop_id=selected_workshop_id,
    )
