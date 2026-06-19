from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.aggregator import aggregator_agent
from app.agents.reporter import reporter_agent
from app.config import settings
from app.core.business_time import last_completed_production_business_date
from app.database import get_sessionmaker
from app.models.reports import DailyReport
from app.services import hermes_rag_service
from app.services.report import template_daily_report


def build_daily_report_product(
    db: Session,
    *,
    target_date: date,
    generated_by: str = 'hermes',
) -> dict[str, Any]:
    report = _ensure_daily_report(db, target_date=target_date)
    previous_template_payload = dict((report.report_data or {}).get('template_daily_report') or {})
    previous_template_text = str(previous_template_payload.get('text') or report.final_text_summary or '').strip()
    payload = template_daily_report.apply_template_daily_report_to_report(
        db,
        report=report,
        target_date=target_date,
    )
    payload_status = str(payload.get('status') or 'blocked')
    text = str(payload.get('text') or '').strip() if payload_status == 'ready' else ''
    now = datetime.now(timezone.utc)
    report_data = dict(report.report_data or {})
    report_data['daily_report_product'] = {
        'generated_by': generated_by,
        'generated_at': now.isoformat(),
        'status': payload_status,
        'missing_fields': payload.get('missing_fields') or [],
    }
    report.report_data = report_data
    if text:
        report.text_summary = report.text_summary or text
        report.final_text_summary = text
    elif payload_status != 'ready':
        report.final_text_summary = None
        if previous_template_text and str(report.text_summary or '').strip() == previous_template_text:
            report.text_summary = None
        report.status = 'draft'
        report.published_at = None
        report.published_by = None
        report.reviewed_at = None
        report.reviewed_by = None
        report.final_confirmed_by = None
        report.final_confirmed_at = None
        report.is_final_version = False
    report.generated_at = report.generated_at or now
    report.delivery_ready = payload_status == 'ready' and bool(text)
    if settings.AUTO_PUBLISH_ENABLED and report.delivery_ready and report.status in {'draft', 'reviewed'}:
        report.status = 'published'
        report.published_at = report.published_at or now
    db.flush()
    return {
        'status': payload_status,
        'business_date': target_date.isoformat(),
        'report_id': report.id,
        'text': text,
        'missing_fields': payload.get('missing_fields') or [],
        'conflicts': payload.get('conflicts') or [],
        'scheduled_at': '07:30',
    }


def generate_daily_reports(target_date: date | None = None) -> dict[str, Any]:
    business_date = target_date or last_completed_production_business_date()
    SessionLocal = get_sessionmaker()
    product: dict[str, Any] = {}
    with SessionLocal() as session:
        aggregator_agent.execute(db=session, target_date=business_date)
        session.commit()
        product = build_daily_report_product(session, target_date=business_date)
        session.commit()
        hermes_rag_service.archive_latest_daily_report_to_rag(
            session,
            report_date=business_date,
            generated_by='hermes',
        )
        session.commit()
        reporter_agent.execute(db=session, target_date=business_date)
        session.commit()
    result: dict[str, Any] = {'status': 'ok', 'business_date': business_date.isoformat()}
    for key, value in product.items():
        result['report_status' if key == 'status' else key] = value
    return result


def _ensure_daily_report(db: Session, *, target_date: date) -> DailyReport:
    report = (
        db.query(DailyReport)
        .filter(DailyReport.report_date == target_date, DailyReport.report_type == 'production')
        .order_by(DailyReport.published_at.desc().nullslast(), DailyReport.id.desc())
        .first()
    )
    if report is not None:
        return report
    report = DailyReport(
        report_date=target_date,
        report_type='production',
        generated_scope='auto_confirmed',
        output_mode='both',
        status='draft',
        report_data={},
    )
    db.add(report)
    db.flush()
    return report
