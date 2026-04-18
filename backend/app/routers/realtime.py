from __future__ import annotations

import asyncio
import json
import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import decode_token
from app.core.deps import get_db
from app.core.event_bus import event_bus
from app.core.rate_limit import acquire_connection_rate_limit, enforce_request_rate_limit
from app.core.scope import build_scope_summary, can_view_all_work_order_entries, resolve_work_order_entry_workshop_scope
from app.models.system import User
from app.schemas.realtime import LiveAggregationOut, LiveCellDetailOut
from app.services import realtime_service


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
    permit = acquire_connection_rate_limit(request, current_user, scope='realtime_stream', limit=2)
    try:
        cursor = int(last_event_id if last_event_id is not None else request.headers.get('last-event-id', '0') or 0)
    except ValueError:
        cursor = 0

    return StreamingResponse(
        _event_stream(request, workshop_scope=workshop_scope, cursor=cursor, permit=permit),
        media_type='text/event-stream',
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
