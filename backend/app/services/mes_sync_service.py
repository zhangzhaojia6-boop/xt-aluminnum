from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.adapters import get_mes_adapter
from app.adapters.mes_adapter import CoilSnapshot, MesMachineLineSource
from app.config import settings
from app.models.mes import CoilFlowEvent, MesCoilSnapshot, MesMachineLineSnapshot, MesSyncCursor, MesSyncRunLog


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
    return datetime.now(timezone.utc)


def _to_float(value: Any) -> float | None:
    if value in (None, ''):
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.startswith('/Date(') and text.endswith(')/'):
        milliseconds = _to_int(text[6:-2])
        if milliseconds is None or milliseconds <= 0:
            return None
        try:
            return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _metadata_value(metadata: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata:
            return metadata[key]
    return None


def _mes_product_id(snapshot: CoilSnapshot) -> str | None:
    product = _to_mapping(snapshot.metadata.get('Product'))
    return _to_text(product.get('Id') or snapshot.metadata.get('ProductId') or snapshot.metadata.get('ProductID'))


def _projected_coil_id(snapshot: CoilSnapshot) -> str:
    product_id = _mes_product_id(snapshot)
    if product_id:
        return f'MES:{product_id}'
    material_code = _to_text(snapshot.metadata.get('MaterialCode'))
    batch_no = _to_text(snapshot.batch_no or snapshot.tracking_card_no)
    if material_code and batch_no:
        return f'fallback:{batch_no}:{material_code}'
    return _to_text(snapshot.coil_id) or f'fallback:{batch_no or "unknown"}:{material_code or "unknown"}'


def _projection_fields(snapshot: CoilSnapshot, synced_at: datetime) -> dict[str, Any]:
    metadata = snapshot.metadata
    return {
        'coil_id': _projected_coil_id(snapshot),
        'mes_product_id': _mes_product_id(snapshot),
        'material_code': _to_text(_metadata_value(metadata, 'MaterialCode', 'material_code')),
        'customer_alias': _to_text(_metadata_value(metadata, 'CustomerAlias', 'CustomerSimple', 'CustomerName', 'customer_alias')),
        'alloy_grade': _to_text(_metadata_value(metadata, 'AlloyGrade', 'Alloy', 'alloy_grade')),
        'material_state': _to_text(_metadata_value(metadata, 'MaterialState', 'State', 'StateName', 'material_state')),
        'spec_thickness': _to_float(_metadata_value(metadata, 'SpecThickness', 'Thickness')),
        'spec_width': _to_float(_metadata_value(metadata, 'SpecWidth', 'Width')),
        'spec_length': _to_text(_metadata_value(metadata, 'SpecLength', 'Length')),
        'spec_display': _to_text(_metadata_value(metadata, 'Spec', 'SpecDisplay', 'Specification')),
        'feeding_weight': _to_float(_metadata_value(metadata, 'FeedingWeight')),
        'material_weight': _to_float(_metadata_value(metadata, 'MaterialWeight')),
        'gross_weight': _to_float(_metadata_value(metadata, 'GrossWeight')),
        'net_weight': _to_float(_metadata_value(metadata, 'NetWeight')),
        'current_workshop': _to_text(_metadata_value(metadata, 'CurrentWorkShop', 'current_workshop')),
        'current_process': _to_text(_metadata_value(metadata, 'CurrentProcess', 'current_process')),
        'current_process_sort': _to_int(_metadata_value(metadata, 'CurrentProcessSort', 'current_process_sort')),
        'next_workshop': _to_text(_metadata_value(metadata, 'NextWorkShop', 'next_workshop')),
        'next_process': _to_text(_metadata_value(metadata, 'NextProcess', 'next_process')),
        'next_process_sort': _to_int(_metadata_value(metadata, 'NextProcessSort', 'next_process_sort')),
        'process_route_text': _to_text(_metadata_value(metadata, 'ProcessRoute', 'process_route_text')),
        'print_process_route_text': _to_text(_metadata_value(metadata, 'PrintProcessRoute', 'print_process_route_text')),
        'status_name': _to_text(_metadata_value(metadata, 'StatusName', 'status_name')),
        'card_status_name': _to_text(_metadata_value(metadata, 'CardStatusName', 'card_status_name')),
        'production_status': _to_text(_metadata_value(metadata, 'ProductionStatus', 'production_status')),
        'delay_hours': _to_float(_metadata_value(metadata, 'DelayHour', 'delay_hours')),
        'in_stock_date': _parse_datetime(_metadata_value(metadata, 'InStockDate', 'in_stock_date')),
        'delivery_date': _parse_datetime(_metadata_value(metadata, 'DeliveryDate', 'delivery_date')),
        'allocation_date': _parse_datetime(_metadata_value(metadata, 'AllocationDate', 'allocation_date')),
        'last_seen_from_mes_at': synced_at,
    }


def _projection_update_fields(projection: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in projection.items() if key != 'coil_id'}


def _apply_projection(entity: Any, projection: Mapping[str, Any]) -> None:
    for key, value in _projection_update_fields(projection).items():
        setattr(entity, key, value)


def _record_flow_event(
    db: Session,
    *,
    existing: Any,
    snapshot: CoilSnapshot,
    projection: Mapping[str, Any],
    payload: dict[str, Any],
) -> None:
    previous_process = _to_text(getattr(existing, 'current_process', None) or getattr(existing, 'process_code', None))
    current_process = _to_text(projection.get('current_process') or snapshot.process_code)
    if not current_process or previous_process == current_process:
        return

    db.add(
        CoilFlowEvent(
            coil_key=str(projection['coil_id']),
            tracking_card_no=snapshot.tracking_card_no,
            previous_workshop=_to_text(getattr(existing, 'current_workshop', None) or getattr(existing, 'workshop_code', None)),
            previous_process=previous_process,
            current_workshop=_to_text(projection.get('current_workshop') or snapshot.workshop_code),
            current_process=current_process,
            next_workshop=_to_text(projection.get('next_workshop')),
            next_process=_to_text(projection.get('next_process')),
            event_time=snapshot.updated_at or snapshot.event_time,
            source_payload=payload,
        )
    )


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
    projection = _projection_fields(snapshot, snapshot.updated_at or snapshot.event_time or _utcnow())
    return {
        'coil_id': projection['coil_id'],
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
        'projection': {
            key: (value.isoformat() if isinstance(value, datetime) else value)
            for key, value in projection.items()
        },
        'metadata': snapshot.metadata,
    }


def _window_started_at(now: datetime, *, cursor: MesSyncCursor) -> datetime:
    if cursor.last_event_at is not None:
        return cursor.last_event_at - timedelta(minutes=max(settings.MES_SYNC_WINDOW_MINUTES, 1))
    return now - timedelta(minutes=max(settings.MES_SYNC_WINDOW_MINUTES, 1))


def _upsert_snapshot(db: Session, *, snapshot: CoilSnapshot, synced_at: datetime) -> tuple[bool, bool]:
    projection = _projection_fields(snapshot, synced_at)
    coil_id = projection['coil_id']
    existing = _query_first(db.query(MesCoilSnapshot).filter(MesCoilSnapshot.coil_id == coil_id))
    payload = _serialize_snapshot(snapshot)
    business_date = (snapshot.updated_at or snapshot.event_time).date() if (snapshot.updated_at or snapshot.event_time) else None
    if existing is None:
        db.add(
            MesCoilSnapshot(
                coil_id=coil_id,
                tracking_card_no=snapshot.tracking_card_no,
                qr_code=snapshot.qr_code,
                batch_no=snapshot.batch_no,
                contract_no=snapshot.contract_no,
                **_projection_update_fields(projection),
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

    _record_flow_event(db, existing=existing, snapshot=snapshot, projection=projection, payload=payload)

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
    _apply_projection(existing, projection)
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


def _stats(
    *,
    cursor_key: str,
    fetched_count: int,
    upserted_count: int = 0,
    replayed_count: int = 0,
    synced_at: datetime,
    status: str = 'success',
    error_message: str | None = None,
) -> MesSyncStats:
    return MesSyncStats(
        cursor_key=cursor_key,
        fetched_count=fetched_count,
        upserted_count=upserted_count,
        replayed_count=replayed_count,
        next_cursor=None,
        lag_seconds=None,
        last_event_at=None,
        last_synced_at=synced_at,
        status=status,
        error_message=error_message,
    )


def sync_mes_crafts(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    _ = db
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_crafts()
    return _stats(cursor_key='mes_crafts', fetched_count=len(rows), synced_at=synced_at)


def sync_mes_devices(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    _ = db
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_devices()
    return _stats(cursor_key='mes_devices', fetched_count=len(rows), synced_at=synced_at)


def _sync_coil_list(db: Session, *, cursor_key: str, rows: list[CoilSnapshot], synced_at: datetime) -> MesSyncStats:
    upserted_count = 0
    replayed_count = 0
    for row in rows:
        changed, replayed = _upsert_snapshot(db, snapshot=row, synced_at=synced_at)
        if changed:
            upserted_count += 1
        if replayed:
            replayed_count += 1
    return _stats(
        cursor_key=cursor_key,
        fetched_count=len(rows),
        upserted_count=upserted_count,
        replayed_count=replayed_count,
        synced_at=synced_at,
    )


def sync_mes_follow_cards(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_follow_cards(limit=settings.MES_SYNC_LIMIT)
    return _sync_coil_list(db, cursor_key='mes_follow_cards', rows=rows, synced_at=synced_at)


def sync_mes_dispatch(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_dispatch(limit=settings.MES_SYNC_LIMIT)
    return _sync_coil_list(db, cursor_key='mes_dispatch', rows=rows, synced_at=synced_at)


def sync_mes_wip_total(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    _ = db
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_wip_totals()
    return _stats(cursor_key='mes_wip_total', fetched_count=len(rows), synced_at=synced_at)


def sync_mes_stock(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    _ = db
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_stock(limit=settings.MES_SYNC_LIMIT)
    return _stats(cursor_key='mes_stock', fetched_count=len(rows), synced_at=synced_at)


def sync_mes_machine_lines(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    sources = get_mes_adapter().list_machine_line_sources()
    upserted_count = 0
    for source in sources:
        changed = _upsert_machine_line(db, source=source, synced_at=synced_at)
        if changed:
            upserted_count += 1
    return _stats(
        cursor_key='mes_machine_lines',
        fetched_count=len(sources),
        upserted_count=upserted_count,
        synced_at=synced_at,
    )


def sync_mes_projection(db: Session, *, now: datetime | None = None) -> list[MesSyncStats]:
    synced_at = now or _utcnow()
    return [
        sync_mes_crafts(db, now=synced_at),
        sync_mes_devices(db, now=synced_at),
        sync_mes_follow_cards(db, now=synced_at),
        sync_mes_dispatch(db, now=synced_at),
        sync_mes_wip_total(db, now=synced_at),
        sync_mes_stock(db, now=synced_at),
        sync_mes_machine_lines(db, now=synced_at),
    ]


def _upsert_machine_line(db: Session, *, source: MesMachineLineSource, synced_at: datetime) -> bool:
    slot_no = source.slot_no or _extract_slot_no(source.line_name)
    line_code = _to_text(source.line_code) or _stable_line_code(source.workshop_name, slot_no, source.line_name)
    existing = _query_first(db.query(MesMachineLineSnapshot).filter(MesMachineLineSnapshot.line_code == line_code))
    if existing is None:
        db.add(
            MesMachineLineSnapshot(
                line_code=line_code,
                line_name=source.line_name,
                workshop_name=source.workshop_name,
                slot_no=slot_no,
                last_seen_from_mes_at=synced_at,
                source_payload=source.metadata,
            )
        )
        return True
    existing.line_name = source.line_name
    existing.workshop_name = source.workshop_name
    existing.slot_no = slot_no
    existing.last_seen_from_mes_at = synced_at
    existing.source_payload = source.metadata
    return True


def _extract_slot_no(line_name: str) -> int | None:
    text = line_name.strip()
    if '#' not in text:
        return None
    return _to_int(text.split('#', 1)[0])


def _stable_line_code(workshop_name: str | None, slot_no: int | None, line_name: str) -> str:
    workshop = _to_text(workshop_name) or 'unknown'
    if slot_no is not None:
        return f'{workshop}:{slot_no:02d}'
    return f'{workshop}:{line_name.strip()}'


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
