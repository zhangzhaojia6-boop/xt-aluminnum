from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.schemas.mes import MesImportResponse, MesImportSummary
from app.schemas.mes_sync import MesSyncStatusOut
from app.services import mes_service
from app.services import mes_sync_service

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


@router.get('/sync-status', response_model=MesSyncStatusOut)
def sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MesSyncStatusOut:
    _ = current_user
    status = mes_sync_service.latest_sync_status(db)
    return MesSyncStatusOut(
        cursor_key=status['cursor_key'],
        last_synced_at=status.get('last_synced_at'),
        last_event_at=status.get('last_event_at'),
        lag_seconds=status.get('lag_seconds'),
        fetched_count=status.get('fetched_count', 0),
        upserted_count=status.get('upserted_count', 0),
        replayed_count=status.get('replayed_count', 0),
        next_cursor=status.get('cursor_value'),
        status=status.get('last_run_status', 'idle'),
        error_message=status.get('error_message'),
    )
