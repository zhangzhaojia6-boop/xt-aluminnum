from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.permissions import get_current_mobile_user, get_current_reviewer_user
from app.models.system import User
from app.schemas.attendance import (
    AttendanceAnomalyOut,
    AttendanceAnomalyReviewRequest,
    AttendanceConfirmationOut,
    AttendanceConfirmationSubmitRequest,
    AttendanceDetailResponse,
    AttendanceExceptionOut,
    AttendanceImportResponse,
    AttendanceProcessRequest,
    AttendanceProcessResponse,
    AttendanceResultListResponse,
    AttendanceResultOut,
    AttendanceResultOverrideRequest,
    AttendanceScheduleOut,
    AttendanceSummaryOut,
    ClockRecordOut,
    ExceptionResolveRequest,
)
from app.schemas.imports import ImportSummary
from app.services import attendance_confirm_service, attendance_service, import_service

router = APIRouter(tags=['attendance'])


@router.post('/schedules/import', response_model=AttendanceImportResponse)
def import_schedules(
    file: UploadFile = File(...),
    template_code: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttendanceImportResponse:
    result = import_service.import_attendance_schedules(db, file, current_user, template_code)
    return AttendanceImportResponse(
        batch_id=result.batch.id,
        batch_no=result.batch.batch_no,
        import_type=result.batch.import_type,
        summary=ImportSummary(**result.summary),
    )


@router.get('/schedules', response_model=list[AttendanceScheduleOut])
def list_schedules(
    start_date: date | None = None,
    end_date: date | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AttendanceScheduleOut]:
    _ = current_user
    payloads = attendance_service.list_schedules(
        db,
        start_date=start_date,
        end_date=end_date,
        employee_id=employee_id,
    )
    return [AttendanceScheduleOut(**item) for item in payloads]


@router.post('/clocks/import', response_model=AttendanceImportResponse)
def import_clocks(
    file: UploadFile = File(...),
    template_code: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttendanceImportResponse:
    result = import_service.import_clock_records(db, file, current_user, template_code)
    return AttendanceImportResponse(
        batch_id=result.batch.id,
        batch_no=result.batch.batch_no,
        import_type=result.batch.import_type,
        summary=ImportSummary(**result.summary),
    )


@router.get('/clocks', response_model=list[ClockRecordOut])
def list_clocks(
    start_date: date | None = None,
    end_date: date | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ClockRecordOut]:
    _ = current_user
    payloads = attendance_service.list_clocks(
        db,
        start_date=start_date,
        end_date=end_date,
        employee_id=employee_id,
    )
    return [ClockRecordOut(**item) for item in payloads]


@router.post('/process', response_model=AttendanceProcessResponse)
def process_attendance(
    body: AttendanceProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttendanceProcessResponse:
    if body.end_date < body.start_date:
        raise HTTPException(status_code=400, detail='end_date must be greater than or equal to start_date')

    summary = attendance_service.process_attendance(
        db,
        start_date=body.start_date,
        end_date=body.end_date,
        operator=current_user,
    )
    return AttendanceProcessResponse(
        processed_dates=summary.processed_dates,
        processed_results=summary.processed_results,
        generated_exceptions=summary.generated_exceptions,
    )


@router.get('/results', response_model=AttendanceResultListResponse)
def list_results(
    business_date: date,
    workshop_id: int | None = None,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttendanceResultListResponse:
    _ = current_user
    payload = attendance_service.list_results(
        db,
        business_date=business_date,
        workshop_id=workshop_id,
        team_id=team_id,
    )
    return AttendanceResultListResponse(
        summary=payload['summary'],
        items=[AttendanceResultOut.model_validate(item) for item in payload['items']],
    )


@router.get('/results/{employee_id}/{business_date}', response_model=AttendanceDetailResponse)
def get_result_detail(
    employee_id: int,
    business_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttendanceDetailResponse:
    _ = current_user
    try:
        result, schedules, clocks, exceptions = attendance_service.get_result_detail(
            db,
            employee_id=employee_id,
            business_date=business_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return AttendanceDetailResponse(
        result=AttendanceResultOut.model_validate(result),
        schedules=[AttendanceScheduleOut(**item) for item in schedules],
        clocks=[ClockRecordOut(**item) for item in clocks],
        exceptions=[AttendanceExceptionOut(**item) for item in exceptions],
    )


@router.get('/exceptions', response_model=list[AttendanceExceptionOut])
def list_exceptions(
    business_date: date,
    exception_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AttendanceExceptionOut]:
    _ = current_user
    payloads = attendance_service.list_exceptions(
        db,
        business_date=business_date,
        exception_type=exception_type,
        status=status,
    )
    return [AttendanceExceptionOut(**item) for item in payloads]


@router.post('/exceptions/{exception_id}/resolve', response_model=AttendanceExceptionOut)
def resolve_exception(
    exception_id: int,
    body: ExceptionResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttendanceExceptionOut:
    try:
        item = attendance_service.resolve_attendance_exception(
            db,
            exception_id=exception_id,
            action=body.action,
            note=body.note,
            operator=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    payloads = attendance_service.list_exceptions(
        db,
        business_date=item.business_date,
        exception_type=item.exception_type,
        status=item.status,
    )
    target = next((entry for entry in payloads if entry['id'] == item.id), None)
    if target is None:
        raise HTTPException(status_code=500, detail='Failed to load resolved exception')
    return AttendanceExceptionOut(**target)


@router.post('/results/{result_id}/override', response_model=AttendanceResultOut)
def override_result(
    result_id: int,
    body: AttendanceResultOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttendanceResultOut:
    try:
        result = attendance_service.override_attendance_result(
            db,
            result_id=result_id,
            payload=body.model_dump(exclude_unset=True),
            operator=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return AttendanceResultOut.model_validate(result)


@router.get('/draft', response_model=AttendanceConfirmationOut, name='attendance-draft')
def attendance_draft(
    machine_id: int,
    shift_id: int,
    business_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> AttendanceConfirmationOut:
    payload = attendance_confirm_service.build_draft(
        db,
        machine_id=machine_id,
        shift_id=shift_id,
        business_date=business_date,
        current_user=current_user,
    )
    return AttendanceConfirmationOut(**payload)


@router.post('/confirm', response_model=AttendanceConfirmationOut, name='attendance-confirm')
def attendance_confirm(
    body: AttendanceConfirmationSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> AttendanceConfirmationOut:
    payload = attendance_confirm_service.submit_confirmation(
        db,
        payload=body.model_dump(),
        current_user=current_user,
    )
    return AttendanceConfirmationOut(**payload)


@router.get('/anomalies', response_model=list[AttendanceAnomalyOut], name='attendance-anomalies')
def attendance_anomalies(
    workshop_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_reviewer_user),
) -> list[AttendanceAnomalyOut]:
    if date_from is None or date_to is None:
        raise HTTPException(status_code=400, detail='date_from and date_to are required')
    payloads = attendance_confirm_service.list_anomalies(
        db,
        workshop_id=workshop_id,
        date_from=date_from,
        date_to=date_to,
        current_user=current_user,
    )
    return [AttendanceAnomalyOut(**item) for item in payloads]


@router.patch('/anomalies/{detail_id}/review', response_model=dict)
def review_attendance_anomaly(
    detail_id: int,
    body: AttendanceAnomalyReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_reviewer_user),
) -> dict:
    return attendance_confirm_service.update_anomaly_review(
        db,
        detail_id=detail_id,
        hr_status=body.hr_status,
        note=body.note,
        current_user=current_user,
    )


@router.get('/summary', response_model=AttendanceSummaryOut, name='attendance-summary')
def attendance_summary(
    business_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttendanceSummaryOut:
    payload = attendance_confirm_service.build_summary(
        db,
        business_date=business_date,
        current_user=current_user,
    )
    return AttendanceSummaryOut(**payload)
