from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import time
from typing import Any, Mapping

from sqlalchemy import and_, func, or_, text
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.adapters import get_mes_adapter
from app.adapters.mes_adapter import CoilSnapshot, MesMachineLineSource, MesSourceRecord, MesWipTotal
from app.config import settings
from app.core.business_time import resolve_production_business_date
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.models.mes import (
    CoilFlowEvent,
    MesCoilSnapshot,
    MesDailyWipSnapshot,
    MesMachineLineSnapshot,
    MesMaterialRecord,
    MesReferenceItem,
    MesStockRecord,
    MesSyncCursor,
    MesSyncRunLog,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
    MesYieldRecord,
)


SYNC_CURSOR_KEY = 'coil_snapshots'
SQLSERVER_MES_REQUIRED_ENV = [
    'MES_ADAPTER',
    'MES_SQLSERVER_HOST',
    'MES_SQLSERVER_PORT',
    'MES_SQLSERVER_DATABASE',
    'MES_SQLSERVER_USERNAME',
    'MES_SQLSERVER_PASSWORD',
]
MVC_MES_REQUIRED_ENV = ['MES_ADAPTER', 'MES_MVC_BASE_URL', 'MES_MVC_USERNAME', 'MES_MVC_PASSWORD']
REST_API_MES_REQUIRED_ENV = ['MES_ADAPTER', 'MES_API_BASE', 'MES_API_TRACKING_CARD_INFO_PATH', 'MES_API_COIL_SNAPSHOTS_PATH']
XINTAI_MES_REQUIRED_ENV = ['MES_ADAPTER', 'MES_API_BASE', 'MES_API_KEY']
DEFAULT_MES_REQUIRED_ENV = SQLSERVER_MES_REQUIRED_ENV


class MesSyncVendorError(RuntimeError):
    """External MES fetch failed after retries; keep the failed run visible."""


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


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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


def _to_source_identifier(value: Any) -> str | None:
    text = _to_text(value)
    if text is None:
        return None
    normalized = text.lower()
    if normalized in {'0', '00000000-0000-0000-0000-000000000000'}:
        return None
    return text


def _to_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_payload(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return filter_sensitive_mapping(metadata)


def required_env_for_adapter(adapter_name: str | None = None) -> list[str]:
    normalized = (adapter_name if adapter_name is not None else settings.MES_ADAPTER or 'null').strip().lower()
    if normalized == 'mvc':
        return list(MVC_MES_REQUIRED_ENV)
    if normalized == 'rest_api':
        return list(REST_API_MES_REQUIRED_ENV)
    if normalized in {'xintai', 'xintai_api'}:
        return list(XINTAI_MES_REQUIRED_ENV)
    return list(SQLSERVER_MES_REQUIRED_ENV)


def _kg_to_tons(value: Any) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    return round(number / 1000, 6)


def _wip_workshop_label():
    return func.coalesce(
        func.nullif(MesCoilSnapshot.current_workshop, ''),
        func.nullif(MesCoilSnapshot.workshop_code, ''),
        func.nullif(MesCoilSnapshot.next_process, ''),
    )


def _wip_process_label():
    return func.coalesce(
        func.nullif(MesCoilSnapshot.current_process, ''),
        func.nullif(MesCoilSnapshot.next_process, ''),
        '',
    )


def _wip_filter_for_business_date(business_date):
    def present(column):
        return and_(column.isnot(None), column != '')

    not_finished_stock = and_(
        MesCoilSnapshot.in_stock_date.is_(None),
        or_(MesCoilSnapshot.status_name.is_(None), MesCoilSnapshot.status_name != '已入库'),
    )
    return (
        MesCoilSnapshot.business_date == business_date,
        MesCoilSnapshot.delivery_date.is_(None),
        MesCoilSnapshot.allocation_date.is_(None),
        not_finished_stock,
        or_(present(MesCoilSnapshot.current_process), present(MesCoilSnapshot.next_process)),
    )


def refresh_daily_wip_snapshots_from_coils(db: Session, *, business_date, snapshot_at: datetime | None = None) -> int:
    db.flush()
    workshop_label = _wip_workshop_label()
    process_label = _wip_process_label()
    rows = (
        db.query(
            workshop_label,
            process_label,
            func.count(MesCoilSnapshot.id),
            func.sum(MesCoilSnapshot.material_weight),
            func.sum(MesCoilSnapshot.feeding_weight),
        )
        .filter(*_wip_filter_for_business_date(business_date))
        .group_by(workshop_label, process_label)
        .all()
    )
    db.query(MesDailyWipSnapshot).filter(
        MesDailyWipSnapshot.business_date == business_date,
        MesDailyWipSnapshot.source == 'mes_coil_snapshot',
    ).delete(synchronize_session=False)

    snapshot_time = snapshot_at or _utcnow()
    for workshop, process, count, material_weight, feeding_weight in rows:
        if not workshop:
            continue
        db.add(
            MesDailyWipSnapshot(
                business_date=business_date,
                workshop_name=str(workshop),
                process_name=str(process or ''),
                coil_count=int(count or 0),
                material_weight_tons=_kg_to_tons(material_weight),
                feeding_weight_tons=_to_float(feeding_weight),
                snapshot_at=snapshot_time,
                source='mes_coil_snapshot',
                source_payload={'basis': 'mes_coil_snapshots', 'business_date': business_date.isoformat()},
            )
        )
    return sum(1 for workshop, *_rest in rows if workshop)


def _refresh_affected_daily_wip_snapshots(db: Session, *, business_dates: set[Any], snapshot_at: datetime) -> None:
    if not business_dates or not hasattr(db, 'get_bind'):
        return
    for item in sorted(business_dates):
        refresh_daily_wip_snapshots_from_coils(db, business_date=item, snapshot_at=snapshot_at)


def _record_event_time(record: MesSourceRecord, *keys: str) -> datetime | None:
    if record.event_time is not None:
        return record.event_time
    for key in keys:
        parsed = _parse_datetime(record.metadata.get(key))
        if parsed is not None:
            return parsed
    return None


def _record_business_date(record: MesSourceRecord, *keys: str) -> Any:
    event_time = _record_event_time(record, *keys)
    return resolve_production_business_date(event_time) if event_time is not None else None


def _snapshot_business_event_time(snapshot: CoilSnapshot) -> datetime | None:
    return snapshot.event_time or snapshot.updated_at


def _snapshot_business_date(snapshot: CoilSnapshot) -> Any:
    event_time = _snapshot_business_event_time(snapshot)
    return resolve_production_business_date(event_time) if event_time is not None else None


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


def _source_id(record: MesSourceRecord, *keys: str) -> str:
    source_id = _to_source_identifier(record.source_id)
    if source_id:
        return source_id
    for key in keys:
        text_value = _to_source_identifier(record.metadata.get(key))
        if text_value:
            return text_value
    payload = json.dumps(dict(record.metadata or {}), ensure_ascii=False, sort_keys=True, default=str)
    return f'fallback:{hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]}'


def _mes_product_id(snapshot: CoilSnapshot) -> str | None:
    product = _to_mapping(snapshot.metadata.get('Product'))
    return _to_text(
        product.get('Id')
        or snapshot.metadata.get('ProductId')
        or snapshot.metadata.get('ProductID')
        or snapshot.metadata.get('Id')
        or snapshot.metadata.get('ID')
    )


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


def _dedupe_snapshots_by_projected_id(rows: list[CoilSnapshot]) -> list[CoilSnapshot]:
    deduped: dict[str, CoilSnapshot] = {}
    for row in rows:
        deduped[_projected_coil_id(row)] = row
    return list(deduped.values())


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


def _dialect_name(db: Session) -> str:
    try:
        bind = db.get_bind()
    except Exception:  # noqa: BLE001
        return ''
    return str(getattr(getattr(bind, 'dialect', None), 'name', '') or '')


def _lock_snapshot_key(db: Session, *, coil_id: str) -> None:
    if _dialect_name(db) != 'postgresql':
        return
    db.execute(
        text('SELECT pg_advisory_xact_lock(hashtext(:lock_key))'),
        {'lock_key': f'mes_coil_snapshot:{coil_id}'},
    )


def _duration_seconds(started_at: datetime | None, finished_at: datetime | None) -> float | None:
    start = _as_utc(started_at)
    finish = _as_utc(finished_at)
    if start is None or finish is None:
        return None
    return round(max((finish - start).total_seconds(), 0.0), 3)


def _adapter_configured() -> bool:
    return (settings.MES_ADAPTER or 'null').strip().lower() != 'null'


def _current_adapter_name() -> str:
    return (settings.MES_ADAPTER or 'null').strip().lower()


def stale_threshold_seconds() -> float:
    return float(max(settings.MES_SYNC_POLL_MINUTES, 1) * 300)


def _retry_limit() -> int:
    return max(int(settings.MES_SYNC_RETRY_LIMIT or 0), 0)


def _retry_backoff_seconds(attempt_index: int) -> float:
    return max(float(settings.MES_SYNC_BACKOFF_SECONDS or 0.0), 0.0) * max(attempt_index, 1)


def _sleep_before_retry(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _run_with_adapter_retries(operation):
    attempts = 0
    retry_limit = _retry_limit()
    while True:
        attempts += 1
        try:
            return operation(), attempts
        except (NotImplementedError, SQLAlchemyError):
            raise
        except Exception:
            if attempts > retry_limit:
                raise
            _sleep_before_retry(_retry_backoff_seconds(attempts))


def _base_sync_status(*, cursor_key: str, configured: bool) -> dict[str, Any]:
    return {
        'cursor_key': cursor_key,
        'cursor_value': None,
        'configured': configured,
        'migration_ready': True,
        'status': 'idle' if configured else 'unconfigured',
        'adapter': _current_adapter_name(),
        'source': 'mes_projection' if configured else 'local_entry',
        'stale_threshold_seconds': stale_threshold_seconds(),
        'retry_limit': _retry_limit(),
        'lag_seconds': None,
        'last_synced_at': None,
        'last_event_at': None,
        'last_run_status': 'idle',
        'last_run_started_at': None,
        'last_run_finished_at': None,
        'fetched_count': 0,
        'upserted_count': 0,
        'replayed_count': 0,
        'error_message': None,
        'last_error': None,
        'action_required': 'none' if configured else 'configure_mes',
        'required_env': [] if configured else required_env_for_adapter(),
    }


def _projection_migration_missing_status(*, cursor_key: str) -> dict[str, Any]:
    payload = _base_sync_status(cursor_key=cursor_key, configured=True)
    payload.update(
        {
            'migration_ready': False,
            'status': 'migration_missing',
            'source': 'local_entry',
            'action_required': 'run_migration',
        }
    )
    return payload


def _status_from_lag(lag_seconds: float | None) -> str:
    if lag_seconds is None:
        return 'idle'
    if lag_seconds > stale_threshold_seconds():
        return 'stale'
    return 'fresh'


def _is_projection_shape_error(exc: Exception) -> bool:
    if not isinstance(exc, (ProgrammingError, OperationalError)):
        return False
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            'mes_coil_snapshots',
            'mes_sync_cursors',
            'mes_sync_run_logs',
            'no such table',
            'no such column',
            'undefined column',
            'does not exist',
            'unknown column',
        )
    )


def _ensure_cursor(db: Session, *, cursor_key: str) -> MesSyncCursor:
    entity = _query_first(db.query(MesSyncCursor).filter(MesSyncCursor.cursor_key == cursor_key))
    if entity is not None:
        return entity
    entity = MesSyncCursor(cursor_key=cursor_key)
    db.add(entity)
    db.flush()
    return entity


def _serialize_snapshot(snapshot: CoilSnapshot) -> dict[str, Any]:
    business_date = _snapshot_business_date(snapshot)
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
        'business_date': business_date.isoformat() if business_date else None,
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


def _upsert_snapshot(
    db: Session,
    *,
    snapshot: CoilSnapshot,
    synced_at: datetime,
    affected_business_dates: set[Any] | None = None,
) -> tuple[bool, bool]:
    projection = _projection_fields(snapshot, synced_at)
    coil_id = projection['coil_id']
    _lock_snapshot_key(db, coil_id=coil_id)
    existing = _query_first(db.query(MesCoilSnapshot).filter(MesCoilSnapshot.coil_id == coil_id))
    if existing is None and projection.get('mes_product_id'):
        existing = _query_first(db.query(MesCoilSnapshot).filter(MesCoilSnapshot.mes_product_id == projection['mes_product_id']))
        if existing is not None:
            existing.coil_id = coil_id
    payload = _serialize_snapshot(snapshot)
    business_date = _snapshot_business_date(snapshot)
    if affected_business_dates is not None and business_date is not None:
        affected_business_dates.add(business_date)
    if existing is None:
        entity = MesCoilSnapshot(
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
        db.add(entity)
        db.flush()
        return True, False

    previous_business_date = getattr(existing, 'business_date', None)
    if affected_business_dates is not None and previous_business_date is not None:
        affected_business_dates.add(previous_business_date)

    incoming_updated_at = _as_utc(snapshot.updated_at or snapshot.event_time)
    existing_updated_at = _as_utc(existing.updated_from_mes_at)
    if (
        existing_updated_at is not None
        and incoming_updated_at is not None
        and incoming_updated_at < existing_updated_at
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
        (snapshots, next_cursor), attempt_count = _run_with_adapter_retries(
            lambda: adapter.list_coil_snapshots(
                cursor=cursor.cursor_value,
                updated_after=window_started_at,
                limit=settings.MES_SYNC_LIMIT,
            )
        )
    except Exception as exc:  # noqa: BLE001
        run_log.finished_at = _utcnow()
        run_log.status = 'failed'
        run_log.error_message = redact_secret_text(str(exc))
        metadata = run_log.metadata_json if isinstance(run_log.metadata_json, dict) else {}
        run_log.metadata_json = {
            **metadata,
            'attempt_count': metadata.get('attempt_count', _retry_limit() + 1),
            'retry_limit': _retry_limit(),
        }
        raise MesSyncVendorError(run_log.error_message) from exc

    run_log.metadata_json = {
        **(run_log.metadata_json or {}),
        'attempt_count': attempt_count,
        'retry_limit': _retry_limit(),
    }
    upserted_count = 0
    replayed_count = 0
    last_event_at = cursor.last_event_at
    affected_business_dates: set[Any] = set()
    for item in snapshots:
        changed, replayed = _upsert_snapshot(
            db,
            snapshot=item,
            synced_at=synced_at,
            affected_business_dates=affected_business_dates,
        )
        if changed:
            upserted_count += 1
        if replayed:
            replayed_count += 1
        event_at = _as_utc(item.updated_at or item.event_time)
        if event_at and (last_event_at is None or event_at > _as_utc(last_event_at)):
            last_event_at = event_at

    cursor.cursor_value = next_cursor
    cursor.window_started_at = window_started_at
    cursor.last_event_at = last_event_at
    cursor.last_synced_at = synced_at
    _refresh_affected_daily_wip_snapshots(db, business_dates=affected_business_dates, snapshot_at=synced_at)

    lag_seconds = None
    if last_event_at is not None:
        normalized_last_event = last_event_at if last_event_at.tzinfo else last_event_at.replace(tzinfo=timezone.utc)
        lag_seconds = max((synced_at - normalized_last_event).total_seconds(), 0.0)

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
    affected_business_dates: set[Any] = set()
    for row in _dedupe_snapshots_by_projected_id(rows):
        changed, replayed = _upsert_snapshot(
            db,
            snapshot=row,
            synced_at=synced_at,
            affected_business_dates=affected_business_dates,
        )
        if changed:
            upserted_count += 1
        if replayed:
            replayed_count += 1
    _refresh_affected_daily_wip_snapshots(db, business_dates=affected_business_dates, snapshot_at=synced_at)
    return _stats(
        cursor_key=cursor_key,
        fetched_count=len(rows),
        upserted_count=upserted_count,
        replayed_count=replayed_count,
        synced_at=synced_at,
    )


def _upsert_by_source_id(db: Session, *, model: type, source_id: str, fields: Mapping[str, Any]) -> bool:
    existing = _query_first(db.query(model).filter(model.source_id == source_id))
    if existing is None:
        db.add(model(source_id=source_id, **fields))
        return True
    for key, value in fields.items():
        setattr(existing, key, value)
    return True


def _workshop_process_fields(record: MesSourceRecord, synced_at: datetime) -> dict[str, Any]:
    payload = _safe_payload(record.metadata)
    end_time = _record_event_time(record, 'EndDatetime', 'StrEndDatetime', 'CalcDatetime', 'StrOperateDate')
    input_kg = _to_float(_metadata_value(payload, 'BeginWeight', 'InputWeight', 'UpWeight'))
    output_kg = _to_float(_metadata_value(payload, 'EndWeight', 'OutputWeight', 'CalcWeight'))
    return {
        'source_path': record.source_path,
        'batch_no': _to_text(_metadata_value(payload, 'BatchNumber', 'BatchNo')),
        'customer_alias': _to_text(_metadata_value(payload, 'CustomerSimple', 'Customer', 'CustomerName')),
        'workshop_name': _to_text(_metadata_value(payload, 'WorkShop', 'Workshop', 'WorkShopName')),
        'process_name': _to_text(_metadata_value(payload, 'Process', 'ProcessName', 'WorkShopProcess')),
        'worker_name': _to_text(_metadata_value(payload, 'Worker', 'WorkerName', 'Operator')),
        'device_name': _to_text(_metadata_value(payload, 'DeviceName', 'Device', 'MachineName')),
        'input_weight_kg': input_kg,
        'input_weight_tons': _kg_to_tons(input_kg),
        'output_weight_kg': output_kg,
        'output_weight_tons': _kg_to_tons(output_kg),
        'yield_rate': _to_float(_metadata_value(payload, 'YieldRate', 'CraftYield')),
        'end_time': end_time,
        'business_date': resolve_production_business_date(end_time) if end_time is not None else _record_business_date(record, 'StrOperateDate'),
        'last_seen_from_mes_at': synced_at,
        'source_payload': payload,
    }


def _stock_fields(record: MesSourceRecord, synced_at: datetime) -> dict[str, Any]:
    payload = _safe_payload(record.metadata)
    in_stock_date = _record_event_time(record, 'InStockDate', 'StrInStockDate', 'OperateDate', 'CreateDate', 'AllocationDate')
    net_kg = _to_float(_metadata_value(payload, 'NetWeight', 'InStockNetWeight'))
    gross_kg = _to_float(_metadata_value(payload, 'GrossWeight'))
    return {
        'source_path': record.source_path,
        'batch_no': _to_text(_metadata_value(payload, 'BatchNumber', 'BatchNo')),
        'contract_no': _to_text(_metadata_value(payload, 'ContractCode', 'ContractNo')),
        'customer_alias': _to_text(_metadata_value(payload, 'CustomerSimple', 'Customer', 'CustomerName')),
        'net_weight_kg': net_kg,
        'net_weight_tons': _kg_to_tons(net_kg),
        'gross_weight_kg': gross_kg,
        'gross_weight_tons': _kg_to_tons(gross_kg),
        'in_stock_date': in_stock_date,
        'business_date': resolve_production_business_date(in_stock_date) if in_stock_date is not None else _record_business_date(record),
        'status_name': _to_text(_metadata_value(payload, 'StatusName', 'Status')),
        'last_seen_from_mes_at': synced_at,
        'source_payload': payload,
    }


def _material_fields(record: MesSourceRecord, synced_at: datetime) -> dict[str, Any]:
    payload = _safe_payload(record.metadata)
    production_date = _record_event_time(record, 'ProductionDate', 'StrProductionDate')
    weight_kg = _to_float(_metadata_value(payload, 'Weight', 'MaterialWeight'))
    return {
        'source_path': record.source_path,
        'material_code': _to_text(_metadata_value(payload, 'MaterialCode', 'MaterialAutoCode')),
        'workshop_name': _to_text(_metadata_value(payload, 'WorkShopRolling', 'PWorkShop', 'WorkShop')),
        'line_name': _to_text(_metadata_value(payload, 'WorkShopLine', 'LineName')),
        'position_name': _to_text(_metadata_value(payload, 'PositionName', 'Position')),
        'alloy_grade': _to_text(_metadata_value(payload, 'Alloy')),
        'spec_display': _to_text(_metadata_value(payload, 'Specification', 'Spec')),
        'weight_kg': weight_kg,
        'weight_tons': _kg_to_tons(weight_kg),
        'production_date': production_date,
        'business_date': resolve_production_business_date(production_date) if production_date is not None else _record_business_date(record),
        'status_name': _to_text(_metadata_value(payload, 'StatusName', 'Status')),
        'last_seen_from_mes_at': synced_at,
        'source_payload': payload,
    }


def _yield_fields(record: MesSourceRecord, synced_at: datetime) -> dict[str, Any]:
    payload = _safe_payload(record.metadata)
    report_time = _record_event_time(record, 'InStockDate', 'StrInStockDate', 'OperateDate', 'StrOperateDate')
    return {
        'source_path': record.source_path,
        'batch_no': _to_text(_metadata_value(payload, 'BatchNumber', 'BatchNo')),
        'contract_no': _to_text(_metadata_value(payload, 'ContractCode', 'ContractNo')),
        'customer_alias': _to_text(_metadata_value(payload, 'CustomerSimple', 'Customer', 'CustomerName')),
        'contract_total_weight_tons': _to_float(_metadata_value(payload, 'ContractTotalWeight', 'ContractNoticeDetailTotalWeight')),
        'feeding_weight_tons': _to_float(_metadata_value(payload, 'FeedingWeight')),
        'in_stock_net_weight_tons': _to_float(_metadata_value(payload, 'InStockNetWeight', 'NetWeight')),
        'yield_rate': _to_float(_metadata_value(payload, 'YieldRate', 'Yield')),
        'report_time': report_time,
        'business_date': resolve_production_business_date(report_time) if report_time is not None else _record_business_date(record),
        'last_seen_from_mes_at': synced_at,
        'source_payload': payload,
    }


def _reference_source_type(source_path: str) -> str:
    if source_path.startswith('/Craft/'):
        return 'craft'
    if source_path.startswith('/Device/'):
        return 'device'
    if source_path.startswith('/Dict/'):
        return 'dict'
    if source_path.startswith('/Material/'):
        return 'material_board'
    return source_path.strip('/').replace('/', '_').lower() or 'unknown'


def _upsert_reference_item(db: Session, *, record: MesSourceRecord, synced_at: datetime) -> bool:
    payload = _safe_payload(record.metadata)
    source_type = _reference_source_type(record.source_path)
    source_id = _source_id(record, 'Id', 'Code', 'Name')
    existing = _query_first(
        db.query(MesReferenceItem).filter(
            MesReferenceItem.source_type == source_type,
            MesReferenceItem.source_id == source_id,
        )
    )
    fields = {
        'source_path': record.source_path,
        'code': _to_text(_metadata_value(payload, 'Code')),
        'name': _to_text(_metadata_value(payload, 'Name', 'Craft', 'DeviceName')),
        'parent_id': _to_text(_metadata_value(payload, 'PID', 'ParentID', 'WorkShopID')),
        'workshop_name': _to_text(_metadata_value(payload, 'WorkShop', 'WorkShopName')),
        'status_name': _to_text(_metadata_value(payload, 'StatusName', 'Status')),
        'last_seen_from_mes_at': synced_at,
        'source_payload': payload,
    }
    if existing is None:
        db.add(MesReferenceItem(source_type=source_type, source_id=source_id, **fields))
        return True
    for key, value in fields.items():
        setattr(existing, key, value)
    return True


def _sync_source_records(
    db: Session,
    *,
    cursor_key: str,
    rows: list[MesSourceRecord],
    synced_at: datetime,
    model: type,
    field_builder,
    id_keys: tuple[str, ...] = ('Id',),
) -> MesSyncStats:
    upserted_count = 0
    deduped_rows: dict[str, MesSourceRecord] = {}
    for row in rows:
        source_id = _source_id(row, *id_keys)
        deduped_rows[source_id] = row
    for source_id, row in deduped_rows.items():
        if _upsert_by_source_id(db, model=model, source_id=source_id, fields=field_builder(row, synced_at)):
            upserted_count += 1
    return _stats(cursor_key=cursor_key, fetched_count=len(rows), upserted_count=upserted_count, synced_at=synced_at)


def sync_mes_workshop_process_records(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_workshop_process_records(limit=settings.MES_SYNC_LIMIT)
    return _sync_source_records(
        db,
        cursor_key='mes_workshop_process_records',
        rows=rows,
        synced_at=synced_at,
        model=MesWorkshopProcessRecord,
        field_builder=_workshop_process_fields,
        id_keys=('Id', 'BatchNumber'),
    )


def sync_mes_stock_records(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_stock_records(limit=settings.MES_SYNC_LIMIT)
    return _sync_source_records(
        db,
        cursor_key='mes_stock_records',
        rows=rows,
        synced_at=synced_at,
        model=MesStockRecord,
        field_builder=_stock_fields,
        id_keys=('Id', 'BatchNumber'),
    )


def sync_mes_material_records(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_material_records(limit=settings.MES_SYNC_LIMIT)
    return _sync_source_records(
        db,
        cursor_key='mes_material_records',
        rows=rows,
        synced_at=synced_at,
        model=MesMaterialRecord,
        field_builder=_material_fields,
        id_keys=('MaterialCode', 'Id'),
    )


def sync_mes_yield_records(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_yield_records(limit=settings.MES_SYNC_LIMIT)
    return _sync_source_records(
        db,
        cursor_key='mes_yield_records',
        rows=rows,
        synced_at=synced_at,
        model=MesYieldRecord,
        field_builder=_yield_fields,
        id_keys=('Id', 'BatchNumber'),
    )


def sync_mes_reference_items(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_reference_items()
    upserted_count = 0
    deduped_rows: dict[tuple[str, str], MesSourceRecord] = {}
    for row in rows:
        key = (_reference_source_type(row.source_path), _source_id(row, 'Id', 'Code', 'Name'))
        deduped_rows[key] = row
    for row in deduped_rows.values():
        if _upsert_reference_item(db, record=row, synced_at=synced_at):
            upserted_count += 1
    return _stats(cursor_key='mes_reference_items', fetched_count=len(rows), upserted_count=upserted_count, synced_at=synced_at)


def sync_mes_follow_cards(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_follow_cards(limit=settings.MES_SYNC_LIMIT)
    return _sync_coil_list(db, cursor_key='mes_follow_cards', rows=rows, synced_at=synced_at)


def sync_mes_dispatch(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_dispatch(limit=settings.MES_SYNC_LIMIT)
    return _sync_coil_list(db, cursor_key='mes_dispatch', rows=rows, synced_at=synced_at)


def _merge_wip_payload(existing_payload: Any, incoming_payload: Any) -> dict[str, Any]:
    if isinstance(existing_payload, Mapping) and isinstance(existing_payload.get('merged_items'), list):
        return {'merged_items': [*existing_payload['merged_items'], incoming_payload]}
    return {'merged_items': [existing_payload, incoming_payload]}


def _merge_wip_fields(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    target['doing_count'] = int(target.get('doing_count') or 0) + int(incoming.get('doing_count') or 0)
    target['doing_weight_tons'] = round(float(target.get('doing_weight_tons') or 0) + float(incoming.get('doing_weight_tons') or 0), 6)
    target['source_payload'] = _merge_wip_payload(target.get('source_payload'), incoming.get('source_payload'))


def sync_mes_wip_total(db: Session, *, now: datetime | None = None) -> MesSyncStats:
    synced_at = now or _utcnow()
    rows = get_mes_adapter().list_wip_totals()
    merged_fields: dict[str, dict[str, Any]] = {}
    for row in rows:
        process_totals = _to_mapping(row.metadata.get('process_totals'))
        if process_totals:
            for process_name, weight in process_totals.items():
                source_id = f'{row.workshop_name}:{process_name}'
                fields = {
                    'workshop_name': row.workshop_name,
                    'process_name': _to_text(process_name),
                    'doing_count': row.doing_count,
                    'doing_weight_tons': _to_float(weight),
                    'snapshot_at': synced_at,
                    'source_payload': _safe_payload(row.metadata),
                }
                if source_id in merged_fields:
                    _merge_wip_fields(merged_fields[source_id], fields)
                else:
                    merged_fields[source_id] = fields
            continue
        source_id = f'{row.workshop_name}:total'
        fields = {
            'workshop_name': row.workshop_name,
            'process_name': None,
            'doing_count': row.doing_count,
            'doing_weight_tons': row.doing_weight,
            'snapshot_at': synced_at,
            'source_payload': _safe_payload(row.metadata),
        }
        if source_id in merged_fields:
            _merge_wip_fields(merged_fields[source_id], fields)
        else:
            merged_fields[source_id] = fields
    upserted_count = 0
    for source_id, fields in merged_fields.items():
        if _upsert_by_source_id(db, model=MesWipTotalSnapshot, source_id=source_id, fields=fields):
            upserted_count += 1
    return _stats(cursor_key='mes_wip_total', fetched_count=len(rows), upserted_count=upserted_count, synced_at=synced_at)


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


def _sync_projection_step(
    db: Session,
    *,
    cursor_key: str,
    synced_at: datetime,
    runner,
) -> MesSyncStats:
    try:
        stats, _attempt_count = _run_with_adapter_retries(lambda: runner(db, now=synced_at))
        return stats
    except NotImplementedError as exc:
        return _stats(
            cursor_key=cursor_key,
            fetched_count=0,
            synced_at=synced_at,
            status='skipped',
            error_message=redact_secret_text(f'not implemented: {exc}'),
        )
    except SQLAlchemyError:
        raise
    except Exception as exc:  # noqa: BLE001
        return _stats(
            cursor_key=cursor_key,
            fetched_count=0,
            synced_at=synced_at,
            status='failed',
            error_message=redact_secret_text(str(exc)),
        )


def _run_projection_steps(
    db: Session,
    *,
    synced_at: datetime,
    steps: tuple[tuple[str, str], ...],
) -> list[MesSyncStats]:
    return [
        _sync_projection_step(db, cursor_key=cursor_key, synced_at=synced_at, runner=globals()[runner_name])
        for cursor_key, runner_name in steps
    ]


REALTIME_PROJECTION_STEPS = (
    ('mes_follow_cards', 'sync_mes_follow_cards'),
    ('mes_dispatch', 'sync_mes_dispatch'),
)

BUSINESS_PROJECTION_STEPS = (
    ('mes_wip_total', 'sync_mes_wip_total'),
    ('mes_stock', 'sync_mes_stock'),
    ('mes_workshop_process_records', 'sync_mes_workshop_process_records'),
    ('mes_stock_records', 'sync_mes_stock_records'),
    ('mes_material_records', 'sync_mes_material_records'),
    ('mes_yield_records', 'sync_mes_yield_records'),
)

REFERENCE_PROJECTION_STEPS = (
    ('mes_crafts', 'sync_mes_crafts'),
    ('mes_devices', 'sync_mes_devices'),
    ('mes_reference_items', 'sync_mes_reference_items'),
    ('mes_machine_lines', 'sync_mes_machine_lines'),
)


def sync_mes_realtime_projection(db: Session, *, now: datetime | None = None) -> list[MesSyncStats]:
    synced_at = now or _utcnow()
    return _run_projection_steps(db, synced_at=synced_at, steps=REALTIME_PROJECTION_STEPS)


def sync_mes_business_projection(db: Session, *, now: datetime | None = None) -> list[MesSyncStats]:
    synced_at = now or _utcnow()
    return _run_projection_steps(db, synced_at=synced_at, steps=BUSINESS_PROJECTION_STEPS)


def sync_mes_reference_projection(db: Session, *, now: datetime | None = None) -> list[MesSyncStats]:
    synced_at = now or _utcnow()
    return _run_projection_steps(db, synced_at=synced_at, steps=REFERENCE_PROJECTION_STEPS)


def sync_mes_projection(db: Session, *, now: datetime | None = None) -> list[MesSyncStats]:
    synced_at = now or _utcnow()
    return (
        sync_mes_reference_projection(db, now=synced_at)
        + sync_mes_realtime_projection(db, now=synced_at)
        + sync_mes_business_projection(db, now=synced_at)
    )


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
    current = _as_utc(now) or _utcnow()
    cursor = _query_first(db.query(MesSyncCursor).filter(MesSyncCursor.cursor_key == cursor_key))
    if cursor is None or cursor.last_event_at is None:
        latest = _query_first(
            db.query(MesCoilSnapshot).order_by(MesCoilSnapshot.updated_from_mes_at.desc().nullslast(), MesCoilSnapshot.id.desc())
        )
        latest_updated_at = _as_utc(latest.updated_from_mes_at) if latest is not None else None
        if latest_updated_at is None:
            return None
        return max((current - latest_updated_at).total_seconds(), 0.0)
    cursor_last_event_at = _as_utc(cursor.last_event_at)
    if cursor_last_event_at is None:
        return None
    return max((current - cursor_last_event_at).total_seconds(), 0.0)


def latest_sync_status(db: Session, *, cursor_key: str = SYNC_CURSOR_KEY, now: datetime | None = None) -> dict[str, Any]:
    if not _adapter_configured():
        return _base_sync_status(cursor_key=cursor_key, configured=False)

    current = now or _utcnow()
    try:
        cursor = _query_first(db.query(MesSyncCursor).filter(MesSyncCursor.cursor_key == cursor_key))
        latest_run = _query_first(
            db.query(MesSyncRunLog)
            .filter(MesSyncRunLog.cursor_key == cursor_key)
            .order_by(MesSyncRunLog.started_at.desc(), MesSyncRunLog.id.desc())
        )
        lag_seconds = compute_sync_lag_seconds(db, cursor_key=cursor_key, now=current)
    except Exception as exc:  # noqa: BLE001
        if _is_projection_shape_error(exc):
            return _projection_migration_missing_status(cursor_key=cursor_key)
        raise

    last_run_status = latest_run.status if latest_run else 'idle'
    status = 'failed' if last_run_status == 'failed' else _status_from_lag(lag_seconds)
    if status == 'failed':
        action_required = 'check_vendor'
    elif status == 'stale':
        action_required = 'check_sync_lag'
    else:
        action_required = 'none'
    error_message = redact_secret_text(latest_run.error_message) if latest_run and latest_run.error_message else None
    return {
        'cursor_key': cursor_key,
        'cursor_value': cursor.cursor_value if cursor else None,
        'configured': True,
        'migration_ready': True,
        'status': status,
        'adapter': _current_adapter_name(),
        'source': 'mes_projection',
        'stale_threshold_seconds': stale_threshold_seconds(),
        'retry_limit': _retry_limit(),
        'last_event_at': cursor.last_event_at.isoformat() if cursor and cursor.last_event_at else None,
        'last_synced_at': cursor.last_synced_at.isoformat() if cursor and cursor.last_synced_at else None,
        'lag_seconds': lag_seconds,
        'last_run_status': last_run_status,
        'last_run_started_at': latest_run.started_at.isoformat() if latest_run else None,
        'last_run_finished_at': latest_run.finished_at.isoformat() if latest_run and latest_run.finished_at else None,
        'fetched_count': latest_run.fetched_count if latest_run else 0,
        'upserted_count': latest_run.upserted_count if latest_run else 0,
        'replayed_count': latest_run.replayed_count if latest_run else 0,
        'error_message': error_message,
        'last_error': error_message,
        'action_required': action_required,
    }


def recent_sync_runs(db: Session, *, cursor_key: str = SYNC_CURSOR_KEY, limit: int = 12) -> dict[str, Any]:
    resolved_limit = max(1, min(int(limit or 12), 50))
    empty_summary = {
        'total_count': 0,
        'success_count': 0,
        'failed_count': 0,
        'running_count': 0,
        'latest_status': 'unconfigured' if not _adapter_configured() else 'idle',
    }
    if not _adapter_configured():
        return {'cursor_key': cursor_key, 'limit': resolved_limit, 'summary': empty_summary, 'items': []}

    rows = (
        db.query(MesSyncRunLog)
        .filter(MesSyncRunLog.cursor_key == cursor_key)
        .order_by(MesSyncRunLog.started_at.desc(), MesSyncRunLog.id.desc())
        .limit(resolved_limit)
        .all()
    )
    items = [
        {
            'cursor_key': row.cursor_key,
            'started_at': row.started_at.isoformat() if row.started_at else None,
            'finished_at': row.finished_at.isoformat() if row.finished_at else None,
            'status': row.status,
            'fetched_count': row.fetched_count,
            'upserted_count': row.upserted_count,
            'replayed_count': row.replayed_count,
            'duration_seconds': _duration_seconds(row.started_at, row.finished_at),
            'lag_seconds': _to_float(row.lag_seconds),
            'error_message': redact_secret_text(row.error_message) if row.error_message else None,
        }
        for row in rows
    ]
    summary = {
        'total_count': len(items),
        'success_count': sum(1 for item in items if item['status'] == 'success'),
        'failed_count': sum(1 for item in items if item['status'] == 'failed'),
        'running_count': sum(1 for item in items if item['status'] == 'running'),
        'latest_status': items[0]['status'] if items else 'idle',
    }
    return {'cursor_key': cursor_key, 'limit': resolved_limit, 'summary': summary, 'items': items}
