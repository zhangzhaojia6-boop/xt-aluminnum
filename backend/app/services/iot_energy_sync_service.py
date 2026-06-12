from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import time
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.adapters.iot_energy_adapter import IotEnergyAdapter, NullIotEnergyAdapter, SqlServerIotEnergyAdapter
from app.config import Settings, settings
from app.core.redaction import redact_secret_text
from app.models.energy import IotEnergySnapshot, IotEnergySyncRun
from app.models.master import Equipment, Workshop


@dataclass(slots=True)
class IotEnergySyncResult:
    status: str
    records_read: int
    records_written: int
    sync_run_id: int | None
    error_message: str | None = None
    attempt_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            'status': self.status,
            'records_read': self.records_read,
            'records_written': self.records_written,
            'sync_run_id': self.sync_run_id,
            'error_message': self.error_message,
            'attempt_count': self.attempt_count,
        }


def get_iot_energy_adapter_for_settings(runtime_settings: Settings = settings) -> IotEnergyAdapter | None:
    adapter_name = (runtime_settings.IOT_ENERGY_ADAPTER or 'null').strip().lower()
    if adapter_name == 'sqlserver':
        return SqlServerIotEnergyAdapter(
            host=runtime_settings.IOT_ENERGY_SQLSERVER_HOST or '',
            port=runtime_settings.IOT_ENERGY_SQLSERVER_PORT,
            database=runtime_settings.IOT_ENERGY_SQLSERVER_DATABASE or '',
            username=runtime_settings.IOT_ENERGY_SQLSERVER_USERNAME or '',
            password=runtime_settings.IOT_ENERGY_SQLSERVER_PASSWORD or '',
            query=runtime_settings.IOT_ENERGY_SQLSERVER_QUERY or '',
            timeout_seconds=runtime_settings.IOT_ENERGY_SQLSERVER_TIMEOUT_SECONDS,
            encrypt=runtime_settings.IOT_ENERGY_SQLSERVER_ENCRYPT,
        )
    if adapter_name == 'null':
        return None
    return NullIotEnergyAdapter()


def sync_iot_energy_snapshots_from_settings(
    db: Session,
    *,
    business_date: date,
    runtime_settings: Settings = settings,
    now: datetime | None = None,
) -> IotEnergySyncResult:
    return sync_iot_energy_snapshots(
        db,
        business_date=business_date,
        adapter=get_iot_energy_adapter_for_settings(runtime_settings),
        meter_map=runtime_settings.iot_energy_meter_map,
        now=now,
        retry_limit=runtime_settings.IOT_ENERGY_SYNC_RETRY_LIMIT,
        retry_backoff_seconds=runtime_settings.IOT_ENERGY_SYNC_BACKOFF_SECONDS,
    )


def sync_iot_energy_snapshots(
    db: Session,
    *,
    business_date: date,
    adapter: IotEnergyAdapter | None,
    meter_map: Mapping[str, Mapping[str, str]] | None = None,
    limit: int = 500,
    now: datetime | None = None,
    source_system: str = 'iot_meter',
    retry_limit: int = 0,
    retry_backoff_seconds: float = 0.0,
    sleeper=time.sleep,
) -> IotEnergySyncResult:
    started_at = now or _utcnow()
    sync_run = IotEnergySyncRun(
        source_system=source_system,
        status='running',
        started_at=started_at,
        raw_payload={'business_date': business_date.isoformat(), 'limit': limit},
    )
    db.add(sync_run)
    db.flush()

    if adapter is None:
        return _finish_run(
            sync_run,
            status='skipped',
            records_read=0,
            records_written=0,
            error_message='未配置物联网能耗适配器',
        )

    readings = []
    attempt_count = 0
    max_attempts = max(int(retry_limit or 0), 0) + 1
    for attempt_index in range(max_attempts):
        attempt_count = attempt_index + 1
        try:
            readings = adapter.list_readings(business_date=business_date, limit=limit)
            break
        except Exception as exc:  # noqa: BLE001
            if attempt_count >= max_attempts:
                return _finish_run(
                    sync_run,
                    status='failed',
                    records_read=0,
                    records_written=0,
                    error_message=redact_secret_text(str(exc)),
                    attempt_count=attempt_count,
                    extra_payload={'retry_limit': max_attempts - 1},
                )
            delay_seconds = max(float(retry_backoff_seconds or 0.0), 0.0) * attempt_count
            if delay_seconds > 0:
                sleeper(delay_seconds)

    normalized_map = _normalize_meter_map(meter_map or {})
    records_written = 0
    for reading in readings:
        if not reading.meter_code or reading.reading_at is None:
            continue
        mapping = normalized_map.get(_normalize_code(reading.meter_code), {})
        workshop_id = _resolve_workshop_id(db, mapping.get('workshop_code'))
        machine_id = _resolve_machine_id(db, mapping.get('machine_code') or mapping.get('equipment_code'))
        existing = (
            db.query(IotEnergySnapshot)
            .filter(
                IotEnergySnapshot.source_system == source_system,
                IotEnergySnapshot.meter_code == reading.meter_code,
                IotEnergySnapshot.reading_at == reading.reading_at,
            )
            .one_or_none()
        )
        if existing is None:
            existing = IotEnergySnapshot(
                source_system=source_system,
                meter_code=reading.meter_code,
                reading_at=reading.reading_at,
                business_date=business_date,
            )
            db.add(existing)

        existing.sync_run_id = sync_run.id
        existing.business_date = business_date
        existing.workshop_id = workshop_id
        existing.machine_id = machine_id
        existing.meter_name = reading.meter_name
        existing.electricity_kwh = reading.electricity_kwh
        existing.gas_m3 = reading.gas_m3
        existing.water_m3 = reading.water_m3
        existing.raw_payload = {
            **(reading.metadata or {}),
            'mapping': dict(mapping),
        }
        records_written += 1

    return _finish_run(
        sync_run,
        status='success',
        records_read=len(readings),
        records_written=records_written,
        attempt_count=attempt_count,
        extra_payload={'retry_limit': max_attempts - 1},
    )


def _finish_run(
    sync_run: IotEnergySyncRun,
    *,
    status: str,
    records_read: int,
    records_written: int,
    error_message: str | None = None,
    attempt_count: int = 1,
    extra_payload: Mapping[str, Any] | None = None,
) -> IotEnergySyncResult:
    sync_run.finished_at = _utcnow()
    sync_run.status = status
    sync_run.records_read = records_read
    sync_run.records_written = records_written
    sync_run.error_message = error_message
    sync_run.raw_payload = {
        **(sync_run.raw_payload or {}),
        **dict(extra_payload or {}),
        'attempt_count': attempt_count,
    }
    return IotEnergySyncResult(
        status=status,
        records_read=records_read,
        records_written=records_written,
        sync_run_id=sync_run.id,
        error_message=error_message,
        attempt_count=attempt_count,
    )


def latest_sync_status(
    db: Session,
    *,
    now: datetime | None = None,
    runtime_settings: Settings = settings,
) -> dict[str, Any]:
    configured = (runtime_settings.IOT_ENERGY_ADAPTER or 'null').strip().lower() != 'null'
    threshold = stale_threshold_seconds(runtime_settings)
    if not configured:
        return {
            'configured': False,
            'status': 'unconfigured',
            'adapter': 'null',
            'source': 'local_entry',
            'stale_threshold_seconds': threshold,
            'retry_limit': runtime_settings.IOT_ENERGY_SYNC_RETRY_LIMIT,
            'lag_seconds': None,
            'last_synced_at': None,
            'action_required': 'configure_iot_energy',
        }

    current = _as_utc(now) or _utcnow()
    latest_run = (
        db.query(IotEnergySyncRun)
        .filter(IotEnergySyncRun.source_system == 'iot_meter')
        .order_by(IotEnergySyncRun.started_at.desc(), IotEnergySyncRun.id.desc())
        .first()
    )
    last_finished_at = _as_utc(latest_run.finished_at) if latest_run and latest_run.finished_at else None
    lag_seconds = max((current - last_finished_at).total_seconds(), 0.0) if last_finished_at else None
    last_run_status = latest_run.status if latest_run else 'idle'
    if last_run_status == 'failed':
        status = 'failed'
        action_required = 'check_iot_energy_vendor'
    elif lag_seconds is None:
        status = 'idle'
        action_required = 'wait_first_iot_energy_sync'
    elif lag_seconds > threshold:
        status = 'stale'
        action_required = 'check_iot_energy_lag'
    else:
        status = 'fresh'
        action_required = 'none'
    error_message = redact_secret_text(latest_run.error_message) if latest_run and latest_run.error_message else None
    return {
        'configured': True,
        'status': status,
        'adapter': (runtime_settings.IOT_ENERGY_ADAPTER or 'null').strip().lower(),
        'source': 'iot_energy',
        'stale_threshold_seconds': threshold,
        'retry_limit': runtime_settings.IOT_ENERGY_SYNC_RETRY_LIMIT,
        'lag_seconds': lag_seconds,
        'last_synced_at': last_finished_at.isoformat() if last_finished_at else None,
        'last_run_status': last_run_status,
        'last_run_started_at': latest_run.started_at.isoformat() if latest_run and latest_run.started_at else None,
        'last_run_finished_at': latest_run.finished_at.isoformat() if latest_run and latest_run.finished_at else None,
        'records_read': latest_run.records_read if latest_run else 0,
        'records_written': latest_run.records_written if latest_run else 0,
        'error_message': error_message,
        'last_error': error_message,
        'action_required': action_required,
    }


def stale_threshold_seconds(runtime_settings: Settings = settings) -> float:
    return float(max(runtime_settings.IOT_ENERGY_SYNC_POLL_SECONDS, 30) * 10)


def _normalize_meter_map(meter_map: Mapping[str, Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    return {_normalize_code(key): value for key, value in meter_map.items() if _normalize_code(key)}


def _normalize_code(value: Any) -> str:
    return str(value or '').strip().upper()


def _resolve_workshop_id(db: Session, code: str | None) -> int | None:
    normalized = _normalize_code(code)
    if not normalized:
        return None
    row = db.query(Workshop).filter(Workshop.code == normalized).one_or_none()
    return row.id if row else None


def _resolve_machine_id(db: Session, code: str | None) -> int | None:
    normalized = _normalize_code(code)
    if not normalized:
        return None
    row = db.query(Equipment).filter(Equipment.code == normalized).one_or_none()
    return row.id if row else None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
