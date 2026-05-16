from __future__ import annotations

from app.database import get_sessionmaker


def sync_mes_coil_snapshots() -> dict[str, object]:
    from app.services import mes_sync_service

    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        stats = mes_sync_service.sync_coil_snapshots(db=session)
        projection_stats = mes_sync_service.sync_mes_projection(db=session)
        session.commit()
    return {
        'coil_snapshots': stats.to_dict(),
        'projection': [item.to_dict() for item in projection_stats],
    }
