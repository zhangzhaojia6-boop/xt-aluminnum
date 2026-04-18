from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.permissions import assert_review_access, get_current_reviewer_user
from app.core.scope import build_scope_summary
from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.schemas.imports import ImportSummary
from app.schemas.production import (
    ProductionExceptionOut,
    ShiftDataActionRequest,
    ShiftDataActionResponse,
    ProductionImportResponse,
    ShiftProductionDataDetailResponse,
    ShiftProductionDataOut,
)
from app.services import production_service

router = APIRouter(tags=['production'])


def _effective_review_scope(current_user: User, *, workshop_id: int | None, team_id: int | None) -> tuple[int | None, int | None]:
    summary = build_scope_summary(current_user)
    if summary.is_admin or summary.data_scope_type == 'all':
        return workshop_id, team_id

    effective_workshop_id = workshop_id or summary.workshop_id
    effective_team_id = team_id
    if summary.data_scope_type == 'self_team':
        effective_team_id = team_id or summary.team_id
    elif summary.data_scope_type == 'self_workshop':
        effective_team_id = team_id
    elif summary.data_scope_type == 'assigned':
        effective_team_id = team_id if team_id is not None else summary.team_id

    assert_review_access(
        current_user,
        workshop_id=effective_workshop_id,
        team_id=effective_team_id,
    )
    return effective_workshop_id, effective_team_id


@router.post('/import', response_model=ProductionImportResponse)
def import_production_file(
    file: UploadFile = File(...),
    template_code: str | None = Form(default=None),
    duplicate_strategy: str = Form(default='reject'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionImportResponse:
    result = production_service.import_shift_production_data(
        db,
        upload_file=file,
        current_user=current_user,
        template_code=template_code,
        duplicate_strategy=duplicate_strategy,
    )
    return ProductionImportResponse(
        batch_id=result.batch_id,
        batch_no=result.batch_no,
        import_type=result.import_type,
        summary=ImportSummary(**result.summary),
    )


@router.get('/shift-data', response_model=list[ShiftProductionDataOut])
def list_shift_data(
    start_date: date | None = None,
    end_date: date | None = None,
    workshop_id: int | None = None,
    team_id: int | None = None,
    data_status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_reviewer_user),
) -> list[ShiftProductionDataOut]:
    effective_workshop_id, effective_team_id = _effective_review_scope(
        current_user,
        workshop_id=workshop_id,
        team_id=team_id,
    )
    payloads = production_service.list_shift_data(
        db,
        start_date=start_date,
        end_date=end_date,
        workshop_id=effective_workshop_id,
        team_id=effective_team_id,
        data_status=data_status,
    )
    return [ShiftProductionDataOut(**item) for item in payloads]


@router.get('/shift-data/{shift_data_id}', response_model=ShiftProductionDataDetailResponse)
def shift_data_detail(
    shift_data_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_reviewer_user),
) -> ShiftProductionDataDetailResponse:
    entity = production_service.ensure_shift_data_exists(db, shift_data_id=shift_data_id)
    assert_review_access(
        current_user,
        workshop_id=entity.workshop_id,
        team_id=entity.team_id,
        shift_id=entity.shift_config_id,
    )
    try:
        item, exceptions, trails = production_service.get_shift_data_detail(db, shift_data_id=shift_data_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ShiftProductionDataDetailResponse(
        item=ShiftProductionDataOut(**item),
        exceptions=[ProductionExceptionOut(**entry) for entry in exceptions],
        audit_trails=trails,
    )


@router.get('/exceptions', response_model=list[ProductionExceptionOut])
def list_production_exceptions(
    business_date: date | None = None,
    exception_type: str | None = None,
    status: str | None = None,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_reviewer_user),
) -> list[ProductionExceptionOut]:
    summary = build_scope_summary(current_user)
    effective_workshop_id, effective_team_id = _effective_review_scope(
        current_user,
        workshop_id=workshop_id,
        team_id=current_user.team_id if summary.data_scope_type == 'self_team' else None,
    )
    payloads = production_service.list_production_exceptions(
        db,
        business_date=business_date,
        exception_type=exception_type,
        status=status,
        workshop_id=effective_workshop_id,
        team_id=effective_team_id,
    )
    return [ProductionExceptionOut(**item) for item in payloads]


def _build_action_response(db: Session, *, shift_data_id: int, message: str) -> ShiftDataActionResponse:
    item, _, _ = production_service.get_shift_data_detail(db, shift_data_id=shift_data_id)
    return ShiftDataActionResponse(
        message=message,
        item=ShiftProductionDataOut(**item),
    )


@router.post('/shift-data/{shift_data_id}/review', response_model=ShiftDataActionResponse)
def review_shift_data(
    shift_data_id: int,
    body: ShiftDataActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_reviewer_user),
) -> ShiftDataActionResponse:
    production_service.update_shift_data_status(
        db,
        shift_data_id=shift_data_id,
        action='review',
        reason=body.reason,
        operator=current_user,
    )
    return _build_action_response(db, shift_data_id=shift_data_id, message='reviewed')


@router.post('/shift-data/{shift_data_id}/confirm', response_model=ShiftDataActionResponse)
def confirm_shift_data(
    shift_data_id: int,
    body: ShiftDataActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_reviewer_user),
) -> ShiftDataActionResponse:
    production_service.update_shift_data_status(
        db,
        shift_data_id=shift_data_id,
        action='confirm',
        reason=body.reason,
        operator=current_user,
    )
    return _build_action_response(db, shift_data_id=shift_data_id, message='confirmed')


@router.post('/shift-data/{shift_data_id}/reject', response_model=ShiftDataActionResponse)
def reject_shift_data(
    shift_data_id: int,
    body: ShiftDataActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_reviewer_user),
) -> ShiftDataActionResponse:
    production_service.update_shift_data_status(
        db,
        shift_data_id=shift_data_id,
        action='reject',
        reason=body.reason,
        operator=current_user,
    )
    return _build_action_response(db, shift_data_id=shift_data_id, message='rejected')


@router.post('/shift-data/{shift_data_id}/void', response_model=ShiftDataActionResponse)
def void_shift_data(
    shift_data_id: int,
    body: ShiftDataActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_reviewer_user),
) -> ShiftDataActionResponse:
    production_service.update_shift_data_status(
        db,
        shift_data_id=shift_data_id,
        action='void',
        reason=body.reason,
        operator=current_user,
    )
    return _build_action_response(db, shift_data_id=shift_data_id, message='voided')
