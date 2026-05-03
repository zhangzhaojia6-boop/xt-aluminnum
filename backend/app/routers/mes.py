from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
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
    scope = build_scope_summary(current_user)
    if not (scope.is_admin or scope.is_manager or scope.is_reviewer):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='MES sync status access denied')
    sync_payload = mes_sync_service.latest_sync_status(db)
    return MesSyncStatusOut(
        cursor_key=sync_payload['cursor_key'],
        last_synced_at=sync_payload.get('last_synced_at'),
        last_event_at=sync_payload.get('last_event_at'),
        lag_seconds=sync_payload.get('lag_seconds'),
        fetched_count=sync_payload.get('fetched_count', 0),
        upserted_count=sync_payload.get('upserted_count', 0),
        replayed_count=sync_payload.get('replayed_count', 0),
        next_cursor=sync_payload.get('cursor_value'),
        status=sync_payload.get('last_run_status', 'idle'),
        error_message=sync_payload.get('error_message') if scope.is_admin else None,
    )
