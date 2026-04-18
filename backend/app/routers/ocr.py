from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.permissions import get_current_mobile_user
from app.core.rate_limit import enforce_request_rate_limit
from app.models.system import User
from app.schemas.ocr import OCRExtractOut, OCRVerifyOut, OCRVerifyRequest
from app.services import ocr_service


router = APIRouter(tags=['ocr'])


@router.post('/ocr/extract', response_model=OCRExtractOut, name='ocr-extract')
async def extract_ocr_fields(
    request: Request,
    workshop_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> OCRExtractOut:
    enforce_request_rate_limit(request, current_user, scope='ocr_extract', limit=10, window_seconds=60)
    file_bytes = await file.read()
    payload = ocr_service.extract_submission(
        db,
        file_name=file.filename or 'ocr.jpg',
        file_bytes=file_bytes,
        workshop_type=workshop_type,
        current_user=current_user,
    )
    return OCRExtractOut(**payload)


@router.post('/ocr/verify', response_model=OCRVerifyOut, name='ocr-verify')
def verify_ocr_fields(
    body: OCRVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_mobile_user),
) -> OCRVerifyOut:
    payload = ocr_service.verify_submission(
        db,
        submission_id=body.ocr_submission_id,
        corrected_fields=body.corrected_fields,
        rejected=body.rejected,
        current_user=current_user,
    )
    return OCRVerifyOut(**payload)
