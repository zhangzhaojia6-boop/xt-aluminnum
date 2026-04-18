from __future__ import annotations

from datetime import date, datetime, timezone
import os
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.config import settings
from app.database import get_engine, get_sessionmaker
from app.services import mes_sync_service


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_business_date() -> date:
    return datetime.now(ZoneInfo(settings.DEFAULT_TIMEZONE)).date()


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
            if pipeline_payload.get('hard_gate_passed'):
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

    if (settings.MES_ADAPTER or 'null').strip().lower() != 'null':
        try:
            session_factory = get_sessionmaker()
            db = session_factory()
            try:
                mes_sync_status = mes_sync_service.latest_sync_status(db)
            finally:
                db.close()
            details['mes_sync'] = mes_sync_status
            lag_seconds = mes_sync_status.get('lag_seconds')
            if lag_seconds is None:
                checks['mes_sync'] = 'idle'
            elif float(lag_seconds) <= max(settings.MES_SYNC_POLL_MINUTES, 1) * 300:
                checks['mes_sync'] = 'ok'
            else:
                checks['mes_sync'] = 'stale'
        except Exception as exc:  # noqa: BLE001
            checks['mes_sync'] = f'error:{exc.__class__.__name__}'
            details['mes_sync'] = {'error': str(exc)}

    payload = {
        'status': 'ready' if ready else 'not_ready',
        'service': settings.APP_NAME,
        'environment': settings.app_env_normalized,
        'timestamp': _utc_timestamp(),
        'checks': checks,
        'details': details,
    }
    return ready, payload
