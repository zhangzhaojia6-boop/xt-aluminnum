from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.imports import ImportBatch
from app.models.system import User
from app.schemas.common import PaginatedResponse
from app.schemas.imports import (
    ImportBatchOut,
    ImportUploadResponse,
)

router = APIRouter(tags=['imports'])


@router.post('/upload', response_model=ImportUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    import_type: str = Form(default='generic'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportUploadResponse:
    _ = file, import_type, db, current_user
    raise HTTPException(status_code=410, detail='文件导入功能已停用，请使用移动端每日填报。')


@router.get('/history', response_model=PaginatedResponse[ImportBatchOut])
def import_history(
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    query = db.query(ImportBatch).order_by(ImportBatch.id.desc())
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {'items': items, 'total': total, 'skip': skip, 'limit': limit}


@router.get('/daily-production/mapping-preview')
def daily_production_mapping_preview(
    batch_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = batch_id, db, current_user
    raise HTTPException(status_code=410, detail='每日产量导入映射预览已停用，请使用移动端每日填报。')


@router.get('/history/{batch_id}', response_model=ImportBatchOut)
def import_detail(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportBatch:
    _ = current_user
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail='import batch not found')
    return batch
