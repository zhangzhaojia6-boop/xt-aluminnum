from __future__ import annotations

from datetime import date

from app.agents.aggregator import aggregator_agent
from app.agents.reporter import reporter_agent
from app.core.business_time import last_completed_production_business_date
from app.database import get_sessionmaker
from app.services import report as report_service


def generate_forecast_daily_report(target_date: date | None = None) -> dict[str, str]:
    business_date = target_date or last_completed_production_business_date()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        report_service.generate_production_stage_report(
            db=session,
            report_date=business_date,
            stage='forecast',
            scope='auto_confirmed',
            output_mode='both',
            operator=None,
        )
    return {'status': 'ok', 'business_date': business_date.isoformat(), 'stage': 'forecast'}


def generate_final_daily_report(target_date: date | None = None) -> dict[str, str]:
    business_date = target_date or last_completed_production_business_date()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        aggregator_agent.execute(db=session, target_date=business_date)
        session.commit()
        report_service.generate_production_stage_report(
            db=session,
            report_date=business_date,
            stage='final',
            scope='auto_confirmed',
            output_mode='both',
            operator=None,
        )
        reporter_agent.execute(db=session, target_date=business_date)
        session.commit()
    return {'status': 'ok', 'business_date': business_date.isoformat(), 'stage': 'final'}


def generate_daily_reports(target_date: date | None = None) -> dict[str, str]:
    return generate_final_daily_report(target_date)
