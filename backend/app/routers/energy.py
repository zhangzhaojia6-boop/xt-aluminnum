from datetime import date

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.schemas.energy import EnergyImportResponse, EnergyImportSummary, EnergySummaryOut
from app.services import energy_service

router = APIRouter(tags=['energy'])


@router.post('/import', response_model=EnergyImportResponse)
def import_energy(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnergyImportResponse:
    result = energy_service.import_energy_data(db, upload_file=file, current_user=current_user)
    return EnergyImportResponse(
        batch_id=result.batch_id,
        batch_no=result.batch_no,
        import_type=result.import_type,
        summary=EnergyImportSummary(**result.summary),
    )


@router.get('/summary', response_model=list[EnergySummaryOut])
def list_energy_summary(
    business_date: date | None = None,
    workshop_id: int | None = None,
    shift_config_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EnergySummaryOut]:
    _ = current_user
    rows = energy_service.get_energy_summary(
        db,
        business_date=business_date,
        workshop_id=workshop_id,
        shift_config_id=shift_config_id,
    )
    return [EnergySummaryOut(**row) for row in rows]
