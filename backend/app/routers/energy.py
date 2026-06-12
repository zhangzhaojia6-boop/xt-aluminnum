from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
from app.models.system import User
from app.schemas.energy import EnergyImportResponse, EnergySummaryOut
from app.services import energy_service

router = APIRouter(tags=['energy'])


def _effective_energy_workshop_id(
    current_user: User,
    *,
    workshop_id: int | None,
    shift_config_id: int | None,
) -> int | None:
    summary = build_scope_summary(current_user)
    if not (summary.is_admin or summary.is_manager or summary.is_reviewer):
        raise HTTPException(status_code=403, detail='Permission denied')
    if summary.is_admin or summary.data_scope_type == 'all':
        return workshop_id

    effective_workshop_id = workshop_id or summary.workshop_id
    if summary.data_scope_type == 'assigned':
        if not summary.assigned_shift_ids or shift_config_id is None:
            raise HTTPException(status_code=403, detail='Review scope denied')
        if int(shift_config_id) not in summary.assigned_shift_ids:
            raise HTTPException(status_code=403, detail='Review scope denied')
        if effective_workshop_id is None:
            raise HTTPException(status_code=403, detail='Review scope denied')
        if summary.workshop_id is not None and int(effective_workshop_id) != int(summary.workshop_id):
            raise HTTPException(status_code=403, detail='Review scope denied')
        return effective_workshop_id

    if summary.data_scope_type == 'self_team':
        raise HTTPException(status_code=403, detail='Review scope denied')

    if summary.data_scope_type == 'self_workshop':
        if summary.workshop_id is None or effective_workshop_id is None:
            raise HTTPException(status_code=403, detail='Review scope denied')
        if int(effective_workshop_id) != int(summary.workshop_id):
            raise HTTPException(status_code=403, detail='Review scope denied')
        return effective_workshop_id

    raise HTTPException(status_code=403, detail='Review scope denied')


@router.post('/import', response_model=EnergyImportResponse)
def import_energy(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnergyImportResponse:
    _ = file, db, current_user
    raise HTTPException(status_code=410, detail='能耗导入功能已停用，请使用电工/内勤每日填报。')


@router.get('/summary', response_model=list[EnergySummaryOut], response_model_exclude_none=True)
def list_energy_summary(
    business_date: date | None = None,
    workshop_id: int | None = None,
    shift_config_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EnergySummaryOut]:
    effective_workshop_id = _effective_energy_workshop_id(
        current_user,
        workshop_id=workshop_id,
        shift_config_id=shift_config_id,
    )
    rows = energy_service.get_energy_summary(
        db,
        business_date=business_date,
        workshop_id=effective_workshop_id,
        shift_config_id=shift_config_id,
    )
    return [EnergySummaryOut(**row) for row in rows]
