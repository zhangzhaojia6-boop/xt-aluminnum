from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.core.health import current_business_date
from app.database import get_sessionmaker
from app.services import iot_energy_sync_service


def _publish_sync_event(result: dict[str, object]) -> None:
    try:
        from app.core.event_bus import event_bus

        event_bus.publish('iot_energy_sync_completed', {
            'business_date': result.get('business_date'),
            'source': 'iot_energy',
            'result': result,
        })
    except Exception:
        return


def sync_iot_energy_snapshots() -> dict[str, object]:
    SessionLocal = get_sessionmaker()
    business_date = current_business_date()
    with SessionLocal() as session:
        try:
            result = iot_energy_sync_service.sync_iot_energy_snapshots_from_settings(
                session,
                business_date=business_date,
            )
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            raise
    payload = {'business_date': business_date.isoformat(), 'iot_energy': result.to_dict()}
    _publish_sync_event(payload)
    return payload
