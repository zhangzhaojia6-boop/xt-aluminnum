from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.schemas.mes import MesImportResponse, MesImportSummary
from app.services import mes_service

router = APIRouter(tags=['mes'])


@router.post('/import', response_model=MesImportResponse)
def import_mes_export(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MesImportResponse:
    result = mes_service.import_mes_export(db, upload_file=file, current_user=current_user)
    return MesImportResponse(
        batch_id=result.batch_id,
        batch_no=result.batch_no,
        import_type=result.import_type,
        summary=MesImportSummary(**result.summary),
    )
