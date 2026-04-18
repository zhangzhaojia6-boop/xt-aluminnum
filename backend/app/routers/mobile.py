from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.permissions import get_current_mobile_user
from app.models.system import User
from app.schemas.mobile import (
    MobileBootstrapOut,
    MobileCurrentShiftOut,
    MobilePhotoUploadResponse,
    MobileReminderActionRequest,
    MobileReminderRecordOut,
    MobileReportHistoryResponse,
    MobileReportPayload,
    MobileShiftReportHistoryItemOut,
    MobileShiftReportOut,
)
from app.services import mobile_reminder_service, mobile_report_service

router = APIRouter(tags=['mobile'])


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get('/bootstrap', response_model=MobileBootstrapOut, name='mobile-bootstrap')
def mobile_bootstrap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> MobileBootstrapOut:
    payload = mobile_report_service.get_mobile_bootstrap(db, current_user=current_user)
    return MobileBootstrapOut(**payload)


@router.get('/current-shift', response_model=MobileCurrentShiftOut, name='mobile-current-shift')
def current_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> MobileCurrentShiftOut:
    payload = mobile_report_service.get_current_shift(db, current_user=current_user)
    return MobileCurrentShiftOut(**payload)


@router.get('/report/{business_date}/{shift_id}', response_model=MobileShiftReportOut, name='mobile-report-detail')
def report_detail(
    business_date: date,
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> MobileShiftReportOut:
    payload = mobile_report_service.get_report_detail(
        db,
        business_date=business_date,
        shift_id=shift_id,
        current_user=current_user,
    )
    return MobileShiftReportOut(**payload)


@router.post('/report/save', response_model=MobileShiftReportOut, name='mobile-report-save')
def save_report(
    body: MobileReportPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> MobileShiftReportOut:
    payload = mobile_report_service.save_or_submit_report(
        db,
        payload=body.model_dump(),
        current_user=current_user,
        submit=False,
        ip_address=_request_ip(request),
        user_agent=request.headers.get('user-agent'),
    )
    return MobileShiftReportOut(**payload)


@router.post('/report/submit', response_model=MobileShiftReportOut, name='mobile-report-submit')
def submit_report(
    body: MobileReportPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> MobileShiftReportOut:
    payload = mobile_report_service.save_or_submit_report(
        db,
        payload=body.model_dump(),
        current_user=current_user,
        submit=True,
        ip_address=_request_ip(request),
        user_agent=request.headers.get('user-agent'),
    )
    return MobileShiftReportOut(**payload)


@router.get('/report/history', response_model=MobileReportHistoryResponse, name='mobile-report-history')
def report_history(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> MobileReportHistoryResponse:
    payload = mobile_report_service.list_report_history(
        db,
        current_user=current_user,
        limit=limit,
    )
    return MobileReportHistoryResponse(
        items=[MobileShiftReportHistoryItemOut(**item) for item in payload['items']],
        total=payload['total'],
    )


@router.post('/report/upload-photo', response_model=MobilePhotoUploadResponse, name='mobile-report-upload-photo')
async def upload_photo(
    request: Request,
    business_date: date = Form(...),
    shift_id: int = Form(...),
    override_reason: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> MobilePhotoUploadResponse:
    file_bytes = await file.read()
    payload = mobile_report_service.upload_report_photo(
        db,
        business_date=business_date,
        shift_id=shift_id,
        file_name=file.filename or 'photo.jpg',
        file_bytes=file_bytes,
        current_user=current_user,
        override_reason=override_reason,
        ip_address=_request_ip(request),
        user_agent=request.headers.get('user-agent'),
    )
    return MobilePhotoUploadResponse(**payload)


@router.post('/reminders/run', response_model=list[MobileReminderRecordOut], name='mobile-reminders-run')
def run_reminders(
    target_date: date | None = None,
    grace_minutes: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MobileReminderRecordOut]:
    rows = mobile_reminder_service.run_reminders(
        db,
        current_user=current_user,
        target_date=target_date,
        grace_minutes=grace_minutes,
    )
    return [MobileReminderRecordOut(**item) for item in rows]


@router.get('/reminders', response_model=list[MobileReminderRecordOut], name='mobile-reminders-list')
def list_reminders(
    target_date: date | None = None,
    reminder_status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MobileReminderRecordOut]:
    rows = mobile_reminder_service.list_reminders(
        db,
        current_user=current_user,
        business_date=target_date,
        reminder_status=reminder_status,
    )
    return [MobileReminderRecordOut(**item) for item in rows]


@router.post('/reminders/{reminder_id}/ack', response_model=MobileReminderRecordOut, name='mobile-reminder-ack')
def ack_reminder(
    reminder_id: int,
    body: MobileReminderActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MobileReminderRecordOut:
    payload = mobile_reminder_service.ack_reminder(
        db,
        reminder_id=reminder_id,
        current_user=current_user,
        note=body.note,
    )
    return MobileReminderRecordOut(**payload)


@router.post('/reminders/{reminder_id}/close', response_model=MobileReminderRecordOut, name='mobile-reminder-close')
def close_reminder(
    reminder_id: int,
    body: MobileReminderActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MobileReminderRecordOut:
    payload = mobile_reminder_service.close_reminder(
        db,
        reminder_id=reminder_id,
        current_user=current_user,
        note=body.note,
    )
    return MobileReminderRecordOut(**payload)
