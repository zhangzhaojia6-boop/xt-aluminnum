from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.adapters import NullMesAdapter, get_mes_adapter, set_mes_adapter
from app.adapters.factory import create_mes_adapter
from app.config import settings
from app.core.redaction import filter_sensitive_mapping
from app.database import get_sessionmaker


_ACTION_BY_FAILURE_KIND = {
    'connection_failed': 'check_mes_connection',
    'query_timeout': 'check_mes_timeout',
    'schema_changed': 'check_mes_schema',
    'read_failed': 'check_mes_source',
}


def _publish_sync_event(event_type: str, payload: dict[str, object]) -> dict[str, object] | None:
    try:
        from app.core.event_bus import event_bus

        return event_bus.publish(event_type, {
            'business_date': None,
            'source': 'mes_projection',
            **payload,
        })
    except Exception:
        return None


def _safe_result(value):
    if isinstance(value, dict):
        filtered = filter_sensitive_mapping(value)
        return {
            key: _safe_result(item)
            for key, item in filtered.items()
            if key not in {'error_message', 'last_error', 'error'}
        }
    if isinstance(value, list):
        return [_safe_result(item) for item in value]
    return value


def _iter_sync_steps(value):
    if isinstance(value, dict):
        if 'cursor_key' in value and 'status' in value:
            yield value
        for item in value.values():
            yield from _iter_sync_steps(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_sync_steps(item)


def _signal_step(item: dict[str, object]) -> dict[str, object]:
    failure_kind = str(item.get('failure_kind') or 'read_failed')
    return {
        'cursor_key': str(item.get('cursor_key') or 'unknown'),
        'status': str(item.get('status') or 'unknown'),
        'attempt_count': max(1, int(item.get('attempt_count') or 1)),
        'failure_kind': failure_kind,
        'recovered': bool(item.get('recovered')),
        'action': _ACTION_BY_FAILURE_KIND.get(failure_kind, 'check_mes_source'),
    }


def _vendor_failure_step(exc) -> dict[str, object]:
    failure_kind = str(getattr(exc, 'failure_kind', None) or 'read_failed')
    return {
        'cursor_key': str(getattr(exc, 'cursor_key', None) or 'coil_snapshots'),
        'status': 'failed',
        'attempt_count': max(1, int(getattr(exc, 'attempt_count', 1) or 1)),
        'failure_kind': failure_kind,
        'recovered': False,
        'action': _ACTION_BY_FAILURE_KIND.get(failure_kind, 'check_mes_source'),
    }


def _run_sync_group(runner) -> dict[str, object]:
    from app.services import mes_sync_service

    _ensure_mes_adapter_initialized()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        try:
            result = runner(mes_sync_service, session)
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise
        except mes_sync_service.MesSyncVendorError as exc:
            session.commit()
            _publish_sync_event('mes_sync_failed', {'steps': [_vendor_failure_step(exc)]})
            raise
        except Exception:
            session.rollback()
            raise
    safe_result = _safe_result(result)
    _publish_sync_event('mes_sync_completed', {'result': safe_result})
    steps = list(_iter_sync_steps(result))
    failed_steps = [_signal_step(item) for item in steps if item.get('status') == 'failed']
    recovered_steps = [_signal_step(item) for item in steps if bool(item.get('recovered'))]
    if failed_steps:
        _publish_sync_event('mes_sync_failed', {'steps': failed_steps})
    if recovered_steps:
        _publish_sync_event('mes_sync_recovered', {'steps': recovered_steps})
    return result


def _ensure_mes_adapter_initialized() -> None:
    if (settings.MES_ADAPTER or 'null').strip().lower() == 'null':
        return
    if isinstance(get_mes_adapter(), NullMesAdapter):
        set_mes_adapter(create_mes_adapter())


def sync_mes_coil_snapshots() -> dict[str, object]:
    return _run_sync_group(
        lambda mes_sync_service, session: {
            'coil_snapshots': mes_sync_service.sync_coil_snapshots(db=session).to_dict(),
        }
    )


def sync_mes_realtime_projection() -> dict[str, object]:
    return _run_sync_group(
        lambda mes_sync_service, session: {
            'projection': [item.to_dict() for item in mes_sync_service.sync_mes_realtime_projection(db=session)],
        }
    )


def sync_mes_business_projection() -> dict[str, object]:
    return _run_sync_group(
        lambda mes_sync_service, session: {
            'projection': [item.to_dict() for item in mes_sync_service.sync_mes_business_projection(db=session)],
        }
    )


def sync_mes_month_to_date_projection() -> dict[str, object]:
    return _run_sync_group(
        lambda mes_sync_service, session: {
            'projection': [item.to_dict() for item in mes_sync_service.sync_mes_month_to_date_projection(db=session)],
        }
    )


def sync_mes_reference_projection() -> dict[str, object]:
    return _run_sync_group(
        lambda mes_sync_service, session: {
            'projection': [item.to_dict() for item in mes_sync_service.sync_mes_reference_projection(db=session)],
        }
    )
