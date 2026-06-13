from __future__ import annotations

from datetime import date, datetime, timezone
import os

from sqlalchemy import text

from app.config import settings
from app.core.business_time import resolve_production_business_date
from app.database import get_engine, get_sessionmaker
from app.services import iot_energy_sync_service, mes_sync_service


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_business_date() -> date:
    return resolve_production_business_date()


def build_liveness_payload() -> dict:
    return {
        'status': 'ok',
        'service': settings.APP_NAME,
        'environment': settings.app_env_normalized,
        'timestamp': _utc_timestamp(),
        'checks': {
            'app': 'ok',
        },
    }


def _check_database() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        connection.execute(text('SELECT 1'))


def _check_upload_dir() -> None:
    upload_dir = settings.upload_dir_path
    upload_dir.mkdir(parents=True, exist_ok=True)
    if not os.access(upload_dir, os.W_OK):
        raise RuntimeError(f'upload dir is not writable: {upload_dir}')


def _sanitize_mes_sync_status(payload: dict) -> dict:
    sanitized = dict(payload)
    if sanitized.get('status') == 'failed':
        if sanitized.get('error_message'):
            sanitized['error_message'] = 'redacted'
        if sanitized.get('last_error'):
            sanitized['last_error'] = 'redacted'
    return sanitized


def _resolve_mes_sync_check(payload: dict) -> str:
    sync_status = payload.get('status')
    if sync_status in {'migration_missing', 'failed', 'stale', 'unconfigured'}:
        return sync_status
    if sync_status == 'fresh':
        return 'ok'

    sync_freshness_seconds = payload.get('sync_freshness_seconds')
    if sync_freshness_seconds is not None:
        return 'ok' if float(sync_freshness_seconds) <= mes_sync_service.stale_threshold_seconds() else 'stale'

    lag_seconds = payload.get('lag_seconds')
    if lag_seconds is None:
        return 'idle'
    return 'ok' if float(lag_seconds) <= mes_sync_service.stale_threshold_seconds() else 'stale'


def inspect_pipeline_readiness(*, target_date: date | None = None) -> dict:
    from app.services.config_readiness_service import inspect_pilot_config

    resolved_date = target_date or current_business_date()
    session_factory = get_sessionmaker()
    db = session_factory()
    try:
        return inspect_pilot_config(db, target_date=resolved_date)
    finally:
        db.close()


def build_readiness_payload() -> tuple[bool, dict]:
    checks: dict[str, str] = {}
    details: dict[str, dict] = {}
    ready = True

    for name, checker in (
        ('database', _check_database),
        ('uploads', _check_upload_dir),
    ):
        try:
            checker()
            checks[name] = 'ok'
        except Exception as exc:  # noqa: BLE001
            ready = False
            checks[name] = f'error:{exc.__class__.__name__}'

    if settings.AUTO_PIPELINE_REQUIRE_READY:
        try:
            pipeline_payload = inspect_pipeline_readiness()
            details['pipeline'] = pipeline_payload
            for check_name, check_payload in (pipeline_payload.get('checks') or {}).items():
                if isinstance(check_payload, dict) and check_payload.get('status'):
                    checks[check_name] = str(check_payload['status'])
            if pipeline_payload.get('hard_gate_passed'):
                if pipeline_payload.get('warning_issues'):
                    checks['pipeline'] = 'warning'
                else:
                    checks['pipeline'] = 'ok'
            else:
                ready = False
                checks['pipeline'] = 'blocked'
        except Exception as exc:  # noqa: BLE001
            ready = False
            checks['pipeline'] = f'error:{exc.__class__.__name__}'
    else:
        checks['pipeline'] = 'skipped'
        details['pipeline'] = {
            'target_date': current_business_date().isoformat(),
            'hard_gate_passed': True,
            'reason': 'AUTO_PIPELINE_REQUIRE_READY=false',
        }

    if (settings.MES_ADAPTER or 'null').strip().lower() == 'null':
        checks['mes_sync'] = 'unconfigured'
        details['mes_sync'] = {
            'configured': False,
            'migration_ready': True,
            'status': 'unconfigured',
            'source': 'local_entry',
            'lag_seconds': None,
            'action_required': 'configure_mes',
            'required_env': mes_sync_service.required_env_for_adapter(),
        }
    else:
        try:
            session_factory = get_sessionmaker()
            db = session_factory()
            try:
                mes_sync_status = mes_sync_service.latest_sync_status(db)
            finally:
                db.close()
            details['mes_sync'] = _sanitize_mes_sync_status(mes_sync_status)
            checks['mes_sync'] = _resolve_mes_sync_check(mes_sync_status)
        except Exception as exc:  # noqa: BLE001
            checks['mes_sync'] = f'error:{exc.__class__.__name__}'
            details['mes_sync'] = {
                'configured': True,
                'migration_ready': False,
                'status': 'failed',
                'source': 'mes_projection',
                'lag_seconds': None,
                'action_required': 'check_mes_sync',
                'error': exc.__class__.__name__,
            }

    if (settings.IOT_ENERGY_ADAPTER or 'null').strip().lower() == 'null':
        checks['iot_energy_sync'] = 'unconfigured'
        details['iot_energy_sync'] = {
            'configured': False,
            'status': 'unconfigured',
            'source': 'local_entry',
            'lag_seconds': None,
            'action_required': 'configure_iot_energy',
        }
    else:
        try:
            session_factory = get_sessionmaker()
            db = session_factory()
            try:
                iot_sync_status = iot_energy_sync_service.latest_sync_status(db)
            finally:
                db.close()
            details['iot_energy_sync'] = _sanitize_mes_sync_status(iot_sync_status)
            sync_status = iot_sync_status.get('status')
            if sync_status in {'failed', 'stale', 'unconfigured', 'idle'}:
                checks['iot_energy_sync'] = str(sync_status)
            else:
                checks['iot_energy_sync'] = 'ok'
        except Exception as exc:  # noqa: BLE001
            checks['iot_energy_sync'] = f'error:{exc.__class__.__name__}'
            details['iot_energy_sync'] = {
                'configured': True,
                'status': 'failed',
                'source': 'iot_energy',
                'lag_seconds': None,
                'action_required': 'check_iot_energy_sync',
                'error': exc.__class__.__name__,
            }

    payload = {
        'status': 'ready' if ready else 'not_ready',
        'service': settings.APP_NAME,
        'environment': settings.app_env_normalized,
        'timestamp': _utc_timestamp(),
        'checks': checks,
        'details': details,
    }
    return ready, payload
