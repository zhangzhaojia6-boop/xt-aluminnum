from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.permissions import get_current_mobile_user
from app.core.workshop_templates import DEFAULT_WORKSHOP_TEMPLATES, WORKSHOP_TYPE_BY_WORKSHOP_CODE, resolve_workshop_type
from app.models.master import Workshop
from app.models.system import User
from app.schemas.mobile import (
    MobileBootstrapOut,
    MobileCoilEntryOut,
    MobileCoilEntryPayload,
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


@router.get('/coil-list/{business_date}/{shift_id}', response_model=list[MobileCoilEntryOut], name='mobile-coil-list')
def coil_list(
    business_date: date,
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> list[MobileCoilEntryOut]:
    entries = mobile_report_service.list_coil_entries(
        db,
        business_date=business_date,
        shift_id=shift_id,
        current_user=current_user,
    )
    return [MobileCoilEntryOut(**e) for e in entries]


@router.post('/coil-entry', response_model=MobileCoilEntryOut, name='mobile-coil-entry')
def create_coil_entry(
    body: MobileCoilEntryPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> MobileCoilEntryOut:
    entry = mobile_report_service.create_coil_entry(
        db,
        payload=body.model_dump(),
        current_user=current_user,
        ip_address=_request_ip(request),
    )
    return MobileCoilEntryOut(**entry)


ROLE_FIELD_MAPPING = {
    'machine_operator': {'sections': ['entry', 'shift'], 'label': '产量数据'},
    'energy_stat': {'extra_filter': 'energy_stat', 'label': '能耗数据'},
    'maintenance_lead': {'extra_filter': 'maintenance_lead', 'label': '设备维护'},
    'hydraulic_lead': {'extra_filter': 'hydraulic_lead', 'label': '液压耗材'},
    'consumable_stat': {'extra_filter': 'consumable_stat', 'label': '耗材统计'},
    'qc': {'sections': ['qc'], 'label': '质检数据'},
    'weigher': {'sections': ['entry'], 'label': '称重数据'},
    'shift_leader': {'sections': ['entry', 'shift', 'extra', 'qc'], 'label': '班次汇总'},
    'contracts': {'extra_filter': 'contracts', 'label': '合同与投料'},
    'inventory_keeper': {'sections': ['entry'], 'label': '库存数据'},
    'utility_manager': {'extra_filter': 'utility_manager', 'label': '水电气'},
}


def _filter_fields_by_role(fields: list[dict], role: str) -> list[dict]:
    result = []
    for f in fields:
        role_write = f.get('role_write', [])
        if not role_write or role in role_write or role in ('admin', 'shift_leader'):
            result.append(f)
    return result


@router.get('/entry-fields', name='mobile-entry-fields')
def entry_fields(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> dict:
    workshop = db.get(Workshop, current_user.workshop_id) if current_user.workshop_id else None
    if workshop is None:
        return {'groups': [], 'mode': 'unknown', 'error': '未绑定车间'}

    ws_code = workshop.code.upper()
    ws_type = WORKSHOP_TYPE_BY_WORKSHOP_CODE.get(ws_code)
    if not ws_type:
        try:
            ws_type = resolve_workshop_type(
                workshop_type=getattr(workshop, 'workshop_type', None),
                workshop_code=ws_code,
                workshop_name=workshop.name,
            )
        except Exception:
            ws_type = 'casting'

    template = DEFAULT_WORKSHOP_TEMPLATES.get(ws_type, {})
    role = current_user.role or ''
    mapping = ROLE_FIELD_MAPPING.get(role, ROLE_FIELD_MAPPING.get('shift_leader', {}))

    groups = []
    is_per_coil = role == 'machine_operator'

    if 'extra_filter' in mapping:
        target_role = mapping['extra_filter']
        fields = []
        for f in template.get('extra_fields', []):
            rw = f.get('role_write', [])
            if target_role in rw:
                fields.append(f)
        for f in template.get('qc_fields', []):
            rw = f.get('role_write', [])
            if target_role in rw:
                fields.append(f)
        if fields:
            groups.append({'label': mapping.get('label', '填报'), 'fields': fields})
    else:
        sections = mapping.get('sections', ['entry'])
        if 'entry' in sections:
            ef = _filter_fields_by_role(template.get('entry_fields', []), role)
            if ef:
                groups.append({'label': '产量数据' if is_per_coil else '基础数据', 'fields': ef})
        if 'shift' in sections:
            sf = _filter_fields_by_role(template.get('shift_fields', []), role)
            if sf:
                groups.append({'label': '班次数据', 'fields': sf})
        if 'extra' in sections:
            xf = _filter_fields_by_role(template.get('extra_fields', []), role)
            if xf:
                groups.append({'label': '补充数据', 'fields': xf})
        if 'qc' in sections:
            qf = _filter_fields_by_role(template.get('qc_fields', []), role)
            if qf:
                groups.append({'label': '质检', 'fields': qf})

    readonly = template.get('readonly_fields', [])
    readonly_filtered = _filter_fields_by_role(readonly, role)

    return {
        'groups': groups,
        'readonly_fields': readonly_filtered,
        'mode': 'per_coil' if is_per_coil else 'per_shift',
        'workshop_type': ws_type,
        'role': role,
        'role_label': mapping.get('label', '填报'),
    }
