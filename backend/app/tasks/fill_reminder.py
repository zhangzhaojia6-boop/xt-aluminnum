from __future__ import annotations

from app.agents.reminder import reminder_agent
from app.core.health import current_business_date
from app.database import get_sessionmaker


def send_fill_reminders() -> dict[str, str]:
    target_date = current_business_date()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        reminder_agent.execute(db=session, target_date=target_date)
        session.commit()
    return {'status': 'ok', 'business_date': target_date.isoformat()}
