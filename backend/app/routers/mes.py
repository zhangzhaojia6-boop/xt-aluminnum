from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.scope import ScopeSummary, build_scope_summary
from app.models.system import User
from app.schemas.mes import MesImportResponse
from app.schemas.mes_extended import (
    MesExtendedSummaryOut,
    MesMaterialRecordOut,
    MesReferenceItemOut,
    MesStockRecordOut,
    MesWipTotalSnapshotOut,
    MesWorkshopProcessRecordOut,
    MesYieldRecordOut,
)
from app.schemas.mes_sync import MesSyncRunsOut, MesSyncStatusOut
from app.services import mes_extended_service, mes_sync_service

router = APIRouter(tags=['mes'])


def _ensure_mes_access(user: User) -> ScopeSummary:
    scope = build_scope_summary(user)
    if not (scope.is_admin or scope.is_manager or scope.is_reviewer):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='MES data access denied')
    return scope


def _resolve_mes_workshop_names(db: Session, scope: ScopeSummary, workshop_id: int | None) -> set[str] | None:
    if workshop_id is None:
        return mes_extended_service.resolve_scope_workshop_names(db, scope)
    if scope.is_admin or scope.data_scope_type == 'all':
        names = mes_extended_service.resolve_workshop_id_names(db, workshop_id)
        if not names:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='车间不存在')
        return names
    if scope.workshop_id is not None and int(scope.workshop_id) == int(workshop_id):
        names = mes_extended_service.resolve_scope_workshop_names(db, scope)
        if not names:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='车间不存在')
        return names
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='MES workshop scope denied')


@router.post('/import', response_model=MesImportResponse)
def import_mes_export(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MesImportResponse:
    _ = file, db, current_user
    raise HTTPException(status_code=410, detail='MES 导入功能已停用，请使用移动端每日填报。')


@router.get('/sync-status', response_model=MesSyncStatusOut)
def sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MesSyncStatusOut:
    scope = _ensure_mes_access(current_user)
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
        configured=bool(sync_payload.get('configured')),
        migration_ready=bool(sync_payload.get('migration_ready', True)),
        source=sync_payload.get('source') or 'local_entry',
        status=sync_payload.get('status') or sync_payload.get('last_run_status', 'idle'),
        last_run_status=sync_payload.get('last_run_status') or 'idle',
        action_required=sync_payload.get('action_required') or 'none',
        required_env=list(sync_payload.get('required_env') or []),
        error_message=sync_payload.get('error_message') if scope.is_admin else None,
    )


@router.get('/sync-runs', response_model=MesSyncRunsOut)
def sync_runs(
    limit: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MesSyncRunsOut:
    scope = _ensure_mes_access(current_user)
    payload = mes_sync_service.recent_sync_runs(db, limit=limit)
    items = [
        {**item, 'error_message': item.get('error_message') if scope.is_admin else None}
        for item in payload.get('items', [])
    ]
    return MesSyncRunsOut(
        cursor_key=payload.get('cursor_key') or 'coil_snapshots',
        limit=payload.get('limit') or limit,
        summary=payload.get('summary') or {},
        items=items,
    )


@router.get('/extended/summary', response_model=MesExtendedSummaryOut)
def extended_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MesExtendedSummaryOut:
    scope = _ensure_mes_access(current_user)
    return mes_extended_service.build_summary(
        db,
        workshop_names=mes_extended_service.resolve_scope_workshop_names(db, scope),
    )


@router.get('/extended/workshop-process-records', response_model=list[MesWorkshopProcessRecordOut])
def workshop_process_records(
    business_date: date | None = None,
    workshop_id: int | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MesWorkshopProcessRecordOut]:
    scope = _ensure_mes_access(current_user)
    return mes_extended_service.list_workshop_process_records(
        db,
        business_date=business_date,
        search=search,
        limit=limit,
        offset=offset,
        workshop_names=_resolve_mes_workshop_names(db, scope, workshop_id),
    )


@router.get('/extended/stock-records', response_model=list[MesStockRecordOut])
def stock_records(
    business_date: date | None = None,
    workshop_id: int | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MesStockRecordOut]:
    scope = _ensure_mes_access(current_user)
    return mes_extended_service.list_stock_records(
        db,
        business_date=business_date,
        search=search,
        limit=limit,
        offset=offset,
        workshop_names=_resolve_mes_workshop_names(db, scope, workshop_id),
    )


@router.get('/extended/material-records', response_model=list[MesMaterialRecordOut])
def material_records(
    business_date: date | None = None,
    workshop_id: int | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MesMaterialRecordOut]:
    scope = _ensure_mes_access(current_user)
    return mes_extended_service.list_material_records(
        db,
        business_date=business_date,
        search=search,
        limit=limit,
        offset=offset,
        workshop_names=_resolve_mes_workshop_names(db, scope, workshop_id),
    )


@router.get('/extended/yield-records', response_model=list[MesYieldRecordOut])
def yield_records(
    business_date: date | None = None,
    workshop_id: int | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MesYieldRecordOut]:
    scope = _ensure_mes_access(current_user)
    return mes_extended_service.list_yield_records(
        db,
        business_date=business_date,
        search=search,
        limit=limit,
        offset=offset,
        workshop_names=_resolve_mes_workshop_names(db, scope, workshop_id),
    )


@router.get('/extended/wip-total-snapshots', response_model=list[MesWipTotalSnapshotOut])
def wip_total_snapshots(
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MesWipTotalSnapshotOut]:
    scope = _ensure_mes_access(current_user)
    return mes_extended_service.list_wip_total_snapshots(
        db,
        search=search,
        limit=limit,
        offset=offset,
        workshop_names=mes_extended_service.resolve_scope_workshop_names(db, scope),
    )


@router.get('/extended/reference-items', response_model=list[MesReferenceItemOut])
def reference_items(
    source_type: str | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MesReferenceItemOut]:
    scope = _ensure_mes_access(current_user)
    return mes_extended_service.list_reference_items(
        db,
        source_type=source_type,
        search=search,
        limit=limit,
        offset=offset,
        workshop_names=mes_extended_service.resolve_scope_workshop_names(db, scope),
    )
