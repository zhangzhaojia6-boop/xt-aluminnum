from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.imports import ImportBatch, ImportRow
from app.models.system import User
from app.schemas.common import PaginatedResponse
from app.schemas.imports import ImportBatchOut, ImportRowOut, ImportSummary, ImportUploadResponse
from app.services import import_service

router = APIRouter(tags=['imports'])


@router.post('/upload', response_model=ImportUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    import_type: str = Form(default='generic'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportUploadResponse:
    result = import_service.store_import_file(upload_file=file, db=db, current_user=current_user, import_type=import_type)

    rows = (
        db.query(ImportRow)
        .filter(ImportRow.batch_id == result.batch.id)
        .order_by(ImportRow.row_number.asc())
        .limit(100)
        .all()
    )

    return ImportUploadResponse(
        batch=ImportBatchOut.model_validate(result.batch),
        rows=[ImportRowOut.model_validate(item) for item in rows],
        summary=ImportSummary(**result.summary),
    )


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
