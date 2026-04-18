from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from sqlalchemy.orm import Session

from app.database import get_sessionmaker
from app.models.production import RealtimeEvent


logger = logging.getLogger(__name__)


def _dispatch_workflow_event(event: dict[str, Any] | None) -> None:
    if not event:
        return
    payload = event.get('payload')
    if not isinstance(payload, dict) or 'workflow_event' not in payload:
        return
    try:
        from app.core.workflow_dispatcher import workflow_dispatcher

        workflow_dispatcher.dispatch_realtime_event(event)
    except Exception:  # noqa: BLE001
        logger.warning('Workflow dispatch failed for %s', event.get('event_type'), exc_info=True)


class InMemoryEventBus:
    def __init__(self, *, max_events: int = 1000):
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._last_id = 0
        self._lock = Lock()
        self._waiters: list[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = []

    def _snapshot(self, *, after_event_id: int, limit: int) -> list[dict[str, Any]]:
        items = [item for item in self._events if item['id'] > after_event_id]
        return items[: max(1, limit)]

    def publish(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._last_id += 1
            event = {
                'id': self._last_id,
                'event_type': event_type,
                'payload': payload,
                'workshop_id': _extract_workshop_id(payload),
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
            self._events.append(event)
            waiters = list(self._waiters)

        for loop, waiter in waiters:
            if loop.is_closed():
                continue
            loop.call_soon_threadsafe(waiter.set)

        _dispatch_workflow_event(event)
        return event

    async def listen(
        self,
        *,
        after_event_id: int = 0,
        limit: int = 50,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        deadline = None if timeout is None else loop.time() + max(timeout, 0)

        while True:
            with self._lock:
                items = self._snapshot(after_event_id=after_event_id, limit=limit)
                if items:
                    return items

                if deadline is not None:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        return []
                else:
                    remaining = None

                waiter = asyncio.Event()
                registration = (loop, waiter)
                self._waiters.append(registration)

            try:
                if remaining is None:
                    await waiter.wait()
                else:
                    await asyncio.wait_for(waiter.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                return []
            finally:
                with self._lock:
                    if registration in self._waiters:
                        self._waiters.remove(registration)


def _extract_workshop_id(payload: dict[str, Any]) -> int | None:
    raw_value = payload.get('workshop_id')
    if raw_value in (None, ''):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _serialize_event(entity: RealtimeEvent) -> dict[str, Any]:
    created_at = entity.created_at
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        'id': int(entity.id),
        'event_type': entity.event_type,
        'payload': dict(entity.payload or {}),
        'workshop_id': entity.workshop_id,
        'created_at': created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
    }


class DatabaseEventBus:
    def __init__(
        self,
        *,
        sessionmaker_factory=get_sessionmaker,
        poll_interval: float = 0.2,
    ):
        self._sessionmaker_factory = sessionmaker_factory
        self._poll_interval = max(0.01, float(poll_interval))

    def _open_session(self) -> Session:
        session_factory = self._sessionmaker_factory()
        return session_factory()

    def _fetch(self, *, after_event_id: int, limit: int) -> list[dict[str, Any]]:
        db = self._open_session()
        try:
            rows = (
                db.query(RealtimeEvent)
                .filter(RealtimeEvent.id > max(0, int(after_event_id)))
                .order_by(RealtimeEvent.id.asc())
                .limit(max(1, int(limit)))
                .all()
            )
            return [_serialize_event(row) for row in rows]
        finally:
            db.close()

    def publish(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        db = self._open_session()
        try:
            entity = RealtimeEvent(
                event_type=event_type,
                payload=payload,
                workshop_id=_extract_workshop_id(payload),
            )
            db.add(entity)
            db.commit()
            db.refresh(entity)
            event = _serialize_event(entity)
            _dispatch_workflow_event(event)
            return event
        except Exception:  # noqa: BLE001
            if hasattr(db, 'rollback'):
                db.rollback()
            logger.warning('Realtime event publish failed for %s', event_type, exc_info=True)
            return None
        finally:
            db.close()

    async def listen(
        self,
        *,
        after_event_id: int = 0,
        limit: int = 50,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        deadline = None if timeout is None else loop.time() + max(timeout, 0)

        while True:
            items = self._fetch(after_event_id=after_event_id, limit=limit)
            if items:
                return items

            if deadline is not None:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return []
                await asyncio.sleep(min(self._poll_interval, remaining))
                continue

            await asyncio.sleep(self._poll_interval)

    def cleanup(self, *, max_age_hours: int = 48, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        cutoff = current - timedelta(hours=max(1, int(max_age_hours)))
        db = self._open_session()
        try:
            deleted = db.query(RealtimeEvent).filter(RealtimeEvent.created_at < cutoff).delete(synchronize_session=False)
            db.commit()
            return int(deleted or 0)
        finally:
            db.close()


event_bus = DatabaseEventBus()


def publish(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return event_bus.publish(event_type, payload)


def cleanup_expired_events() -> int:
    removed = event_bus.cleanup(max_age_hours=48)
    if removed:
        logger.info('Removed %s expired realtime events', removed)
    return removed


def register_jobs(scheduler) -> None:
    if scheduler is None:
        return
    if scheduler.get_job('realtime-events-cleanup') is not None:
        return
    scheduler.add_job(
        cleanup_expired_events,
        'interval',
        hours=1,
        id='realtime-events-cleanup',
        replace_existing=True,
    )
