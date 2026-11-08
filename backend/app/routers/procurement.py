from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user, get_db
from app.domain import procurement_flow as flow
from app.models.procurement import ProcurementDocument, ProcurementRequest
from app.models.system import User
from app.services import procurement_service as service

router = APIRouter(tags=['procurement'])


def require_enabled() -> None:
    if not settings.PROCUREMENT_ENABLED:
        raise HTTPException(status_code=404, detail='采购模块未开启')


class RequestCreate(BaseModel):
    material_name: str
    specification: str | None = None
    unit: str
    category: str
    quantity: Decimal
    estimated_unit_price: Decimal
    needed_by: date | None = None
    purpose: str
    is_emergency: bool = False


class ActionBody(BaseModel):
    action: str
    expected_step: str
    comment: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AssignmentBody(BaseModel):
    user_id: int
    role: str
    enabled: bool = True


def _error(exc: service.ProcurementError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={'detail': exc.message, **exc.extra})


@router.get('/meta', dependencies=[Depends(require_enabled)])
def meta(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    roles = service.user_roles(db, current_user)
    return {
        'roles': sorted(roles),
        'can_view_all': service.can_view_all(current_user, roles),
        'can_manage': current_user.role == 'admin',
        'categories': list(flow.CATEGORIES),
        'assignable_roles': flow.ASSIGNABLE_ROLES,
    }


@router.get('/requests', dependencies=[Depends(require_enabled)])
def list_requests(scope: str = 'todo', db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return service.list_requests(db, user=current_user, scope=scope)
    except service.ProcurementError as exc:
        return _error(exc)


@router.post('/requests', dependencies=[Depends(require_enabled)])
def create_request(body: RequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        request = service.create_request(db, user=current_user, data=body.model_dump())
        roles = service.user_roles(db, current_user)
        result = service.serialize_request(db, request, user=current_user, roles=roles, full=True)
        db.commit()
        return result
    except service.ProcurementError as exc:
        db.rollback()
        return _error(exc)


@router.get('/requests/{request_id}', dependencies=[Depends(require_enabled)])
def get_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    request = db.get(ProcurementRequest, request_id)
    roles = service.user_roles(db, current_user)
    if request is None:
        raise HTTPException(status_code=404, detail='找不到这张申请单')
    if not (service.can_view(current_user, roles, request) or service.can_act(current_user, roles, request)):
        raise HTTPException(status_code=403, detail='没有查看权限')
    return service.serialize_request(db, request, user=current_user, roles=roles, full=True)


@router.post('/requests/{request_id}/actions', dependencies=[Depends(require_enabled)])
def act(request_id: int, body: ActionBody, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        request = service.apply_action(
            db, request_id=request_id, user=current_user, action=body.action,
            expected_step=body.expected_step, comment=body.comment, payload=body.payload,
        )
        result = service.serialize_request(db, request, user=current_user, roles=service.user_roles(db, current_user), full=True)
        db.commit()
        return result
    except service.ProcurementError as exc:
        db.rollback()
        return _error(exc)


@router.post('/requests/{request_id}/documents', dependencies=[Depends(require_enabled)])
async def upload_document(
    request_id: int,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read(service.MAX_UPLOAD_BYTES + 1)
    try:
        document = service.save_document(
            db, request_id=request_id, user=current_user, doc_type=doc_type,
            file_name=file.filename or '', content=content, content_type=file.content_type,
        )
        db.commit()
        return {'id': document.id, 'doc_type': document.doc_type, 'file_name': document.file_name, 'sha256': document.sha256}
    except service.ProcurementError as exc:
        db.rollback()
        return _error(exc)


@router.get('/documents/{document_id}/file', dependencies=[Depends(require_enabled)])
def download_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    document = db.get(ProcurementDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='找不到单据')
    request = db.get(ProcurementRequest, document.request_id)
    roles = service.user_roles(db, current_user)
    if not (service.can_view(current_user, roles, request) or service.can_act(current_user, roles, request)):
        raise HTTPException(status_code=403, detail='没有查看权限')
    return FileResponse(service.document_path(document), media_type=document.content_type, filename=document.file_name)


@router.get('/board', dependencies=[Depends(require_enabled)])
def board(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return service.build_board(db, user=current_user)
    except service.ProcurementError as exc:
        return _error(exc)


def _require_admin(current_user: User) -> None:
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail='只有管理员能分配采购岗位')


@router.get('/assignments', dependencies=[Depends(require_enabled)])
def assignments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    return service.list_assignments(db)


@router.post('/assignments', dependencies=[Depends(require_enabled)])
def update_assignment(body: AssignmentBody, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    try:
        service.set_assignment(db, actor=current_user, user_id=body.user_id, role=body.role, enabled=body.enabled)
        db.commit()
    except service.ProcurementError as exc:
        db.rollback()
        return _error(exc)
    return service.list_assignments(db)
