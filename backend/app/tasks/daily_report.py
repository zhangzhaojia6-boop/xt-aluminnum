from __future__ import annotations

from datetime import date

from app.agents.aggregator import aggregator_agent
from app.agents.reporter import reporter_agent
from app.core.business_time import last_completed_production_business_date
from app.database import get_sessionmaker


def generate_daily_reports(target_date: date | None = None) -> dict[str, str]:
    business_date = target_date or last_completed_production_business_date()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        aggregator_agent.execute(db=session, target_date=business_date)
        session.commit()
        reporter_agent.execute(db=session, target_date=business_date)
        session.commit()
    return {'status': 'ok', 'business_date': business_date.isoformat()}
