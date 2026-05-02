from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from app.config import settings
from app.core.event_bus import event_bus
from app.core.field_permissions import normalize_role
from app.core.workflow_events import attach_workflow_event, build_workflow_event
from app.models.attendance import AttendanceException, AttendanceResult
from app.models.attendance import AttendanceSchedule
from app.models.imports import ImportBatch
from app.models.master import Workshop
from app.models.production import MobileShiftReport, ProductionException, ShiftProductionData
from app.models.reconciliation import DataReconciliationItem
from app.services import energy_service
from app.services import mes_sync_service
from app.services import quality_service
from app.models.reports import DailyReport
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.contract_canonical_service import build_contract_projection
from app.services.contract_progress_projection_service import build_contract_progress_projection
from app.services.contract_delivery_target_service import resolve_contract_delivery_targets
from app.services import leader_summary_service
from app.services.audit_service import record_audit
from app.services.deterministic_orchestration_service import build_runtime_orchestration_snapshot
from app.services.management_estimate_service import build_management_estimate
from app.services import mobile_report_service
from app.services import mobile_reminder_service
from app.services.yield_matrix_canonical_service import build_yield_matrix_projection
from app.services.yield_matrix_delivery_target_service import resolve_yield_matrix_delivery_targets
from app.services.production_service import (
    build_workshop_attendance_summary,
    build_workshop_output_summary,
    mark_shift_data_published,
)


VALID_REPORT_TYPES = ('production', 'attendance', 'exception')

CANONICAL_REPORT_SCOPE = 'auto_confirmed'

VALID_SCOPES = (CANONICAL_REPORT_SCOPE, 'confirmed_only', 'include_reviewed')

VALID_OUTPUT_MODES = ('json', 'text', 'both')

REQUIRED_IMPORT_TYPES = (
    'attendance_schedule',
    'attendance_clock',
    'production_shift',
    'energy',
    'mes_export',
)

READY_REPORT_STATUSES = {'approved', CANONICAL_REPORT_SCOPE}

def _safe_latest_mes_sync_status(db: Session) -> dict[str, Any]:
    try:
        return mes_sync_service.latest_sync_status(db)
    except Exception:  # noqa: BLE001
        return {
            'cursor_key': mes_sync_service.SYNC_CURSOR_KEY,
            'cursor_value': None,
            'last_event_at': None,
            'last_synced_at': None,
            'lag_seconds': None,
            'last_run_status': 'idle',
            'last_run_started_at': None,
            'last_run_finished_at': None,
            'fetched_count': 0,
            'upserted_count': 0,
            'replayed_count': 0,
            'error_message': None,
        }

def _safe_energy_summary_for_date(db: Session, *, target_date: date) -> dict[str, Any]:
    try:
        return energy_service.summarize_energy_for_date(db, business_date=target_date)
    except Exception:  # noqa: BLE001
        return {
            'total_energy': 0.0,
            'total_output_weight': 0.0,
            'energy_per_ton': None,
            'rows': [],
        }

def _safe_recent_import_batches(db: Session, *, limit: int = 10) -> list[ImportBatch]:
    try:
        return db.query(ImportBatch).order_by(ImportBatch.id.desc()).limit(limit).all()
    except Exception:  # noqa: BLE001
        return []

def _safe_recent_reports(db: Session, *, limit: int = 10) -> list[DailyReport]:
    try:
        return db.query(DailyReport).order_by(DailyReport.id.desc()).limit(limit).all()
    except Exception:  # noqa: BLE001
        return []

def _safe_latest_published_report_time(db: Session):
    try:
        return db.query(func.max(DailyReport.published_at)).filter(DailyReport.status == 'published').scalar()
    except Exception:  # noqa: BLE001
        return None

def _safe_pending_shift_items(db: Session, *, target_date: date, limit: int = 20) -> list[ShiftProductionData]:
    try:
        return (
            db.query(ShiftProductionData)
            .filter(ShiftProductionData.business_date == target_date, ShiftProductionData.data_status.in_(['pending', 'reviewed']))
            .order_by(ShiftProductionData.id.desc())
            .limit(limit)
            .all()
        )
    except Exception:  # noqa: BLE001
        return []

def _normalize_blocker_summary(blocker_summary: Any) -> dict[str, Any]:
    if isinstance(blocker_summary, dict):
        digest = str(blocker_summary.get('digest') or '').strip()
        if digest:
            return {
                'has_blockers': bool(blocker_summary.get('has_blockers', True)),
                'digest': digest,
            }
    text = str(blocker_summary or '').strip()
    return {
        'has_blockers': bool(text),
        'digest': text or '未发现关键异常',
    }

def _to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)

def _workshop_name_map(db: Session) -> dict[int, str]:
    return {item.id: item.name for item in db.query(Workshop).all()}

def _shift_code_map(db: Session) -> dict[int, str]:
    return {item.id: item.code for item in db.query(ShiftConfig).all()}

def _normalize_scope(scope: str) -> str:
    if scope in VALID_SCOPES:
        return CANONICAL_REPORT_SCOPE
    raise ValueError('scope must be auto_confirmed, confirmed_only or include_reviewed')

def _mobile_report_decision_status(report: MobileShiftReport | None) -> str:
    if report is None:
        return 'unreported'
    returned_reason = (getattr(report, 'returned_reason', None) or '').strip()
    report_status = getattr(report, 'report_status', None)
    if returned_reason or report_status == 'returned':
        return 'returned'
    if report_status in READY_REPORT_STATUSES:
        return CANONICAL_REPORT_SCOPE
    return report_status or 'unreported'

def _is_leadership_ready_shift(item: ShiftProductionData, *, linked_report: MobileShiftReport | None) -> bool:
    if linked_report is not None:
        return _mobile_report_decision_status(linked_report) == CANONICAL_REPORT_SCOPE
    return item.data_status == 'confirmed'

def _query_shift_items(db: Session, *, report_date: date, scope: str) -> list[ShiftProductionData]:
    _ = _normalize_scope(scope)
    items = db.query(ShiftProductionData).filter(ShiftProductionData.business_date == report_date).all()
    linked_reports = (
        db.query(MobileShiftReport)
        .filter(
            MobileShiftReport.business_date == report_date,
            MobileShiftReport.linked_production_data_id.is_not(None),
        )
        .all()
    )
    report_map = {
        report.linked_production_data_id: report
        for report in linked_reports
        if report.linked_production_data_id is not None
    }
    return [
        item
        for item in items
        if _is_leadership_ready_shift(item, linked_report=report_map.get(item.id))
    ]
