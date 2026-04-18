from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.adapters import get_mes_adapter
from app.adapters.mes_adapter import CoilSnapshot
from app.config import settings
from app.models.mes import MesCoilSnapshot, MesSyncCursor, MesSyncRunLog


SYNC_CURSOR_KEY = 'coil_snapshots'


@dataclass(slots=True)
class MesSyncStats:
    cursor_key: str
    fetched_count: int
    upserted_count: int
    replayed_count: int
    next_cursor: str | None
    lag_seconds: float | None
    last_event_at: datetime | None
    last_synced_at: datetime | None
    status: str
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'cursor_key': self.cursor_key,
            'fetched_count': self.fetched_count,
            'upserted_count': self.upserted_count,
            'replayed_count': self.replayed_count,
            'next_cursor': self.next_cursor,
            'lag_seconds': self.lag_seconds,
            'last_event_at': self.last_event_at.isoformat() if self.last_event_at else None,
            'last_synced_at': self.last_synced_at.isoformat() if self.last_synced_at else None,
            'status': self.status,
            'error_message': self.error_message,
        }


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _query_first(query):
    if hasattr(query, 'first'):
        return query.first()
    if hasattr(query, 'all'):
        rows = query.all()
        return rows[0] if rows else None
    return None


def _ensure_cursor(db: Session, *, cursor_key: str) -> MesSyncCursor:
    entity = _query_first(db.query(MesSyncCursor).filter(MesSyncCursor.cursor_key == cursor_key))
    if entity is not None:
        return entity
    entity = MesSyncCursor(cursor_key=cursor_key)
    db.add(entity)
    db.flush()
    return entity


def _serialize_snapshot(snapshot: CoilSnapshot) -> dict[str, Any]:
    business_date = (snapshot.updated_at or snapshot.event_time).date().isoformat() if (snapshot.updated_at or snapshot.event_time) else None
    return {
        'coil_id': snapshot.coil_id,
        'tracking_card_no': snapshot.tracking_card_no,
        'qr_code': snapshot.qr_code,
        'batch_no': snapshot.batch_no,
        'contract_no': snapshot.contract_no,
        'workshop_code': snapshot.workshop_code,
        'process_code': snapshot.process_code,
        'machine_code': snapshot.machine_code,
        'shift_code': snapshot.shift_code,
        'status': snapshot.status,
        'business_date': business_date,
        'event_time': snapshot.event_time.isoformat() if snapshot.event_time else None,
        'updated_at': snapshot.updated_at.isoformat() if snapshot.updated_at else None,
        'metadata': snapshot.metadata,
    }


def _window_started_at(now: datetime, *, cursor: MesSyncCursor) -> datetime:
    if cursor.last_event_at is not None:
        return cursor.last_event_at - timedelta(minutes=max(settings.MES_SYNC_WINDOW_MINUTES, 1))
    return now - timedelta(minutes=max(settings.MES_SYNC_WINDOW_MINUTES, 1))


def _upsert_snapshot(db: Session, *, snapshot: CoilSnapshot, synced_at: datetime) -> tuple[bool, bool]:
    existing = _query_first(db.query(MesCoilSnapshot).filter(MesCoilSnapshot.coil_id == snapshot.coil_id))
    payload = _serialize_snapshot(snapshot)
    business_date = (snapshot.updated_at or snapshot.event_time).date() if (snapshot.updated_at or snapshot.event_time) else None
    if existing is None:
        db.add(
            MesCoilSnapshot(
                coil_id=snapshot.coil_id,
                tracking_card_no=snapshot.tracking_card_no,
                qr_code=snapshot.qr_code,
                batch_no=snapshot.batch_no,
                contract_no=snapshot.contract_no,
                workshop_code=snapshot.workshop_code,
                process_code=snapshot.process_code,
                machine_code=snapshot.machine_code,
                shift_code=snapshot.shift_code,
                status=snapshot.status,
                business_date=business_date,
                event_time=snapshot.event_time,
                updated_from_mes_at=snapshot.updated_at or snapshot.event_time,
                last_synced_at=synced_at,
                source_payload=payload,
            )
        )
        return True, False

    incoming_updated_at = snapshot.updated_at or snapshot.event_time
    if (
        existing.updated_from_mes_at is not None
        and incoming_updated_at is not None
        and incoming_updated_at < existing.updated_from_mes_at
    ):
        existing.last_synced_at = synced_at
        return False, True

    existing.tracking_card_no = snapshot.tracking_card_no
    existing.qr_code = snapshot.qr_code
    existing.batch_no = snapshot.batch_no
    existing.contract_no = snapshot.contract_no
    existing.workshop_code = snapshot.workshop_code
    existing.process_code = snapshot.process_code
    existing.machine_code = snapshot.machine_code
    existing.shift_code = snapshot.shift_code
    existing.status = snapshot.status
    existing.business_date = business_date
    existing.event_time = snapshot.event_time
    existing.updated_from_mes_at = incoming_updated_at
    existing.last_synced_at = synced_at
    existing.source_payload = payload
    return True, False


def sync_coil_snapshots(
    db: Session,
    *,
    cursor_key: str = SYNC_CURSOR_KEY,
    now: datetime | None = None,
) -> MesSyncStats:
    synced_at = now or _utcnow()
    cursor = _ensure_cursor(db, cursor_key=cursor_key)
    window_started_at = _window_started_at(synced_at, cursor=cursor)
    run_log = MesSyncRunLog(
        cursor_key=cursor_key,
        started_at=synced_at,
        status='running',
        metadata_json={
            'window_started_at': window_started_at.isoformat(),
            'cursor_value': cursor.cursor_value,
            'limit': settings.MES_SYNC_LIMIT,
        },
    )
    db.add(run_log)
    db.flush()

    adapter = get_mes_adapter()
    try:
        snapshots, next_cursor = adapter.list_coil_snapshots(
            cursor=cursor.cursor_value,
            updated_after=window_started_at,
            limit=settings.MES_SYNC_LIMIT,
        )
        upserted_count = 0
        replayed_count = 0
        last_event_at = cursor.last_event_at
        for item in snapshots:
            changed, replayed = _upsert_snapshot(db, snapshot=item, synced_at=synced_at)
            if changed:
                upserted_count += 1
            if replayed:
                replayed_count += 1
            event_at = item.updated_at or item.event_time
            if event_at and (last_event_at is None or event_at > last_event_at):
                last_event_at = event_at

        cursor.cursor_value = next_cursor
        cursor.window_started_at = window_started_at
        cursor.last_event_at = last_event_at
        cursor.last_synced_at = synced_at

        lag_seconds = None
        if last_event_at is not None:
            lag_seconds = max((synced_at - last_event_at).total_seconds(), 0.0)

        run_log.finished_at = _utcnow()
        run_log.status = 'success'
        run_log.fetched_count = len(snapshots)
        run_log.upserted_count = upserted_count
        run_log.replayed_count = replayed_count
        run_log.next_cursor = next_cursor
        run_log.lag_seconds = lag_seconds
        return MesSyncStats(
            cursor_key=cursor_key,
            fetched_count=len(snapshots),
            upserted_count=upserted_count,
            replayed_count=replayed_count,
            next_cursor=next_cursor,
            lag_seconds=lag_seconds,
            last_event_at=last_event_at,
            last_synced_at=synced_at,
            status='success',
        )
    except Exception as exc:  # noqa: BLE001
        run_log.finished_at = _utcnow()
        run_log.status = 'failed'
        run_log.error_message = str(exc)
        raise


def compute_sync_lag_seconds(db: Session, *, cursor_key: str = SYNC_CURSOR_KEY, now: datetime | None = None) -> float | None:
    current = now or _utcnow()
    cursor = _query_first(db.query(MesSyncCursor).filter(MesSyncCursor.cursor_key == cursor_key))
    if cursor is None or cursor.last_event_at is None:
        latest = _query_first(
            db.query(MesCoilSnapshot).order_by(MesCoilSnapshot.updated_from_mes_at.desc().nullslast(), MesCoilSnapshot.id.desc())
        )
        if latest is None or latest.updated_from_mes_at is None:
            return None
        return max((current - latest.updated_from_mes_at).total_seconds(), 0.0)
    return max((current - cursor.last_event_at).total_seconds(), 0.0)


def latest_sync_status(db: Session, *, cursor_key: str = SYNC_CURSOR_KEY, now: datetime | None = None) -> dict[str, Any]:
    current = now or _utcnow()
    cursor = _query_first(db.query(MesSyncCursor).filter(MesSyncCursor.cursor_key == cursor_key))
    latest_run = _query_first(
        db.query(MesSyncRunLog)
        .filter(MesSyncRunLog.cursor_key == cursor_key)
        .order_by(MesSyncRunLog.started_at.desc(), MesSyncRunLog.id.desc())
    )
    return {
        'cursor_key': cursor_key,
        'cursor_value': cursor.cursor_value if cursor else None,
        'last_event_at': cursor.last_event_at.isoformat() if cursor and cursor.last_event_at else None,
        'last_synced_at': cursor.last_synced_at.isoformat() if cursor and cursor.last_synced_at else None,
        'lag_seconds': compute_sync_lag_seconds(db, cursor_key=cursor_key, now=current),
        'last_run_status': latest_run.status if latest_run else 'idle',
        'last_run_started_at': latest_run.started_at.isoformat() if latest_run else None,
        'last_run_finished_at': latest_run.finished_at.isoformat() if latest_run and latest_run.finished_at else None,
        'fetched_count': latest_run.fetched_count if latest_run else 0,
        'upserted_count': latest_run.upserted_count if latest_run else 0,
        'replayed_count': latest_run.replayed_count if latest_run else 0,
        'error_message': latest_run.error_message if latest_run else None,
    }
