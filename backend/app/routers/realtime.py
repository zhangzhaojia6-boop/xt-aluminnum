from __future__ import annotations

import asyncio
import json
import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import decode_token
from app.core.deps import get_db
from app.core.event_bus import event_bus
from app.core.rate_limit import acquire_connection_rate_limit, enforce_request_rate_limit
from app.core.scope import build_scope_summary, can_view_all_work_order_entries, resolve_work_order_entry_workshop_scope
from app.models.system import User
from app.schemas.realtime import (
    LiveActiveBusinessDateOut,
    LiveAggregationOut,
    LiveCellDetailOut,
    LiveFillDetailOut,
    LiveMesFillGapOut,
    LiveMissingOutputWeightResolveOut,
    LiveMissingOutputWeightResolveRequest,
    LivePendingAssignmentOut,
)
from app.services import mes_fill_gap_service, missing_report_export_service, realtime_service
from app.services import pass_count_service


router = APIRouter(tags=['realtime'])
security = HTTPBearer(auto_error=False)


def get_realtime_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    raw_token = credentials.credentials if credentials else None
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid authentication credentials')
    try:
        payload = decode_token(raw_token)
        user_id = int(payload.get('sub'))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid authentication credentials') from exc
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid authentication credentials')
    return user


def _resolve_stream_scope(*, scope: str, current_user: User) -> int | None:
    summary = build_scope_summary(current_user)
    if scope == 'all':
        if not can_view_all_work_order_entries(summary):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Realtime scope denied')
        return None
    try:
        requested_scope = int(scope)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='scope must be workshop id or all') from exc

    scoped_workshop_id = resolve_work_order_entry_workshop_scope(summary)
    if scoped_workshop_id is not None and requested_scope != scoped_workshop_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Realtime scope denied')
    return requested_scope


def _event_matches_scope(event: dict, *, workshop_scope: int | None) -> bool:
    if workshop_scope is None:
        return True
    workshop_id = event.get('workshop_id')
    if workshop_id is None:
        workshop_id = event.get('payload', {}).get('workshop_id')
    return int(workshop_id or 0) == workshop_scope


def _resolve_live_manage_workshop_scope(*, current_user: User, workshop_id: int | None) -> int | None:
    summary = build_scope_summary(current_user)
    if not (summary.is_admin or summary.is_reviewer or summary.is_manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Realtime scope denied')
    scoped_workshop_id = resolve_work_order_entry_workshop_scope(summary)
    if scoped_workshop_id is not None:
        return scoped_workshop_id
    if workshop_id is None:
        return _resolve_stream_scope(scope='all', current_user=current_user)
    return _resolve_stream_scope(scope=str(workshop_id), current_user=current_user)


def _format_sse_event(event: dict) -> str:
    return (
        f"id: {event['id']}\n"
        f"event: {event['event_type']}\n"
        f"data: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"
    )


def _monotonic() -> float:
    return time.monotonic()


async def _event_stream(request: Request, *, workshop_scope: int | None, cursor: int, permit=None):
    heartbeat_interval = 15.0
    yield 'retry: 1000\n\n'

    try:
        while True:
            if await request.is_disconnected():
                break

            events = await event_bus.listen(after_event_id=cursor, limit=50, timeout=0)
            if not events:
                break

            cursor = events[-1]['id']
            for event in events:
                if _event_matches_scope(event, workshop_scope=workshop_scope):
                    yield _format_sse_event(event)

        next_heartbeat_at = _monotonic() + heartbeat_interval
        while True:
            if await request.is_disconnected():
                break

            timeout = max(0.0, next_heartbeat_at - _monotonic())
            events = await event_bus.listen(after_event_id=cursor, limit=50, timeout=timeout)

            if events:
                cursor = events[-1]['id']
                for event in events:
                    if _event_matches_scope(event, workshop_scope=workshop_scope):
                        yield _format_sse_event(event)
                next_heartbeat_at = _monotonic() + heartbeat_interval
                continue

            now = _monotonic()
            if now >= next_heartbeat_at:
                yield ': heartbeat\n\n'
                next_heartbeat_at = now + heartbeat_interval

            await asyncio.sleep(0)
    finally:
        if permit is not None:
            permit.release()


@router.get('/realtime/stream', name='realtime-stream')
def stream_realtime(
    request: Request,
    scope: str = 'all',
    last_event_id: int | None = Query(default=None),
    current_user: User = Depends(get_realtime_user),
):
    workshop_scope = _resolve_stream_scope(scope=scope, current_user=current_user)
    permit = acquire_connection_rate_limit(request, current_user, scope='realtime_stream', limit=6)
    try:
        cursor = int(last_event_id if last_event_id is not None else request.headers.get('last-event-id', '0') or 0)
    except ValueError:
        cursor = 0

    return StreamingResponse(
        _event_stream(request, workshop_scope=workshop_scope, cursor=cursor, permit=permit),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


@router.get('/aggregation/live', response_model=LiveAggregationOut, name='live-aggregation')
def live_aggregation(
    request: Request,
    business_date: date,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> LiveAggregationOut:
    enforce_request_rate_limit(request, current_user, scope='aggregation_live', limit=60, window_seconds=60)
    payload = realtime_service.build_live_aggregation(
        db,
        business_date=business_date,
        workshop_id=workshop_id,
        current_user=current_user,
    )
    return LiveAggregationOut(**payload)


@router.get('/aggregation/live/active-date', response_model=LiveActiveBusinessDateOut, name='live-active-business-date')
def live_active_business_date(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> LiveActiveBusinessDateOut:
    summary = build_scope_summary(current_user)
    workshop_scope = resolve_work_order_entry_workshop_scope(summary)
    payload = realtime_service.resolve_live_business_date(db, workshop_id=workshop_scope)
    return LiveActiveBusinessDateOut(**payload)


@router.patch(
    '/aggregation/live/missing-output/{entry_id}',
    response_model=LiveMissingOutputWeightResolveOut,
    name='live-missing-output-resolve',
)
def resolve_live_missing_output_weight(
    entry_id: int,
    body: LiveMissingOutputWeightResolveRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> LiveMissingOutputWeightResolveOut:
    enforce_request_rate_limit(
        request,
        current_user,
        scope='aggregation_missing_output_resolve',
        limit=30,
        window_seconds=60,
    )
    payload = realtime_service.resolve_missing_output_weight(
        db,
        entry_id=entry_id,
        output_weight=body.output_weight,
        reason=body.reason,
        current_user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
    )
    return LiveMissingOutputWeightResolveOut(**payload)


@router.get('/aggregation/live/detail', response_model=LiveCellDetailOut, name='live-aggregation-detail')
def live_aggregation_detail(
    business_date: date,
    workshop_id: int,
    machine_id: int,
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> LiveCellDetailOut:
    payload = realtime_service.build_live_cell_detail(
        db,
        business_date=business_date,
        workshop_id=workshop_id,
        machine_id=machine_id,
        shift_id=shift_id,
        current_user=current_user,
    )
    return LiveCellDetailOut(**payload)


@router.get('/aggregation/live/fill-details', response_model=LiveFillDetailOut, name='live-fill-details')
def live_fill_details(
    request: Request,
    business_date: date,
    workshop_id: int | None = None,
    search: str | None = None,
    limit: int = 800,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> LiveFillDetailOut:
    enforce_request_rate_limit(request, current_user, scope='aggregation_fill_details', limit=60, window_seconds=60)
    payload = realtime_service.build_fill_detail_ledger(
        db,
        business_date=business_date,
        workshop_id=workshop_id,
        search=search,
        limit=limit,
        current_user=current_user,
    )
    return LiveFillDetailOut(**payload)


@router.get('/aggregation/live/pending-assignment', response_model=LivePendingAssignmentOut, name='live-pending-assignment')
def live_pending_assignment(
    request: Request,
    business_date: date,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> LivePendingAssignmentOut:
    enforce_request_rate_limit(request, current_user, scope='aggregation_pending_assignment', limit=60, window_seconds=60)
    payload = realtime_service.build_pending_assignment_detail(
        db,
        business_date=business_date,
        workshop_id=workshop_id,
        current_user=current_user,
    )
    return LivePendingAssignmentOut(**payload)


@router.get('/aggregation/live/mes-fill-gaps', response_model=LiveMesFillGapOut, name='live-mes-fill-gaps')
def live_mes_fill_gaps(
    request: Request,
    business_date: date,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> LiveMesFillGapOut:
    enforce_request_rate_limit(request, current_user, scope='aggregation_mes_fill_gaps', limit=60, window_seconds=60)
    resolved_workshop_id = _resolve_live_manage_workshop_scope(current_user=current_user, workshop_id=workshop_id)
    payload = mes_fill_gap_service.build_mes_fill_gaps(
        db,
        business_date=business_date,
        workshop_id=resolved_workshop_id,
    )
    return LiveMesFillGapOut(**payload)


@router.get('/aggregation/live/missing-report-export', name='live-missing-report-export')
def live_missing_report_export(
    request: Request,
    business_date: date,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> Response:
    enforce_request_rate_limit(request, current_user, scope='aggregation_missing_report_export', limit=20, window_seconds=60)
    resolved_workshop_id = _resolve_live_manage_workshop_scope(current_user=current_user, workshop_id=workshop_id)
    payload = realtime_service.build_pending_assignment_detail(
        db,
        business_date=business_date,
        workshop_id=resolved_workshop_id,
        current_user=current_user,
    )
    payload = dict(payload)
    payload['mes_fill_gaps'] = mes_fill_gap_service.build_mes_fill_gaps(
        db,
        business_date=business_date,
        workshop_id=resolved_workshop_id,
    )
    content = missing_report_export_service.build_missing_report_workbook(payload)
    filename = f'missing-report-{business_date.isoformat()}.xlsx'
    return Response(
        content=content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@router.get('/aggregation/pass-count/shift', name='pass-count-by-shift')
def pass_count_by_shift(
    request: Request,
    business_date: date,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='aggregation_pass_count', limit=60, window_seconds=60)
    summary = build_scope_summary(current_user)
    scoped = resolve_work_order_entry_workshop_scope(summary)
    if scoped is not None:
        workshop_id = scoped
    return pass_count_service.build_shift_pass_count(
        db,
        business_date=business_date,
        workshop_id=workshop_id,
    )


@router.get('/aggregation/pass-count/month', name='pass-count-by-month')
def pass_count_by_month(
    request: Request,
    year: int,
    month: int,
    workshop_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_realtime_user),
) -> dict:
    enforce_request_rate_limit(request, current_user, scope='aggregation_pass_count_month', limit=30, window_seconds=60)
    summary = build_scope_summary(current_user)
    scoped = resolve_work_order_entry_workshop_scope(summary)
    if scoped is not None:
        workshop_id = scoped
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail='month must be 1..12')
    return pass_count_service.build_monthly_pass_count(
        db,
        year=year,
        month=month,
        workshop_id=workshop_id,
    )
