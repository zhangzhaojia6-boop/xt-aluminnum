from __future__ import annotations

import logging

from app.database import get_sessionmaker
from app.services import agent_communication_service


logger = logging.getLogger(__name__)


def dispatch_due_agent_outbox_messages() -> dict[str, int]:
    """Dispatch due Agent outbox messages through the shared audited service."""

    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        try:
            outcomes = agent_communication_service.dispatch_due_outbox_messages(session)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception('Agent outbox dispatch failed')
            raise
    return {'status': 'ok', 'total': len(outcomes)}
