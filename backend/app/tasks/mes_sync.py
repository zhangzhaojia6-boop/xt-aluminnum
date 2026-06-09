from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.database import get_sessionmaker


def _publish_sync_event(result: dict[str, object]) -> None:
    try:
        from app.core.event_bus import event_bus

        event_bus.publish('mes_sync_completed', {
            'business_date': None,
            'source': 'mes_projection',
            'result': result,
        })
    except Exception:
        return


def _run_sync_group(runner) -> dict[str, object]:
    from app.services import mes_sync_service

    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        try:
            result = runner(mes_sync_service, session)
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise
        except mes_sync_service.MesSyncVendorError:
            session.commit()
            raise
        except Exception:
            session.rollback()
            raise
    _publish_sync_event(result)
    return result


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


def sync_mes_reference_projection() -> dict[str, object]:
    return _run_sync_group(
        lambda mes_sync_service, session: {
            'projection': [item.to_dict() for item in mes_sync_service.sync_mes_reference_projection(db=session)],
        }
    )
