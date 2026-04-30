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


def _build_analysis_handoff(
    *,
    target_date: date,
    surface: str,
    total_output: float | None,
    history_digest: dict[str, Any],
    sync_status: dict[str, Any] | None,
    published_report_at: datetime | None,
    mobile_summary: dict[str, Any],
    delivery_status: dict[str, Any],
    energy_summary: dict[str, Any],
    energy_lane: list[dict[str, Any]],
    contract_lane: dict[str, Any],
    contract_progress: dict[str, Any],
    blocker_summary: dict[str, Any],
    exception_lane: dict[str, Any],
) -> dict[str, Any]:
    unreported_count = int(mobile_summary.get('unreported_count') or 0)
    returned_count = int(mobile_summary.get('returned_count') or 0)
    reporting_rate = round(_to_float(mobile_summary.get('reporting_rate')), 2)
    delivery_ready = bool(delivery_status.get('delivery_ready'))
    missing_steps = [str(item) for item in (delivery_status.get('missing_steps') or []) if item]
    has_blockers = bool(blocker_summary.get('has_blockers'))
    reconciliation_open_count = int(exception_lane.get('reconciliation_open_count') or 0)
    mobile_exception_count = int(exception_lane.get('mobile_exception_count') or 0)
    production_exception_count = int(exception_lane.get('production_exception_count') or 0)

    blocking_reasons: list[str] = []
    if unreported_count > 0:
        blocking_reasons.append('reporting_incomplete')
    if returned_count > 0:
        blocking_reasons.append('reporting_returned')
    if not delivery_ready:
        blocking_reasons.append('delivery_not_ready')
    if has_blockers:
        blocking_reasons.append('quality_blocker')
    if reconciliation_open_count > 0:
        blocking_reasons.append('reconciliation_open')

    attention_flags: list[str] = list(blocking_reasons)

    reporting_status = 'healthy'
    if unreported_count > 0:
        reporting_status = 'blocked'
    elif returned_count > 0:
        reporting_status = 'warning'

    delivery_status_label = 'healthy' if delivery_ready and not missing_steps else 'blocked'

    over_line_count = sum(1 for row in energy_lane if row.get('is_over_line'))
    energy_status = 'healthy'
    if energy_summary.get('energy_per_ton') is None:
        energy_status = 'idle'
    elif over_line_count > 0:
        energy_status = 'warning'
        attention_flags.append('energy_over_line')

    contract_quality_status = str(contract_lane.get('quality_status') or '').strip().lower()
    contract_status = 'healthy'
    if not contract_lane and surface == 'workshop':
        contract_status = 'idle'
    elif contract_quality_status in {'missing', 'blocked'}:
        contract_status = 'blocked'
    elif contract_quality_status == 'warning' or int(contract_progress.get('stalled_contract_count') or 0) > 0:
        contract_status = 'warning'
    if int(contract_progress.get('stalled_contract_count') or 0) > 0:
        attention_flags.append('contract_stalled')

    risk_status = 'healthy'
    if has_blockers or reconciliation_open_count > 0:
        risk_status = 'blocked'
    elif mobile_exception_count > 0 or production_exception_count > 0:
        risk_status = 'warning'
        attention_flags.append('exception_present')

    # Preserve order while removing duplicates across blocking and warning signals.
    attention_flags = list(dict.fromkeys(attention_flags))

    priority = 'low'
    if blocking_reasons:
        priority = 'high'
    elif attention_flags:
        priority = 'medium'

    contract_source_labels = ['专项补录', '系统汇总']
    if surface == 'workshop' and not contract_lane:
        contract_source_labels = ['系统汇总']

    snapshots = list(history_digest.get('daily_snapshots') or [])
    history_points = len(snapshots)
    sync_status_value = str((sync_status or {}).get('last_run_status') or 'idle')
    sync_lag_raw = (sync_status or {}).get('lag_seconds')
    sync_lag_seconds = int(sync_lag_raw) if sync_lag_raw is not None else None
    freshness_status = 'cold'
    if sync_status_value in {'failed', 'error'}:
        freshness_status = 'stale'
    elif sync_lag_seconds is not None and sync_lag_seconds > 3600:
        freshness_status = 'stale'
    elif published_report_at is not None and sync_status_value == 'success':
        freshness_status = 'fresh'
    elif history_points > 0:
        freshness_status = 'warming'

    data_gaps: list[str] = []
    if published_report_at is None:
        data_gaps.append('report_unpublished')
    if history_points == 0:
        data_gaps.append('history_unavailable')
    if freshness_status == 'stale':
        data_gaps.append('sync_stale')
    if contract_status == 'idle':
        data_gaps.append('contracts_unavailable')
    if energy_status == 'idle':
        data_gaps.append('energy_unavailable')

    section_statuses = {
        'reporting': reporting_status,
        'delivery': delivery_status_label,
        'energy': energy_status,
        'contracts': contract_status,
        'risk': risk_status,
    }
    section_matrix = {
        'healthy_sections': [key for key, value in section_statuses.items() if value == 'healthy'],
        'warning_sections': [key for key, value in section_statuses.items() if value == 'warning'],
        'blocked_sections': [key for key, value in section_statuses.items() if value == 'blocked'],
        'idle_sections': [key for key, value in section_statuses.items() if value == 'idle'],
    }
    section_reasons = {
        'reporting': [],
        'delivery': [],
        'energy': [],
        'contracts': [],
        'risk': [],
    }
    if unreported_count > 0:
        section_reasons['reporting'].append('reporting_incomplete')
    if returned_count > 0:
        section_reasons['reporting'].append('reporting_returned')
    if not delivery_ready:
        section_reasons['delivery'].append('delivery_not_ready')
    if over_line_count > 0:
        section_reasons['energy'].append('energy_over_line')
    if energy_status == 'idle':
        section_reasons['energy'].append('energy_unavailable')
    if contract_quality_status in {'missing', 'blocked', 'warning'}:
        section_reasons['contracts'].append(f'contract_quality_{contract_quality_status}')
    if int(contract_progress.get('stalled_contract_count') or 0) > 0:
        section_reasons['contracts'].append('contract_stalled')
    if contract_status == 'idle':
        section_reasons['contracts'].append('contracts_unavailable')
    if has_blockers:
        section_reasons['risk'].append('quality_blocker')
    if reconciliation_open_count > 0:
        section_reasons['risk'].append('reconciliation_open')
    if mobile_exception_count > 0 or production_exception_count > 0:
        section_reasons['risk'].append('exception_present')
    for key, values in section_reasons.items():
        section_reasons[key] = list(dict.fromkeys(values))
    source_matrix = {
        'reporting': ['主操直录'],
        'delivery': ['系统汇总', '结果发布'],
        'energy': ['专项补录', '系统汇总'],
        'contracts': contract_source_labels,
        'risk': ['系统汇总'],
    }
    source_variants = {
        'reporting': ['mobile'],
        'delivery': ['system', 'publish'],
        'energy': ['owner_only', 'system'],
        'contracts': ['system'] if contract_source_labels == ['系统汇总'] else ['owner_only', 'system'],
        'risk': ['system'],
    }
    action_matrix = {
        'reporting': [],
        'delivery': [],
        'energy': [],
        'contracts': [],
        'risk': [],
    }
    if unreported_count > 0:
        action_matrix['reporting'].append('check_unreported_shifts')
    if returned_count > 0:
        action_matrix['reporting'].append('review_returned_entries')
    if not action_matrix['reporting']:
        action_matrix['reporting'].append('watch_reporting_arrivals')

    if 'report_unpublished' in data_gaps:
        action_matrix['delivery'].append('publish_daily_report')
    if 'delivery_not_ready' in section_reasons['delivery']:
        action_matrix['delivery'].append('close_delivery_steps')
    if not action_matrix['delivery']:
        action_matrix['delivery'].append('watch_delivery_release')

    if 'energy_unavailable' in section_reasons['energy']:
        action_matrix['energy'].append('collect_energy_owner_entries')
    if 'energy_over_line' in section_reasons['energy']:
        action_matrix['energy'].append('review_energy_over_line')
    if not action_matrix['energy']:
        action_matrix['energy'].append('watch_energy_baseline')

    if 'contracts_unavailable' in section_reasons['contracts']:
        action_matrix['contracts'].append('collect_contract_owner_entries')
    if any(reason.startswith('contract_quality_') for reason in section_reasons['contracts']):
        action_matrix['contracts'].append('review_contract_quality')
    if 'contract_stalled' in section_reasons['contracts']:
        action_matrix['contracts'].append('review_stalled_contracts')
    if not action_matrix['contracts']:
        action_matrix['contracts'].append('watch_contract_progress')

    if 'quality_blocker' in section_reasons['risk']:
        action_matrix['risk'].append('clear_quality_blockers')
    if 'reconciliation_open' in section_reasons['risk']:
        action_matrix['risk'].append('close_reconciliation_items')
    if 'exception_present' in section_reasons['risk']:
        action_matrix['risk'].append('review_open_exceptions')
    if 'sync_stale' in data_gaps:
        action_matrix['risk'].append('refresh_pipeline_sync')
    if not action_matrix['risk']:
        action_matrix['risk'].append('watch_risk_signals')

    output_points = [
        _to_float(item.get('output_weight'))
        for item in snapshots
        if item.get('output_weight') is not None
    ]
    current_output = output_points[-1] if output_points else (_to_float(total_output) if total_output is not None else None)
    yesterday_output = output_points[-2] if len(output_points) >= 2 else None
    output_delta_vs_yesterday = None
    if current_output is not None and yesterday_output is not None:
        output_delta_vs_yesterday = round(current_output - yesterday_output, 2)
    seven_day_average_output = None
    if output_points:
        seven_day_average_output = round(sum(output_points) / len(output_points), 2)
    elif current_output is not None:
        seven_day_average_output = round(current_output, 2)

    return {
        'target_date': target_date.isoformat(),
        'surface': surface,
        'readiness': len(blocking_reasons) == 0,
        'blocking_reasons': blocking_reasons,
        'priority': priority,
        'attention_flags': attention_flags,
        'data_gaps': data_gaps,
        'section_matrix': section_matrix,
        'section_reasons': section_reasons,
        'source_matrix': source_matrix,
        'source_variants': source_variants,
        'action_matrix': action_matrix,
        'freshness': {
            'freshness_status': freshness_status,
            'sync_status': sync_status_value,
            'sync_lag_seconds': sync_lag_seconds,
            'history_points': history_points,
            'published_report_at': published_report_at.isoformat() if published_report_at else None,
        },
        'trend': {
            'current_output': round(current_output, 2) if current_output is not None else None,
            'yesterday_output': round(yesterday_output, 2) if yesterday_output is not None else None,
            'output_delta_vs_yesterday': output_delta_vs_yesterday,
            'seven_day_average_output': seven_day_average_output,
        },
        'reporting': {
            'status': reporting_status,
            'reporting_rate': reporting_rate,
            'reported_count': int(mobile_summary.get('reported_count') or 0),
            'unreported_count': unreported_count,
            'auto_confirmed_count': int(mobile_summary.get('auto_confirmed_count') or 0),
            'returned_count': returned_count,
            'source_labels': ['主操直录'],
        },
        'delivery': {
            'status': delivery_status_label,
            'delivery_ready': delivery_ready,
            'reports_generated': int(delivery_status.get('reports_generated') or 0),
            'reports_published_count': int(delivery_status.get('reports_published_count') or 0),
            'missing_steps': missing_steps,
            'source_labels': ['系统汇总', '结果发布'],
        },
        'energy': {
            'status': energy_status,
            'energy_per_ton': energy_summary.get('energy_per_ton'),
            'total_energy': energy_summary.get('total_energy'),
            'electricity_value': energy_summary.get('electricity_value'),
            'gas_value': energy_summary.get('gas_value'),
            'water_value': energy_summary.get('water_value'),
            'source_labels': ['专项补录', '系统汇总'],
        },
        'contracts': {
            'status': contract_status,
            'daily_contract_weight': contract_lane.get('daily_contract_weight'),
            'month_to_date_contract_weight': contract_lane.get('month_to_date_contract_weight'),
            'active_contract_count': int(contract_progress.get('active_contract_count') or 0),
            'stalled_contract_count': int(contract_progress.get('stalled_contract_count') or 0),
            'remaining_weight': round(_to_float(contract_progress.get('remaining_weight')), 2),
            'source_labels': contract_source_labels,
        },
        'risk': {
            'status': risk_status,
            'has_blockers': has_blockers,
            'blocker_digest': str(blocker_summary.get('digest') or '未发现关键异常'),
            'reconciliation_open_count': reconciliation_open_count,
            'mobile_exception_count': mobile_exception_count,
            'production_exception_count': production_exception_count,
            'source_labels': ['系统汇总'],
        },
    }


def resolve_report_delivery_payload(db: Session, *, entity: DailyReport) -> dict:
    report_data_value = getattr(entity, 'report_data', None)
    report_data = report_data_value if isinstance(report_data_value, dict) else {}
    yield_matrix_lane = report_data.get('yield_matrix_lane') if isinstance(report_data.get('yield_matrix_lane'), dict) else None
    if isinstance(yield_matrix_lane, dict) and yield_matrix_lane.get('quality_status') == 'ready':
        delivery_scope = (
            yield_matrix_lane.get('primary_delivery_scope')
            or (yield_matrix_lane.get('delivery_scopes') or [None])[0]
        )
        resolution = resolve_yield_matrix_delivery_targets(db, delivery_scope=delivery_scope)
        return {
            'delivery_lane': 'yield_matrix_lane',
            'delivery_scope': delivery_scope,
            'delivery_target': resolution.get('publisher_delivery_target'),
            'delivery_target_key': resolution.get('publisher_target_key'),
            'delivery_resolution_status': resolution.get('resolution_status'),
            'resolved_targets': resolution.get('resolved_targets', []),
        }

    contract_lane = report_data.get('contract_lane') if isinstance(report_data.get('contract_lane'), dict) else None
    if isinstance(contract_lane, dict):
        delivery_scope = (contract_lane.get('primary_delivery_scope') or (contract_lane.get('delivery_scopes') or [None])[0])
        resolution = resolve_contract_delivery_targets(db, delivery_scope=delivery_scope)
        return {
            'delivery_lane': 'contract_lane',
            'delivery_scope': delivery_scope,
            'delivery_target': resolution.get('publisher_delivery_target'),
            'delivery_target_key': resolution.get('publisher_target_key'),
            'delivery_resolution_status': resolution.get('resolution_status'),
            'resolved_targets': resolution.get('resolved_targets', []),
        }

    return {
        'delivery_lane': None,
        'delivery_scope': None,
        'delivery_target': None,
        'delivery_target_key': None,
        'delivery_resolution_status': None,
        'resolved_targets': [],
    }


def _build_report_event_payload(
    db: Session,
    *,
    event_type: str,
    entity: DailyReport,
    operator: User,
    note: str | None = None,
    published_shift_count: int | None = None,
) -> dict:
    report_date = entity.report_date.isoformat()
    base_payload = {
        'report_id': entity.id,
        'report_date': report_date,
        'report_type': entity.report_type,
        'workshop_id': entity.workshop_id,
        'scope': entity.generated_scope,
        'output_mode': entity.output_mode,
        'status': entity.status,
    }
    if note:
        base_payload['note'] = note
    if published_shift_count is not None:
        base_payload['published_shift_count'] = int(published_shift_count)

    delivery_payload = resolve_report_delivery_payload(db, entity=entity)

    workflow_workshop_id = entity.workshop_id
    if delivery_payload.get('delivery_target') == 'workshop' and str(delivery_payload.get('delivery_target_key') or '').isdigit():
        workflow_workshop_id = int(delivery_payload['delivery_target_key'])

    workflow_event = build_workflow_event(
        event_type=event_type,
        actor_role=normalize_role(operator.role),
        actor_id=operator.id,
        scope_type='workshop' if workflow_workshop_id is not None else 'factory',
        workshop_id=workflow_workshop_id,
        team_id=None,
        shift_id=None,
        entity_type='daily_report',
        entity_id=entity.id,
        status=entity.status,
        payload={
            'report_date': report_date,
            'report_type': entity.report_type,
            'scope': entity.generated_scope,
            'note': note,
            'published_shift_count': int(published_shift_count or 0),
            'delivery_lane': delivery_payload.get('delivery_lane'),
            'delivery_scope': delivery_payload.get('delivery_scope'),
            'delivery_target': delivery_payload.get('delivery_target'),
            'delivery_target_key': delivery_payload.get('delivery_target_key'),
            'delivery_resolution_status': delivery_payload.get('delivery_resolution_status'),
            'resolved_targets': delivery_payload.get('resolved_targets', []),
        },
    )
    return attach_workflow_event(base_payload, workflow_event)


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


def _generate_production_report(db: Session, *, report_date: date, scope: str) -> dict:
    canonical_scope = _normalize_scope(scope)
    workshop_map = _workshop_name_map(db)
    shift_map = _shift_code_map(db)
    items = _query_shift_items(db, report_date=report_date, scope=canonical_scope)
    mobile_summary = mobile_report_service.summarize_mobile_reporting(db, target_date=report_date)

    total_output = sum(_to_float(item.output_weight) for item in items)
    total_qualified = sum(_to_float(item.qualified_weight) for item in items)
    total_scrap = sum(_to_float(item.scrap_weight) for item in items)
    total_downtime = sum(int(item.downtime_minutes or 0) for item in items)
    total_issue_count = sum(int(item.issue_count or 0) for item in items)

    shift_output: dict[str, float] = {}
    workshop_output: dict[str, float] = {}
    auto_confirmed = int(mobile_summary.get('auto_confirmed_count', 0) or 0)
    reviewed = 0

    for item in items:
        shift_code = shift_map.get(item.shift_config_id, str(item.shift_config_id))
        workshop_name = workshop_map.get(item.workshop_id, f'Workshop-{item.workshop_id}')
        shift_output[shift_code] = shift_output.get(shift_code, 0.0) + _to_float(item.output_weight)
        workshop_output[workshop_name] = workshop_output.get(workshop_name, 0.0) + _to_float(item.output_weight)
    submitted = int(mobile_summary.get('submitted_count', 0) or 0)
    draft = int(mobile_summary.get('draft_count', 0) or 0)
    returned = int(mobile_summary.get('returned_count', 0) or 0)
    unreported = int(mobile_summary.get('unreported_count', 0) or 0)
    pending = submitted + draft + unreported
    production_exception_count = int(
        db.query(func.count(ProductionException.id))
        .filter(ProductionException.business_date == report_date, ProductionException.status == 'open')
        .scalar()
        or 0
    )
    attendance_exception_count = int(
        db.query(func.count(AttendanceException.id))
        .filter(AttendanceException.business_date == report_date, AttendanceException.status == 'open')
        .scalar()
        or 0
    )

    energy_summary = energy_service.summarize_energy_for_date(db, business_date=report_date)
    contract_lane = build_contract_projection(db, target_date=report_date)
    yield_matrix_lane = build_yield_matrix_projection(db, target_date=report_date)
    return {
        'report_date': report_date.isoformat(),
        'scope': canonical_scope,
        'canonical_scope': canonical_scope,
        'total_output_weight': total_output,
        'shift_count': len(items),
        'workshop_output': workshop_output,
        'shift_output': shift_output,
        'qualified_weight': total_qualified,
        'scrap_weight': total_scrap,
        'downtime_minutes': total_downtime,
        'issue_count': total_issue_count,
        'confirmed_shifts': auto_confirmed,
        'reviewed_shifts': reviewed,
        'pending_shifts': pending,
        'auto_confirmed_shifts': auto_confirmed,
        'submitted_shifts': submitted,
        'draft_shifts': draft,
        'returned_shifts': returned,
        'unreported_shifts': unreported,
        'pending_or_unreported_shifts': pending,
        'reported_shifts': int(mobile_summary.get('reported_count', 0) or 0),
        'production_exception_count': production_exception_count,
        'attendance_exception_count': attendance_exception_count,
        'total_energy': energy_summary['total_energy'],
        'energy_per_ton': energy_summary['energy_per_ton'],
        'energy_rows': energy_summary['rows'],
        'mobile_reporting_summary': mobile_summary,
        'contract_lane': contract_lane,
        'yield_matrix_lane': yield_matrix_lane,
    }


def _generate_attendance_report(db: Session, *, report_date: date) -> dict:
    results = db.query(AttendanceResult).filter(AttendanceResult.business_date == report_date).all()
    exceptions = db.query(AttendanceException).filter(AttendanceException.business_date == report_date).all()

    total = len(results)
    normal = len([item for item in results if item.attendance_status == 'normal'])
    abnormal = len([item for item in results if item.attendance_status != 'normal'])
    processed_ex = len([item for item in exceptions if item.status in {'confirmed', 'corrected', 'ignored'}])
    open_ex = len([item for item in exceptions if item.status == 'open'])
    attendance_count = len([item for item in results if item.attendance_status != 'absent'])

    return {
        'report_date': report_date.isoformat(),
        'attendance_count': attendance_count,
        'total_results': total,
        'normal_count': normal,
        'abnormal_count': abnormal,
        'processed_exception_count': processed_ex,
        'open_exception_count': open_ex,
    }


def _generate_exception_report(db: Session, *, report_date: date) -> dict:
    attendance_rows = (
        db.query(AttendanceException.exception_type, func.count(AttendanceException.id))
        .filter(AttendanceException.business_date == report_date)
        .group_by(AttendanceException.exception_type)
        .all()
    )
    production_rows = (
        db.query(ProductionException.exception_type, func.count(ProductionException.id))
        .filter(ProductionException.business_date == report_date)
        .group_by(ProductionException.exception_type)
        .all()
    )
    energy_diff_count = int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(
            DataReconciliationItem.business_date == report_date,
            DataReconciliationItem.reconciliation_type == 'energy_vs_production',
            DataReconciliationItem.status == 'open',
        )
        .scalar()
        or 0
    )
    return {
        'report_date': report_date.isoformat(),
        'attendance_exceptions': {item[0]: int(item[1]) for item in attendance_rows},
        'production_exceptions': {item[0]: int(item[1]) for item in production_rows},
        'energy_reconciliation_open': energy_diff_count,
    }


def _format_workshop_output_top(workshop_output: dict[str, float], *, limit: int = 4) -> str:
    if not workshop_output:
        return '\u6682\u65e0\u8f66\u95f4\u4ea7\u91cf\u6570\u636e'
    sorted_items = sorted(workshop_output.items(), key=lambda item: item[1], reverse=True)[:limit]
    return '\uff0c'.join(f'{name} {value:.2f} \u5428' for name, value in sorted_items)


def _build_production_text_summary(report_data: dict) -> str:
    date_text = report_data.get('report_date', '')
    workshop_output = report_data.get('workshop_output', {})
    return (
        f'{date_text}\uff0cAgent \u81ea\u52a8\u786e\u8ba4\u73ed\u6b21 {report_data.get("auto_confirmed_shifts", 0)} \u4e2a\uff0c'
        f'\u5f85\u8865\u62a5/\u672a\u95ed\u73af {report_data.get("pending_or_unreported_shifts", 0)} \u4e2a\uff0c'
        f'\u5f02\u5e38\u9000\u56de {report_data.get("returned_shifts", 0)} \u4e2a\u3002'
        f'\u5168\u5382\u4ea7\u51fa {report_data.get("total_output_weight", 0):.2f} \u5428\uff0c'
        f'\u8f66\u95f4\u4ea7\u91cf\uff1a{_format_workshop_output_top(workshop_output)}\u3002'
        f'\u4eca\u65e5\u751f\u4ea7\u5f02\u5e38 {report_data.get("production_exception_count", 0)} \u6761\uff0c'
        f'\u8003\u52e4\u5f02\u5e38 {report_data.get("attendance_exception_count", 0)} \u6761\uff0c'
        f'\u7d2f\u8ba1\u505c\u673a {report_data.get("downtime_minutes", 0)} \u5206\u949f\u3002'
        '\u5f53\u524d\u6574\u4f53\u751f\u4ea7\u53ef\u63a7\uff0c\u5efa\u8bae\u4f18\u5148\u95ed\u73af\u9000\u56de\u539f\u56e0\u5e76\u8865\u9f50\u672a\u62a5\u73ed\u6b21\u3002'
    )


def _build_attendance_text_summary(report_data: dict) -> str:
    return (
        f'{report_data.get("report_date", "")}\uff0c\u8003\u52e4\u7ed3\u679c {report_data.get("total_results", 0)} \u6761\uff0c'
        f'\u51fa\u52e4\u4eba\u6570 {report_data.get("attendance_count", 0)} \u4eba\uff0c'
        f'\u6b63\u5e38 {report_data.get("normal_count", 0)} \u4eba\uff0c'
        f'\u5f02\u5e38 {report_data.get("abnormal_count", 0)} \u4eba\u3002'
        f'\u5f02\u5e38\u5df2\u5904\u7406 {report_data.get("processed_exception_count", 0)} \u6761\uff0c'
        f'\u672a\u5904\u7406 {report_data.get("open_exception_count", 0)} \u6761\u3002'
    )


def _format_exception_counter(counter: dict[str, int]) -> str:
    if not counter:
        return '\u65e0'
    sorted_items = sorted(counter.items(), key=lambda item: item[1], reverse=True)
    return '\uff0c'.join(f'{name}:{count}' for name, count in sorted_items)


def _build_exception_text_summary(report_data: dict) -> str:
    att = report_data.get('attendance_exceptions', {})
    prod = report_data.get('production_exceptions', {})
    return (
        f'{report_data.get("report_date", "")}\uff0c'
        f'\u8003\u52e4\u5f02\u5e38\u5206\u5e03\uff1a{_format_exception_counter(att)}\u3002'
        f'\u751f\u4ea7\u5f02\u5e38\u5206\u5e03\uff1a{_format_exception_counter(prod)}\u3002'
    )


def _build_boss_text_summary(db: Session, *, report_date: date, scope: str) -> str:
    production = _generate_production_report(db, report_date=report_date, scope=scope)
    attendance = _generate_attendance_report(db, report_date=report_date)
    exception = _generate_exception_report(db, report_date=report_date)
    _ = exception

    workshop_output = production.get('workshop_output', {})
    top_workshops = sorted(workshop_output.items(), key=lambda item: item[1], reverse=True)[:3]
    workshop_text = '\uff0c'.join(f'{name}{value:.2f}\u5428' for name, value in top_workshops) or '\u6682\u65e0\u5206\u8f66\u95f4\u4ea7\u91cf'

    energy_rows = production.get('energy_rows', [])
    total_energy = production.get('total_energy', 0.0)
    energy_per_ton = production.get('energy_per_ton')
    energy_per_ton_text = f'{energy_per_ton:.2f}' if energy_per_ton is not None else '-'

    highest_output_workshop = top_workshops[0][0] if top_workshops else None
    workshop_name_by_code = {item.code: item.name for item in db.query(Workshop).all()}
    energy_per_ton_by_workshop = {}
    for row in energy_rows:
        code = row.get('workshop_code') or 'unknown'
        key = workshop_name_by_code.get(code, code)
        if row.get('energy_per_ton') is None:
            continue
        energy_per_ton_by_workshop[key] = row['energy_per_ton']
    high_energy_workshop = None
    if energy_per_ton_by_workshop:
        high_energy_workshop = max(energy_per_ton_by_workshop.items(), key=lambda item: item[1])[0]

    total_output = production.get('total_output_weight', 0.0)
    auto_confirmed_shifts = production.get('auto_confirmed_shifts', 0)
    pending_shifts = production.get('pending_or_unreported_shifts', 0)
    returned_shifts = production.get('returned_shifts', 0)
    attendance_total = attendance.get('attendance_count', 0)
    attendance_abnormal = attendance.get('abnormal_count', 0)
    production_ex = production.get('production_exception_count', 0)
    attendance_ex = production.get('attendance_exception_count', 0)
    downtime = production.get('downtime_minutes', 0)

    open_reconciliation = int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(DataReconciliationItem.business_date == report_date, DataReconciliationItem.status == 'open')
        .scalar()
        or 0
    )

    pending_note = (
        f'\u5f53\u524d\u4ecd\u6709 {open_reconciliation} \u9879\u5dee\u5f02\u5f85\u95ed\u73af\uff0c\u5efa\u8bae\u4f18\u5148\u5b8c\u6210\u5f02\u5e38\u5904\u7406\u540e\u518d\u56fa\u5316\u53e3\u5f84\u3002'
        if open_reconciliation
        else '\u5dee\u5f02\u5df2\u5168\u90e8\u95ed\u73af\uff0c\u53ef\u6309\u81ea\u52a8\u53e3\u5f84\u6301\u7eed\u8ddf\u8fdb\u3002'
    )
    judgement = '\u6574\u4f53\u751f\u4ea7\u8fd0\u884c\u7a33\u5b9a' if open_reconciliation == 0 and production_ex == 0 else '\u751f\u4ea7\u603b\u4f53\u53ef\u63a7\uff0c\u4f46\u9700\u5173\u6ce8\u5f02\u5e38\u53ca\u5dee\u5f02\u5904\u7406'

    return (
        f'{report_date.month}\u6708{report_date.day}\u65e5\uff0c\u5168\u5382\u603b\u4ea7\u51fa {total_output:.2f} \u5428\uff0c'
        f'Agent \u81ea\u52a8\u786e\u8ba4\u73ed\u6b21 {auto_confirmed_shifts} \u4e2a\uff0c'
        f'\u5f85\u8865\u62a5/\u672a\u95ed\u73af {pending_shifts} \u4e2a\uff0c\u5f02\u5e38\u9000\u56de {returned_shifts} \u4e2a\u3002'
        f'{workshop_text}\u3002'
        f'\u5168\u5382\u603b\u80fd\u8017 {total_energy:.2f}\uff0c\u5355\u5428\u80fd\u8017 {energy_per_ton_text}\u3002'
        f'\u4eca\u65e5\u51fa\u52e4\u603b\u4f53\u7a33\u5b9a\uff0c\u51fa\u52e4 {attendance_total} \u4eba\uff0c\u5f02\u5e38 {attendance_abnormal} \u4eba\u3002'
        f'\u751f\u4ea7\u5f02\u5e38 {production_ex} \u6761\uff0c\u8003\u52e4\u5f02\u5e38 {attendance_ex} \u6761\uff0c\u7d2f\u8ba1\u505c\u673a {downtime} \u5206\u949f\u3002'
        f'\u4ea7\u91cf\u6700\u9ad8\u8f66\u95f4\uff1a{highest_output_workshop or "-"}\uff0c\u80fd\u8017\u504f\u9ad8\u8f66\u95f4\uff1a{high_energy_workshop or "-"}\u3002'
        f'\u6570\u636e\u5dee\u5f02\u672a\u5904\u7406 {open_reconciliation} \u9879\u3002'
        f'{pending_note}\u7ecf\u8425\u5224\u65ad\uff1a{judgement}\u3002'
    )


def _build_canonical_workshop_output_summary(db: Session, *, target_date: date) -> list[dict]:
    workshop_map = _workshop_name_map(db)
    grouped: dict[int, dict] = {}
    for item in _query_shift_items(db, report_date=target_date, scope=CANONICAL_REPORT_SCOPE):
        payload = grouped.setdefault(
            item.workshop_id,
            {
                'workshop_id': item.workshop_id,
                'workshop_name': workshop_map.get(item.workshop_id, f'Workshop-{item.workshop_id}'),
                'total_output': 0.0,
                'shift_count': 0,
            },
        )
        payload['total_output'] += _to_float(item.output_weight)
        payload['shift_count'] += 1
    result = list(grouped.values())
    result.sort(key=lambda item: item['total_output'], reverse=True)
    return result


def _generate_report_payload(
    db: Session,
    *,
    report_date: date,
    report_type: str,
    scope: str,
) -> tuple[dict, str]:
    if report_type == 'production':
        report_data = _generate_production_report(db, report_date=report_date, scope=scope)
        text_summary = _build_production_text_summary(report_data)
    elif report_type == 'attendance':
        report_data = _generate_attendance_report(db, report_date=report_date)
        text_summary = _build_attendance_text_summary(report_data)
    elif report_type == 'exception':
        report_data = _generate_exception_report(db, report_date=report_date)
        text_summary = _build_exception_text_summary(report_data)
    else:
        raise ValueError(f'unsupported report_type: {report_type}')
    return report_data, text_summary


def _apply_output_mode(
    *,
    report_data: dict,
    text_summary: str,
    output_mode: str,
) -> tuple[dict | None, str | None]:
    if output_mode == 'json':
        return report_data, None
    if output_mode == 'text':
        return None, text_summary
    return report_data, text_summary


def generate_daily_reports(
    db: Session,
    *,
    report_date: date,
    report_type: str | None,
    scope: str,
    output_mode: str,
    operator: User,
) -> list[DailyReport]:
    if scope not in VALID_SCOPES:
        raise ValueError('scope must be auto_confirmed, confirmed_only or include_reviewed')
    if output_mode not in VALID_OUTPUT_MODES:
        raise ValueError('output_mode must be json, text or both')
    canonical_scope = _normalize_scope(scope)

    report_types = [report_type] if report_type else list(VALID_REPORT_TYPES)
    for item in report_types:
        if item not in VALID_REPORT_TYPES:
            raise ValueError(f'unsupported report_type: {item}')

    now = datetime.now(timezone.utc)
    entities: list[DailyReport] = []
    for current_type in report_types:
        report_data, text_summary = _generate_report_payload(
            db,
            report_date=report_date,
            report_type=current_type,
            scope=canonical_scope,
        )
        payload_data, payload_text = _apply_output_mode(
            report_data=report_data,
            text_summary=text_summary,
            output_mode=output_mode,
        )

        entity = (
            db.query(DailyReport)
            .filter(DailyReport.report_date == report_date, DailyReport.report_type == current_type)
            .first()
        )
        if entity is None:
            entity = DailyReport(
                report_date=report_date,
                report_type=current_type,
                report_data=payload_data,
                text_summary=payload_text,
                status='draft',
                generated_scope=canonical_scope,
                output_mode=output_mode,
                generated_at=now,
            )
            db.add(entity)
        else:
            entity.report_data = payload_data
            entity.text_summary = payload_text
            entity.status = 'draft'
            entity.generated_scope = canonical_scope
            entity.output_mode = output_mode
            entity.generated_at = now
            entity.reviewed_by = None
            entity.reviewed_at = None
            entity.published_by = None
            entity.published_at = None
        db.flush()
        entities.append(entity)

        record_audit(
            db,
            user=operator,
            action='generate_report',
            module='reports',
            entity_type='daily_reports',
            entity_id=entity.id,
            detail={
                'report_date': report_date.isoformat(),
                'report_type': current_type,
                'scope': canonical_scope,
                'requested_scope': scope,
                'output_mode': output_mode,
            },
            auto_commit=False,
        )

    db.commit()
    for item in entities:
        db.refresh(item)
    return entities


def review_report(
    db: Session,
    *,
    report_id: int,
    operator: User,
    note: str | None = None,
) -> DailyReport:
    entity = db.get(DailyReport, report_id)
    if entity is None:
        raise ValueError('report not found')
    if entity.status == 'published':
        raise ValueError('published report cannot be reviewed')

    entity.status = 'reviewed'
    entity.reviewed_by = operator.id
    entity.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    record_audit(
        db,
        user=operator,
        action='review_report',
        module='reports',
        entity_type='daily_reports',
        entity_id=entity.id,
        detail={
            'report_date': entity.report_date.isoformat(),
            'report_type': entity.report_type,
            'note': note,
        },
        reason=note,
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    event_bus.publish(
        'report_reviewed',
        _build_report_event_payload(
            db,
            event_type='report_reviewed',
            entity=entity,
            operator=operator,
            note=note,
        ),
    )
    return entity


def run_daily_pipeline(
    db: Session,
    *,
    report_date: date,
    scope: str,
    output_mode: str,
    force: bool,
    operator: User,
) -> tuple[bool, str | None, int, bool, str | None, list[DailyReport]]:
    from app.services import reconciliation_service
    canonical_scope = _normalize_scope(scope)
    open_blockers = quality_service.count_open_blockers(db, business_date=report_date)
    if open_blockers > 0 and not force:
        return (
            True,
            f'存在 {open_blockers} 条质量阻断问题，请先处理后再生成日报',
            0,
            False,
            None,
            [],
        )
    open_reconciliation = reconciliation_service.count_open_items(db, business_date=report_date)
    if open_reconciliation > 0 and not force:
        return True, f'\u5b58\u5728 {open_reconciliation} \u6761\u672a\u5904\u7406\u5dee\u5f02\uff0c\u8bf7\u5148\u5b8c\u6210\u6838\u5bf9', open_reconciliation, False, None, []

    reports = generate_daily_reports(
        db,
        report_date=report_date,
        report_type=None,
        scope=canonical_scope,
        output_mode=output_mode,
        operator=operator,
    )
    boss_summary = _build_boss_text_summary(db, report_date=report_date, scope=canonical_scope)
    is_final_version = open_reconciliation == 0 and open_blockers == 0
    quality_status = 'passed' if open_blockers == 0 else 'blocked'
    quality_summary = quality_service.blocker_summary(db, business_date=report_date)
    delivery_status = build_delivery_status(db, target_date=report_date)
    for item in reports:
        if item.report_type == 'production':
            item.final_text_summary = boss_summary
            item.is_final_version = is_final_version
        item.quality_gate_status = quality_status
        item.quality_gate_summary = quality_summary
        item.delivery_ready = delivery_status.get('delivery_ready', False)
    db.flush()
    record_audit(
        db,
        user=operator,
        action='run_daily_pipeline',
        module='reports',
        entity_type='daily_reports',
        entity_id=reports[0].id if reports else None,
        detail={
            'report_date': report_date.isoformat(),
            'scope': canonical_scope,
            'requested_scope': scope,
            'output_mode': output_mode,
            'open_reconciliation': open_reconciliation,
            'is_final_version': is_final_version,
            'quality_gate_status': quality_status,
            'force': force,
        },
        auto_commit=False,
    )
    db.commit()
    for item in reports:
        db.refresh(item)
    return False, None, open_reconciliation, is_final_version, boss_summary, reports


def finalize_report(
    db: Session,
    *,
    report_id: int,
    operator: User,
    note: str | None = None,
    force: bool = False,
) -> DailyReport:
    entity = db.get(DailyReport, report_id)
    if entity is None:
        raise ValueError('report not found')
    if entity.status not in {'reviewed', 'published'}:
        raise ValueError('only reviewed or published report can be finalized')

    blocker_count = quality_service.count_open_blockers(db, business_date=entity.report_date)
    if blocker_count > 0:
        if not force:
            raise ValueError(f'存在 {blocker_count} 条质量阻断问题，禁止最终发布')
        if operator.role != 'admin':
            raise ValueError('only admin can force finalize when blockers exist')

    entity.final_confirmed_by = operator.id
    entity.final_confirmed_at = datetime.now(timezone.utc)
    entity.is_final_version = True
    if not entity.final_text_summary:
        entity.final_text_summary = entity.text_summary
    entity.quality_gate_status = 'passed' if blocker_count == 0 else 'blocked'
    entity.quality_gate_summary = quality_service.blocker_summary(db, business_date=entity.report_date)
    delivery_status = build_delivery_status(db, target_date=entity.report_date)
    entity.delivery_ready = delivery_status.get('delivery_ready', False)

    db.flush()
    record_audit(
        db,
        user=operator,
        action='finalize_report',
        module='reports',
        entity_type='daily_reports',
        entity_id=entity.id,
        detail={
            'report_date': entity.report_date.isoformat(),
            'report_type': entity.report_type,
            'note': note,
            'force': force,
            'blocker_count': blocker_count,
        },
        reason=note,
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    return entity


def publish_report(
    db: Session,
    *,
    report_id: int,
    operator: User,
    note: str | None = None,
) -> DailyReport:
    entity = db.get(DailyReport, report_id)
    if entity is None:
        raise ValueError('report not found')
    if entity.status == 'draft':
        raise ValueError('draft report must be reviewed before publish')

    entity.status = 'published'
    entity.published_by = operator.id
    entity.published_at = datetime.now(timezone.utc)

    published_shift_count = 0
    if entity.report_type == 'production':
        publish_scope = 'confirmed_only' if entity.generated_scope == CANONICAL_REPORT_SCOPE else entity.generated_scope
        published_shift_count = mark_shift_data_published(
            db,
            target_date=entity.report_date,
            scope=publish_scope,
            operator=operator,
        )
        report_data = dict(entity.report_data or {})
        report_data['delivery_resolution'] = resolve_report_delivery_payload(db, entity=entity)
        entity.report_data = report_data

    db.flush()
    record_audit(
        db,
        user=operator,
        action='publish_report',
        module='reports',
        entity_type='daily_reports',
        entity_id=entity.id,
        detail={
            'report_date': entity.report_date.isoformat(),
            'report_type': entity.report_type,
            'scope': entity.generated_scope,
            'published_shift_count': published_shift_count,
            'note': note,
        },
        reason=note,
        auto_commit=False,
    )
    db.commit()
    db.refresh(entity)
    event_bus.publish(
        'report_published',
        _build_report_event_payload(
            db,
            event_type='report_published',
            entity=entity,
            operator=operator,
            note=note,
            published_shift_count=published_shift_count,
        ),
    )
    return entity


def list_reports(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    report_type: str | None = None,
    status: str | None = None,
) -> list[DailyReport]:
    query = db.query(DailyReport)
    if start_date:
        query = query.filter(DailyReport.report_date >= start_date)
    if end_date:
        query = query.filter(DailyReport.report_date <= end_date)
    if report_type:
        query = query.filter(DailyReport.report_type == report_type)
    if status:
        query = query.filter(DailyReport.status == status)
    return query.order_by(DailyReport.report_date.desc(), DailyReport.id.desc()).all()


def get_report(db: Session, *, report_id: int) -> DailyReport | None:
    return db.get(DailyReport, report_id)


def _count_reports_by_status(db: Session, *, target_date: date, status: str) -> int:
    return int(
        db.query(func.count(DailyReport.id))
        .filter(
            DailyReport.report_date == target_date,
            DailyReport.status == status,
        )
        .scalar()
        or 0
    )


def build_delivery_status(db: Session, *, target_date: date) -> dict:
    completed_batches = (
        db.query(ImportBatch)
        .filter(func.date(ImportBatch.created_at) == target_date)
        .filter(ImportBatch.status.in_(['completed', 'partial_success']))
        .all()
    )
    completed_types = {item.import_type for item in completed_batches}
    required_import_types = REQUIRED_IMPORT_TYPES + ('contract_report',)
    missing_imports = [item for item in required_import_types if item not in completed_types]
    imports_completed = len(missing_imports) == 0

    reconciliation_open_count = int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(DataReconciliationItem.business_date == target_date, DataReconciliationItem.status == 'open')
        .scalar()
        or 0
    )
    quality_open_count = quality_service.count_open_issues(db, business_date=target_date)
    blocker_count = quality_service.count_open_blockers(db, business_date=target_date)

    reports_generated = int(
        db.query(func.count(DailyReport.id))
        .filter(DailyReport.report_date == target_date)
        .scalar()
        or 0
    )
    reports_reviewed_count = _count_reports_by_status(db, target_date=target_date, status='reviewed')
    reports_published_count = _count_reports_by_status(db, target_date=target_date, status='published')
    reports_ready_count = reports_reviewed_count + reports_published_count

    delivery_ready = (
        imports_completed
        and blocker_count == 0
        and reconciliation_open_count == 0
        and reports_generated > 0
        and reports_ready_count > 0
    )

    missing_steps: list[str] = []
    if missing_imports:
        missing_steps.append(f"imports_missing:{','.join(missing_imports)}")
    if reconciliation_open_count > 0:
        missing_steps.append('reconciliation_open')
    if blocker_count > 0:
        missing_steps.append('quality_blocker')
    if reports_generated == 0:
        missing_steps.append('reports_not_generated')
    if reports_ready_count == 0:
        missing_steps.append('reports_not_reviewed')

    return {
        'target_date': target_date.isoformat(),
        'imports_completed': imports_completed,
        'reconciliation_open_count': reconciliation_open_count,
        'quality_open_count': quality_open_count,
        'blocker_count': blocker_count,
        'reports_generated': reports_generated,
        'reports_reviewed_count': reports_reviewed_count,
        'reports_published_count': reports_published_count,
        'reports_published': reports_ready_count,
        'reports_published_deprecated': True,
        'delivery_ready': delivery_ready,
        'missing_steps': missing_steps,
    }


def _month_to_date_output(db: Session, *, target_date: date, workshop_id: int | None = None) -> float:
    month_start = target_date.replace(day=1)
    query = db.query(func.sum(ShiftProductionData.output_weight)).filter(
        ShiftProductionData.business_date >= month_start,
        ShiftProductionData.business_date <= target_date,
        ShiftProductionData.data_status != 'voided',
    )
    if workshop_id:
        query = query.filter(ShiftProductionData.workshop_id == workshop_id)
    return _to_float(query.scalar())


def _output_totals_by_date(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    workshop_id: int | None = None,
) -> dict[date, float]:
    query = (
        db.query(ShiftProductionData.business_date, func.sum(ShiftProductionData.output_weight))
        .filter(
            ShiftProductionData.business_date >= start_date,
            ShiftProductionData.business_date <= end_date,
            ShiftProductionData.data_status != 'voided',
        )
        .group_by(ShiftProductionData.business_date)
    )
    if workshop_id:
        query = query.filter(ShiftProductionData.workshop_id == workshop_id)
    return {business_date: round(_to_float(total_output), 2) for business_date, total_output in query.all()}


def _active_output_dates(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    workshop_id: int | None = None,
) -> list[date]:
    query = (
        db.query(ShiftProductionData.business_date)
        .filter(
            ShiftProductionData.business_date >= start_date,
            ShiftProductionData.business_date <= end_date,
            ShiftProductionData.data_status != 'voided',
        )
        .distinct()
    )
    if workshop_id:
        query = query.filter(ShiftProductionData.workshop_id == workshop_id)
    return sorted(row[0] for row in query.all() if row and row[0] is not None)


def _build_history_digest(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None = None,
    window_days: int = 7,
) -> dict[str, Any]:
    window_start = target_date - timedelta(days=max(window_days - 1, 0))
    output_by_date = _output_totals_by_date(db, start_date=window_start, end_date=target_date, workshop_id=workshop_id)
    daily_snapshots: list[dict[str, Any]] = []

    for day_offset in range(window_days):
        business_date = window_start + timedelta(days=day_offset)
        inventory_lane = mobile_report_service.summarize_mobile_inventory(
            db,
            target_date=business_date,
            workshop_id=workshop_id,
        )
        contract_lane = build_contract_projection(db, target_date=business_date)
        energy_summary = _safe_energy_summary_for_date(db, target_date=business_date)
        daily_snapshots.append(
            {
                'date': business_date.isoformat(),
                'label': business_date.strftime('%m-%d'),
                'output_weight': round(output_by_date.get(business_date, 0.0), 2),
                'storage_finished_weight': round(
                    sum(_to_float(item.get('storage_finished')) for item in inventory_lane),
                    2,
                ),
                'shipment_weight': round(sum(_to_float(item.get('shipment_weight')) for item in inventory_lane), 2),
                'storage_inbound_area': round(sum(_to_float(item.get('storage_inbound_area')) for item in inventory_lane), 2),
                'contract_weight': round(_to_float(contract_lane.get('daily_contract_weight')), 2),
                'energy_per_ton': round(_to_float(energy_summary.get('energy_per_ton')), 2)
                if energy_summary.get('energy_per_ton') is not None
                else None,
            }
        )

    month_start = target_date.replace(day=1)
    month_output = _month_to_date_output(db, target_date=target_date, workshop_id=workshop_id)
    month_active_dates = _active_output_dates(db, start_date=month_start, end_date=target_date, workshop_id=workshop_id)
    year_start = target_date.replace(month=1, day=1)
    year_output = round(sum(_output_totals_by_date(db, start_date=year_start, end_date=target_date, workshop_id=workshop_id).values()), 2)
    year_active_dates = _active_output_dates(db, start_date=year_start, end_date=target_date, workshop_id=workshop_id)
    active_months = len({(item.year, item.month) for item in year_active_dates})

    return {
        'daily_snapshots': daily_snapshots,
        'month_archive': {
            'total_output': round(month_output, 2),
            'reported_days': len(month_active_dates),
            'average_daily_output': round(month_output / len(month_active_dates), 2) if month_active_dates else 0.0,
            'calendar_day': target_date.day,
        },
        'year_archive': {
            'total_output': round(year_output, 2),
            'reported_days': len(year_active_dates),
            'active_months': active_months,
            'average_monthly_output': round(year_output / active_months, 2) if active_months else 0.0,
        },
    }


def _build_factory_boss_summary(
    *,
    target_date: date,
    total_output: float,
    monthly_output: float,
    total_energy: float,
    energy_per_ton: float | None,
    mobile_summary: dict,
    exception_total: int,
    blocker_summary: dict[str, Any] | None,
) -> str:
    reporting_rate_text = f"{mobile_summary.get('reporting_rate', 0):.0f}%"
    energy_text = f'{energy_per_ton:.2f}' if energy_per_ton is not None else '-'
    focus_items: list[str] = []
    if mobile_summary.get('unreported_count', 0) > 0:
        focus_items.append(f"未报班次 {mobile_summary['unreported_count']} 个")
    if mobile_summary.get('returned_count', 0) > 0:
        focus_items.append(f"退回班次 {mobile_summary['returned_count']} 个")
    if exception_total > 0:
        focus_items.append(f"异常班次 {exception_total} 个")
    blocker_digest = str((blocker_summary or {}).get('digest') or '').strip()
    if blocker_digest and (blocker_summary or {}).get('has_blockers'):
        focus_items.append(blocker_digest)
    focus_text = '；'.join(focus_items) if focus_items else '建议关注未闭环班次与单吨能耗波动。'
    return (
        f"{target_date.month}月{target_date.day}日，全厂今日产量 {total_output:.2f} 吨，"
        f"月累计 {monthly_output:.2f} 吨，上报率 {reporting_rate_text}。"
        f"今日能耗 {total_energy:.2f}，单吨电耗 {energy_text}。"
        f"移动填报异常 {exception_total} 个，建议关注：{focus_text}"
    )


def _build_factory_leader_metrics(
    *,
    total_output: float,
    energy_per_ton: float | None,
    inventory_lane: list[dict[str, Any]],
    contract_lane: dict[str, Any],
    latest_report: DailyReport | None,
    management_estimate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_data = dict(latest_report.report_data or {}) if latest_report and isinstance(latest_report.report_data, dict) else {}
    yield_matrix_lane = dict(report_data.get('yield_matrix_lane') or {})
    yield_rate = (
        yield_matrix_lane.get('company_total_yield')
        if yield_matrix_lane.get('quality_status') == 'ready'
        else report_data.get('yield_rate')
    )
    return {
        'today_total_output': round(total_output, 2),
        'energy_per_ton': round(_to_float(energy_per_ton), 2) if energy_per_ton is not None else None,
        'in_process_weight': round(sum(_to_float(item.get('storage_prepared')) for item in inventory_lane), 2),
        'storage_finished_weight': round(sum(_to_float(item.get('storage_finished')) for item in inventory_lane), 2),
        'shipment_weight': round(sum(_to_float(item.get('shipment_weight')) for item in inventory_lane), 2),
        'storage_inbound_area': round(sum(_to_float(item.get('storage_inbound_area')) for item in inventory_lane), 2),
        'contract_weight': round(_to_float(contract_lane.get('daily_contract_weight')), 2),
        'yield_rate': round(_to_float(yield_rate), 2) if yield_rate is not None else None,
        'total_attendance': int(report_data.get('total_attendance') or 0),
        'estimated_revenue': management_estimate.get('estimated_revenue') if management_estimate else None,
        'estimated_cost': management_estimate.get('estimated_cost') if management_estimate else None,
        'estimated_margin': management_estimate.get('estimated_margin') if management_estimate else None,
        'active_contract_count': management_estimate.get('active_contract_count') if management_estimate else 0,
        'stalled_contract_count': management_estimate.get('stalled_contract_count') if management_estimate else 0,
        'active_coil_count': management_estimate.get('active_coil_count') if management_estimate else 0,
        'sync_lag_seconds': management_estimate.get('sync_lag_seconds') if management_estimate else None,
    }


def _build_dashboard_leader_summary(
    *,
    target_date: date,
    latest_report: DailyReport | None,
    total_output: float,
    energy_summary: dict[str, Any],
    mobile_summary: dict[str, Any],
    contract_lane: dict[str, Any],
    inventory_lane: list[dict[str, Any]],
    exception_lane: dict[str, Any],
    blocker_summary: dict[str, Any] | None,
    yield_matrix_lane: dict[str, Any] | None,
) -> dict[str, Any]:
    report_data = {
        'total_output_weight': total_output,
        'total_energy': energy_summary.get('total_energy'),
        'energy_per_ton': energy_summary.get('energy_per_ton'),
        'reporting_rate': mobile_summary.get('reporting_rate'),
        'total_attendance': int((latest_report.report_data or {}).get('total_attendance') or 0)
        if latest_report and isinstance(latest_report.report_data, dict)
        else 0,
        'contract_lane': contract_lane,
        'yield_matrix_lane': dict(yield_matrix_lane or {}),
        'anomaly_summary': {
            'total': int(exception_lane.get('mobile_exception_count') or 0) + int(exception_lane.get('production_exception_count') or 0),
            'digest': blocker_summary.get('digest') if isinstance(blocker_summary, dict) else '未发现关键异常',
        },
        'inventory_lane': inventory_lane,
    }
    current_metrics = leader_summary_service.build_leader_summary_metrics(report_date=target_date, report_data=report_data)
    stored_summary = (
        dict(latest_report.report_data.get('leader_summary') or {})
        if latest_report and isinstance(latest_report.report_data, dict)
        else {}
    )
    if (
        stored_summary.get('summary_source') == 'llm'
        and stored_summary.get('summary_text')
        and stored_summary.get('metrics') == current_metrics
    ):
        return stored_summary

    return {
        'summary_text': leader_summary_service.build_deterministic_leader_summary(metrics=current_metrics),
        'summary_source': 'deterministic',
        'metrics': current_metrics,
    }


def _build_production_lane(db: Session, *, target_date: date, workshop_id: int | None = None) -> list[dict]:
    items = build_workshop_output_summary(db, target_date=target_date, status_scope='include_pending')
    if workshop_id:
        items = [item for item in items if item['workshop_id'] == workshop_id]

    yesterday = target_date - timedelta(days=1)
    yesterday_items = build_workshop_output_summary(db, target_date=yesterday, status_scope='include_pending')
    yesterday_map = {item['workshop_id']: item['total_output'] for item in yesterday_items}

    lane = []
    for item in items:
        compare_value = yesterday_map.get(item['workshop_id'])
        lane.append(
            {
                **item,
                'source': 'mobile',
                'source_label': '主操直录',
                'source_variant': 'mobile',
                'target_value': None,
                'compare_value': compare_value,
                'delta_vs_yesterday': None if compare_value is None else round(item['total_output'] - compare_value, 2),
            }
        )
    return lane


def _build_energy_lane(db: Session, *, target_date: date, workshop_id: int | None = None) -> list[dict]:
    energy_rows = energy_service.get_energy_summary(db, business_date=target_date, workshop_id=workshop_id)
    return [
        {
            **row,
            **_lane_source_meta(row.get('source')),
            'is_over_line': bool(row.get('energy_per_ton') and row['energy_per_ton'] > 4),
        }
        for row in energy_rows
    ]


def _lane_source_meta(source: str | None) -> dict[str, str]:
    normalized = str(source or 'import').lower()
    if normalized == 'owner_only':
        return {
            'source': 'owner_only',
            'source_label': '专项补录',
            'source_variant': 'owner',
        }
    if normalized == 'mobile':
        return {
            'source': 'mobile',
            'source_label': '主操直录',
            'source_variant': 'mobile',
        }
    return {
        'source': 'import',
        'source_label': '系统导入',
        'source_variant': 'import',
    }


def _build_exception_lane(db: Session, *, target_date: date, workshop_id: int | None = None) -> dict:
    mobile_summary = mobile_report_service.summarize_mobile_reporting(db, target_date=target_date, workshop_id=workshop_id)
    reminder_summary = mobile_reminder_service.summarize_reminders(db, target_date=target_date, workshop_id=workshop_id)
    open_reconciliation = int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(DataReconciliationItem.business_date == target_date, DataReconciliationItem.status == 'open')
        .scalar()
        or 0
    )
    unpublished_reports = int(
        db.query(func.count(DailyReport.id))
        .filter(DailyReport.report_date == target_date, DailyReport.status != 'published')
        .scalar()
        or 0
    )
    if workshop_id:
        unpublished_reports = 0
    return {
        'unreported_shift_count': mobile_summary.get('unreported_count', 0),
        'returned_shift_count': mobile_summary.get('returned_count', 0),
        'late_shift_count': mobile_summary.get('late_count', 0),
        'mobile_exception_count': mobile_summary.get('exception_count', 0),
        'reminder_unreported_count': reminder_summary.get('unreported_count', 0),
        'reminder_late_count': reminder_summary.get('late_report_count', 0),
        'today_reminder_count': reminder_summary.get('today_reminder_count', 0),
        'production_exception_count': mobile_report_service.count_linked_open_production_exceptions(
            db,
            target_date=target_date,
            workshop_id=workshop_id,
        ),
        'reconciliation_open_count': open_reconciliation,
        'pending_report_publish_count': unpublished_reports,
        'returned_items': mobile_summary.get('returned_items', []),
        'reminder_items': reminder_summary.get('recent_items', []),
        'recent_items': mobile_report_service.recent_mobile_exceptions(
            db,
            target_date=target_date,
            workshop_id=workshop_id,
        ),
    }


def _build_runtime_source_lanes(
    *,
    surface: str,
    history_digest: dict[str, Any] | None,
    energy_lane: list[dict[str, Any]] | None,
    inventory_lane: list[dict[str, Any]] | None,
    contract_lane: dict[str, Any] | None,
    exception_lane: dict[str, Any] | None,
    mobile_summary: dict[str, Any] | None,
    delivery_status: dict[str, Any] | None,
    orchestration: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    history_digest = history_digest or {}
    energy_lane = energy_lane or []
    inventory_lane = inventory_lane or []
    contract_lane = contract_lane or {}
    exception_lane = exception_lane or {}
    mobile_summary = mobile_summary or {}
    delivery_status = delivery_status or {}
    orchestration = orchestration or build_runtime_orchestration_snapshot(
        mobile_summary=mobile_summary,
        exception_lane=exception_lane,
        delivery_status=delivery_status,
        reminder_summary=None,
    )
    result_target_map = {
        'factory': {
            'algorithm_pipeline': ['今日产量', '今日上报状态', '单吨能耗'],
            'analysis_agent': ['今日摘要', '今日关注', '近 7 日留存趋势'],
            'execution_agent': ['交付与闭环', '数据留存与归档'],
        },
        'workshop': {
            'algorithm_pipeline': ['今日产量', '生产泳道'],
            'analysis_agent': ['异常与提醒泳道', '上报率'],
            'execution_agent': ['待处理班次', '交付缺口'],
        },
    }
    targets = result_target_map['workshop' if surface == 'workshop' else 'factory']
    expected_count = int(mobile_summary.get('expected_count') or 0)
    reported_count = int(mobile_summary.get('reported_count') or 0)
    reporting_rate = float(mobile_summary.get('reporting_rate') or 0.0)
    returned_count = int(mobile_summary.get('returned_count') or 0)
    unreported_count = int(mobile_summary.get('unreported_count') or 0)
    late_count = int(mobile_summary.get('late_count') or 0)
    auto_confirmed_count = int(mobile_summary.get('auto_confirmed_count') or 0)
    history_points = len(history_digest.get('daily_snapshots') or [])
    reconciliation_open_count = int(exception_lane.get('reconciliation_open_count') or 0)
    exception_count = int(exception_lane.get('mobile_exception_count') or 0) + int(
        exception_lane.get('production_exception_count') or 0
    )
    reports_ready_count = int(
        delivery_status.get('reports_ready_count')
        or delivery_status.get('reports_published')
        or (
            int(delivery_status.get('reports_reviewed_count') or 0)
            + int(delivery_status.get('reports_published_count') or 0)
        )
    )
    workers = {item.get('key'): item for item in (orchestration.get('workers') or [])}
    algorithm_worker = workers.get('algorithm_pipeline', {})
    analysis_worker = workers.get('analysis_agent', {})
    execution_worker = workers.get('execution_agent', {})
    reliability_score = float(orchestration.get('reliability_score') or 0.0)
    blocking_count = int(orchestration.get('blocking_count') or 0)
    bottlenecks = [str(item) for item in (orchestration.get('bottlenecks') or []) if item]
    execution_stage_detail = (
        '、'.join(bottlenecks[:2])
        if bottlenecks
        else '交付链路可持续运行'
    )
    return [
        {
            'key': 'algorithm_pipeline',
            'label': '算法流水线',
            'actor_label': '规则引擎',
            'detail': (
                f'上报率 {reporting_rate:.2f}%'
                if expected_count > 0
                else '暂无应报清单'
            ),
            'stage_label': '确定性规则',
            'stage_detail': f'{reported_count}/{expected_count} 班次到位，自动确认 {auto_confirmed_count} 条',
            'result_label': '原始值标准化 / 自动校验',
            'result_targets': targets['algorithm_pipeline'],
            'status': algorithm_worker.get('status') or 'healthy',
        },
        {
            'key': 'analysis_agent',
            'label': '分析决策助手',
            'actor_label': 'AI 推理',
            'detail': f'异常 {exception_count} 条，差异 {reconciliation_open_count} 条',
            'stage_label': '解释与建议',
            'stage_detail': f'可靠度 {reliability_score:.1f}，风险阻塞 {blocking_count} 项',
            'result_label': '异常归因 / 处理优先级',
            'result_targets': targets['analysis_agent'],
            'status': analysis_worker.get('status') or 'healthy',
        },
        {
            'key': 'execution_agent',
            'label': '执行交付助手',
            'actor_label': '交付编排',
            'detail': f'{reports_ready_count} 份可交付，留存 {history_points} 天',
            'stage_label': '闭环执行',
            'stage_detail': execution_stage_detail,
            'result_label': '日报发布 / 交付闭环',
            'result_targets': targets['execution_agent'],
            'status': execution_worker.get('status') or 'healthy',
        },
    ]


def _build_runtime_trace(
    *,
    surface: str = 'factory',
    history_digest: dict[str, Any] | None,
    energy_lane: list[dict[str, Any]] | None,
    inventory_lane: list[dict[str, Any]] | None,
    contract_lane: dict[str, Any] | None,
    exception_lane: dict[str, Any] | None,
    mobile_summary: dict[str, Any] | None,
    reminder_summary: dict[str, Any] | None,
    delivery_status: dict[str, Any] | None,
    sync_status: dict[str, Any] | None,
) -> dict[str, Any]:
    history_digest = history_digest or {}
    energy_lane = energy_lane or []
    exception_lane = exception_lane or {}
    mobile_summary = mobile_summary or {}
    reminder_summary = reminder_summary or {}
    delivery_status = delivery_status or {}
    sync_status = sync_status or {}

    orchestration = build_runtime_orchestration_snapshot(
        mobile_summary=mobile_summary,
        exception_lane=exception_lane,
        delivery_status=delivery_status,
        reminder_summary=reminder_summary,
    )
    worker_index = {
        item.get('key'): item
        for item in (orchestration.get('workers') or [])
        if isinstance(item, dict)
    }

    expected_count = int(mobile_summary.get('expected_count') or 0)
    reported_count = int(mobile_summary.get('reported_count') or 0)
    auto_confirmed_count = int(mobile_summary.get('auto_confirmed_count') or 0)
    returned_count = int(mobile_summary.get('returned_count') or 0)
    unreported_count = int(mobile_summary.get('unreported_count') or 0)
    late_count = int(mobile_summary.get('late_count') or 0)
    reminder_count = int(reminder_summary.get('today_reminder_count') or 0)
    reporting_rate = float(mobile_summary.get('reporting_rate') or 0.0)

    reconciliation_open_count = int(exception_lane.get('reconciliation_open_count') or 0)
    exception_count = int(exception_lane.get('mobile_exception_count') or 0) + int(
        exception_lane.get('production_exception_count') or 0
    )
    mes_last_run_status = sync_status.get('last_run_status')
    reports_generated = int(delivery_status.get('reports_generated') or 0)
    reports_published_count = int(delivery_status.get('reports_published_count') or 0)
    reports_ready_count = int(
        delivery_status.get('reports_ready_count')
        or delivery_status.get('reports_published')
        or (
            int(delivery_status.get('reports_reviewed_count') or 0)
            + reports_published_count
        )
    )
    missing_steps = list(delivery_status.get('missing_steps') or [])
    delivery_ready = bool(delivery_status.get('delivery_ready'))
    algorithm_status = str(worker_index.get('algorithm_pipeline', {}).get('status') or 'healthy')
    analysis_status = str(worker_index.get('analysis_agent', {}).get('status') or 'healthy')
    execution_status = str(worker_index.get('execution_agent', {}).get('status') or 'healthy')

    return {
        'source_lanes': _build_runtime_source_lanes(
            surface=surface,
            history_digest=history_digest,
            energy_lane=energy_lane,
            inventory_lane=inventory_lane,
            contract_lane=contract_lane,
            exception_lane=exception_lane,
            mobile_summary=mobile_summary,
            delivery_status=delivery_status,
            orchestration=orchestration,
        ),
        'frontline': {
            'status': algorithm_status,
            'expected_count': expected_count,
            'reported_count': reported_count,
            'auto_confirmed_count': auto_confirmed_count,
            'returned_count': returned_count,
            'unreported_count': unreported_count,
            'late_count': late_count,
            'reminder_count': reminder_count,
            'reporting_rate': round(reporting_rate, 2),
        },
        'backline': {
            'status': analysis_status,
            'history_points': len(history_digest.get('daily_snapshots') or []),
            'energy_row_count': len(energy_lane),
            'exception_count': exception_count,
            'reconciliation_open_count': reconciliation_open_count,
            'mes_last_run_status': mes_last_run_status,
        },
        'delivery': {
            'status': execution_status,
            'delivery_ready': delivery_ready,
            'reports_generated': reports_generated,
            'reports_ready_count': reports_ready_count,
            'reports_published_count': reports_published_count,
            'missing_steps': missing_steps,
        },
        'orchestration': orchestration,
    }


_REPORT_STATUS_PRIORITY = {
    'unreported': 0,
    'returned': 1,
    'draft': 2,
    'submitted': 3,
    CANONICAL_REPORT_SCOPE: 4,
    'approved': 4,
}


def _workshop_reporting_meta(report_status: str) -> dict[str, str]:
    hint_map = {
        'submitted': '主操已提交，等待系统自动收口',
        'reviewed': '系统已接住本班数据，正在进入汇总',
        'auto_confirmed': '主操直录已稳定，系统已自动归档',
        'returned': '已退回主操补录，暂未进入汇总',
        'draft': '主操正在填写，结果卡暂未更新',
        'unreported': '主操待补，系统暂未看到本班原始值',
        'late': '主操已迟报，本班结果可能滞后',
    }
    return {
        'source_label': '主操直录',
        'source_variant': 'mobile',
        'status_hint': hint_map.get(report_status, '系统正在同步当前班次状态'),
    }


def _build_workshop_reporting_status(db: Session, target_date: date) -> list[dict]:
    workshops = (
        db.query(Workshop)
        .filter(Workshop.is_active.is_(True), Workshop.workshop_type.isnot(None))
        .order_by(Workshop.sort_order.asc(), Workshop.id.asc())
        .all()
    )
    expected_rows = (
        db.query(AttendanceSchedule.workshop_id, AttendanceSchedule.team_id, AttendanceSchedule.shift_config_id)
        .filter(
            AttendanceSchedule.business_date == target_date,
            AttendanceSchedule.workshop_id.is_not(None),
            AttendanceSchedule.shift_config_id.is_not(None),
            AttendanceSchedule.is_rest_day.is_(False),
        )
        .distinct()
        .all()
    )
    expected_by_workshop: dict[int, set[tuple[int | None, int]]] = {}
    for row in expected_rows:
        expected_by_workshop.setdefault(int(row.workshop_id), set()).add((row.team_id, int(row.shift_config_id)))

    report_rows = (
        db.query(MobileShiftReport)
        .filter(MobileShiftReport.business_date == target_date)
        .all()
    )
    reports_by_workshop: dict[int, list[MobileShiftReport]] = {}
    report_key_status: dict[tuple[int, int | None, int], str] = {}
    for row in report_rows:
        reports_by_workshop.setdefault(int(row.workshop_id), []).append(row)
        report_key_status[(int(row.workshop_id), row.team_id, int(row.shift_config_id))] = _mobile_report_decision_status(row)

    merged: list[dict] = []
    for workshop in workshops:
        wid = int(workshop.id)
        workshop_reports = reports_by_workshop.get(wid, [])
        expected_keys = expected_by_workshop.get(wid, set())
        statuses = [_mobile_report_decision_status(row) for row in workshop_reports]
        if expected_keys:
            for key in expected_keys:
                if (wid, key[0], key[1]) not in report_key_status:
                    statuses.append('unreported')
        if not statuses:
            statuses.append('unreported')
        report_status = min(statuses, key=lambda item: _REPORT_STATUS_PRIORITY.get(item, 99))
        output_weight = round(sum(_to_float(row.output_weight) for row in workshop_reports), 2) if workshop_reports else None
        merged.append(
            {
                'workshop_id': wid,
                'workshop_name': workshop.name,
                'workshop_code': workshop.code,
                'report_status': report_status,
                'output_weight': output_weight,
                **_workshop_reporting_meta(report_status),
            }
        )

    return merged


def build_factory_dashboard(db: Session, *, target_date: date) -> dict:
    production_report = _generate_production_report(db, report_date=target_date, scope=CANONICAL_REPORT_SCOPE)
    total_output = production_report.get('total_output_weight', 0.0)
    shift_count = int(production_report.get('shift_count', 0) or 0)
    confirmed_shift_count = int(production_report.get('auto_confirmed_shifts', 0) or 0)
    reviewed_shift_count = 0
    pending_shift_count = int(production_report.get('pending_or_unreported_shifts', 0) or 0)
    rejected_shift_count = int(production_report.get('returned_shifts', 0) or 0)
    voided_shift_count = int(
        db.query(func.count(ShiftProductionData.id))
        .filter(ShiftProductionData.business_date == target_date, ShiftProductionData.data_status == 'voided')
        .scalar()
        or 0
    )
    attendance_exception_count = int(
        db.query(func.count(AttendanceException.id))
        .filter(AttendanceException.business_date == target_date, AttendanceException.status == 'open')
        .scalar()
        or 0
    )
    production_exception_count = int(
        db.query(func.count(ProductionException.id))
        .filter(ProductionException.business_date == target_date, ProductionException.status == 'open')
        .scalar()
        or 0
    )
    latest_report = (
        db.query(DailyReport)
        .filter(DailyReport.report_type == 'production', DailyReport.report_date == target_date)
        .order_by(DailyReport.generated_at.desc().nullslast(), DailyReport.id.desc())
        .first()
    )

    energy_summary = energy_service.summarize_energy_for_date(db, business_date=target_date)
    open_reconciliation = int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(DataReconciliationItem.business_date == target_date, DataReconciliationItem.status == 'open')
        .scalar()
        or 0
    )
    delivery_status = build_delivery_status(db, target_date=target_date)
    mobile_summary = mobile_report_service.summarize_mobile_reporting(db, target_date=target_date)
    contract_lane = build_contract_projection(db, target_date=target_date)
    contract_progress = build_contract_progress_projection(db, target_date=target_date)
    inventory_lane = mobile_report_service.summarize_mobile_inventory(db, target_date=target_date)
    exception_lane = _build_exception_lane(db, target_date=target_date)
    reminder_summary = mobile_reminder_service.summarize_reminders(db, target_date=target_date)
    sync_status = _safe_latest_mes_sync_status(db)
    blocker_summary = _normalize_blocker_summary(quality_service.blocker_summary(db, business_date=target_date))
    month_output = _month_to_date_output(db, target_date=target_date)
    boss_summary = _build_factory_boss_summary(
        target_date=target_date,
        total_output=total_output,
        monthly_output=month_output,
        total_energy=energy_summary['total_energy'],
        energy_per_ton=energy_summary['energy_per_ton'],
        mobile_summary=mobile_summary,
        exception_total=exception_lane['mobile_exception_count'] + exception_lane['production_exception_count'],
        blocker_summary=blocker_summary,
    )
    management_estimate = build_management_estimate(
        contract_progress=contract_progress,
        contract_lane=contract_lane,
        energy_summary=energy_summary,
        mobile_summary=mobile_summary,
        total_attendance=int((latest_report.report_data or {}).get('total_attendance') or 0) if latest_report and isinstance(latest_report.report_data, dict) else 0,
        sync_status=sync_status,
        runtime_settings=settings,
    )
    leader_summary = _build_dashboard_leader_summary(
        target_date=target_date,
        latest_report=latest_report,
        total_output=total_output,
        energy_summary=energy_summary,
        mobile_summary=mobile_summary,
        contract_lane=contract_lane,
        inventory_lane=inventory_lane,
        exception_lane=exception_lane,
        blocker_summary=blocker_summary,
        yield_matrix_lane=production_report.get('yield_matrix_lane') or (latest_report.report_data.get('yield_matrix_lane') if latest_report and isinstance(latest_report.report_data, dict) else {}),
    )
    history_digest = _build_history_digest(db, target_date=target_date)
    energy_lane = _build_energy_lane(db, target_date=target_date)
    return {
        'target_date': target_date.isoformat(),
        'today_total_output': total_output,
        'month_to_date_output': month_output,
        'history_digest': history_digest,
        'total_energy': energy_summary['total_energy'],
        'energy_per_ton': energy_summary['energy_per_ton'],
        'open_reconciliation_count': open_reconciliation,
        'shift_count': shift_count,
        'confirmed_shift_count': confirmed_shift_count,
        'reviewed_shift_count': reviewed_shift_count,
        'pending_shift_count': pending_shift_count,
        'rejected_shift_count': rejected_shift_count,
        'voided_shift_count': voided_shift_count,
        'attendance_exception_count': attendance_exception_count,
        'production_exception_count': production_exception_count,
        'latest_report_published_at': latest_report.published_at if latest_report else None,
        'latest_report_text_summary': latest_report.text_summary if latest_report else None,
        'final_text_summary': latest_report.final_text_summary if latest_report else None,
        'final_confirmed_at': latest_report.final_confirmed_at if latest_report else None,
        'final_confirmed_by': latest_report.final_confirmed_by if latest_report else None,
        'is_final_version': latest_report.is_final_version if latest_report else False,
        'delivery_ready': delivery_status.get('delivery_ready', False),
        'delivery_status': delivery_status,
        'boss_summary': boss_summary,
        'leader_summary': leader_summary,
        'leader_metrics': _build_factory_leader_metrics(
            total_output=total_output,
            energy_per_ton=energy_summary['energy_per_ton'],
            inventory_lane=inventory_lane,
            contract_lane=contract_lane,
            latest_report=latest_report,
            management_estimate=management_estimate,
        ),
        'runtime_trace': _build_runtime_trace(
            surface='factory',
            history_digest=history_digest,
            energy_lane=energy_lane,
            inventory_lane=inventory_lane,
            contract_lane=contract_lane,
            exception_lane=exception_lane,
            mobile_summary=mobile_summary,
            reminder_summary=reminder_summary,
            delivery_status=delivery_status,
            sync_status=sync_status,
        ),
        'mobile_reporting_summary': mobile_summary,
        'reminder_summary': reminder_summary,
        'blocker_summary': blocker_summary,
        'production_lane': _build_production_lane(db, target_date=target_date),
        'energy_lane': energy_lane,
        'inventory_lane': inventory_lane,
        'exception_lane': exception_lane,
        'workshop_output_summary': _build_canonical_workshop_output_summary(db, target_date=target_date),
        'workshop_attendance_summary': build_workshop_attendance_summary(db, target_date=target_date),
        'workshop_reporting_status': _build_workshop_reporting_status(db, target_date),
        'contract_lane': contract_lane,
        'contract_progress': contract_progress,
        'management_estimate': management_estimate,
        'analysis_handoff': _build_analysis_handoff(
            target_date=target_date,
            surface='factory',
            total_output=total_output,
            history_digest=history_digest,
            sync_status=sync_status,
            published_report_at=latest_report.published_at if latest_report else None,
            mobile_summary=mobile_summary,
            delivery_status=delivery_status,
            energy_summary=energy_summary,
            energy_lane=energy_lane,
            contract_lane=contract_lane,
            contract_progress=contract_progress,
            blocker_summary=blocker_summary,
            exception_lane=exception_lane,
        ),
        'mes_sync_status': sync_status,
    }


def build_workshop_dashboard(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None,
) -> dict:
    base_query = db.query(ShiftProductionData).filter(
        ShiftProductionData.business_date == target_date,
        ShiftProductionData.data_status != 'voided',
    )
    if workshop_id:
        base_query = base_query.filter(ShiftProductionData.workshop_id == workshop_id)

    items = base_query.order_by(ShiftProductionData.id.desc()).limit(100).all()
    total_output = sum(_to_float(item.output_weight) for item in items)
    confirmed = len([item for item in items if item.data_status == 'confirmed'])
    reviewed = len([item for item in items if item.data_status == 'reviewed'])
    pending = len([item for item in items if item.data_status == 'pending'])
    rejected = len([item for item in items if item.data_status == 'rejected'])

    prod_ex_query = db.query(func.count(ProductionException.id)).filter(
        ProductionException.business_date == target_date,
        ProductionException.status == 'open',
    )
    att_ex_query = db.query(func.count(AttendanceException.id)).filter(
        AttendanceException.business_date == target_date,
        AttendanceException.status == 'open',
    )
    if workshop_id:
        prod_ex_query = prod_ex_query.filter(ProductionException.workshop_id == workshop_id)
        att_ex_query = att_ex_query.filter(
            AttendanceException.employee_id.in_(
                db.query(AttendanceResult.employee_id).filter(
                    AttendanceResult.business_date == target_date,
                    AttendanceResult.workshop_id == workshop_id,
                )
            )
        )

    attendance_rows = (
        db.query(
            func.count(AttendanceResult.id).label('total'),
            func.sum(case((AttendanceResult.attendance_status == 'normal', 1), else_=0)).label('normal'),
            func.sum(case((AttendanceResult.attendance_status != 'normal', 1), else_=0)).label('abnormal'),
        )
        .filter(AttendanceResult.business_date == target_date)
    )
    if workshop_id:
        attendance_rows = attendance_rows.filter(AttendanceResult.workshop_id == workshop_id)
    attendance_data = attendance_rows.first()
    energy_totals = energy_service.workshop_energy_summary(db, business_date=target_date, workshop_id=workshop_id)
    workshop_code_map = {item.id: item.code for item in db.query(Workshop).all()}
    workshop_code = workshop_code_map.get(workshop_id)
    reconciliation_open = int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(
            DataReconciliationItem.business_date == target_date,
            DataReconciliationItem.status == 'open',
            DataReconciliationItem.dimension_key.like(f'workshop:{workshop_code}%'),
        )
        .scalar()
        or 0
    )
    mobile_summary = mobile_report_service.summarize_mobile_reporting(db, target_date=target_date, workshop_id=workshop_id)
    exception_lane = _build_exception_lane(db, target_date=target_date, workshop_id=workshop_id)
    reminder_summary = mobile_reminder_service.summarize_reminders(db, target_date=target_date, workshop_id=workshop_id)
    history_digest = _build_history_digest(db, target_date=target_date, workshop_id=workshop_id)
    energy_lane = _build_energy_lane(db, target_date=target_date, workshop_id=workshop_id)
    delivery_status = build_delivery_status(db, target_date=target_date)
    sync_status = _safe_latest_mes_sync_status(db)
    inventory_lane = mobile_report_service.summarize_mobile_inventory(db, target_date=target_date, workshop_id=workshop_id)

    return {
        'target_date': target_date.isoformat(),
        'workshop_id': workshop_id,
        'total_output': total_output,
        'month_to_date_output': _month_to_date_output(db, target_date=target_date, workshop_id=workshop_id),
        'history_digest': history_digest,
        'shift_count': len(items),
        'confirmed_shift_count': confirmed,
        'reviewed_shift_count': reviewed,
        'pending_shift_count': pending,
        'rejected_shift_count': rejected,
        'attendance_exception_count': int(att_ex_query.scalar() or 0),
        'production_exception_count': int(prod_ex_query.scalar() or 0),
        'energy_summary': energy_totals,
        'reconciliation_open_count': reconciliation_open,
        'mobile_reporting_summary': mobile_summary,
        'reminder_summary': reminder_summary,
        'runtime_trace': _build_runtime_trace(
            surface='workshop',
            history_digest=history_digest,
            energy_lane=energy_lane,
            inventory_lane=inventory_lane,
            contract_lane={},
            exception_lane=exception_lane,
            mobile_summary=mobile_summary,
            reminder_summary=reminder_summary,
            delivery_status=delivery_status,
            sync_status=sync_status,
        ),
        'production_lane': _build_production_lane(db, target_date=target_date, workshop_id=workshop_id),
        'energy_lane': energy_lane,
        'inventory_lane': inventory_lane,
        'exception_lane': exception_lane,
        'analysis_handoff': _build_analysis_handoff(
            target_date=target_date,
            surface='workshop',
            total_output=total_output,
            history_digest=history_digest,
            sync_status=sync_status,
            published_report_at=None,
            mobile_summary=mobile_summary,
            delivery_status=delivery_status,
            energy_summary=energy_totals,
            energy_lane=energy_lane,
            contract_lane={},
            contract_progress={},
            blocker_summary={'has_blockers': False, 'digest': '未发现关键异常'},
            exception_lane=exception_lane,
        ),
        'attendance_summary': {
            'total': int((attendance_data.total if attendance_data else 0) or 0),
            'normal': int((attendance_data.normal if attendance_data else 0) or 0),
            'abnormal': int((attendance_data.abnormal if attendance_data else 0) or 0),
        },
        'shift_items': [
            {
                'id': item.id,
                'business_date': item.business_date.isoformat(),
                'shift_config_id': item.shift_config_id,
                'output_weight': _to_float(item.output_weight),
                'actual_headcount': item.actual_headcount,
                'data_status': item.data_status,
                'version_no': item.version_no,
            }
            for item in items
        ],
    }


def build_statistics_dashboard(db: Session, *, target_date: date) -> dict:
    pending_shift_count = int(
        db.query(func.count(ShiftProductionData.id))
        .filter(ShiftProductionData.business_date == target_date, ShiftProductionData.data_status == 'pending')
        .scalar()
        or 0
    )
    reviewed_shift_count = int(
        db.query(func.count(ShiftProductionData.id))
        .filter(ShiftProductionData.business_date == target_date, ShiftProductionData.data_status == 'reviewed')
        .scalar()
        or 0
    )
    confirmed_shift_count = int(
        db.query(func.count(ShiftProductionData.id))
        .filter(ShiftProductionData.business_date == target_date, ShiftProductionData.data_status == 'confirmed')
        .scalar()
        or 0
    )
    rejected_shift_count = int(
        db.query(func.count(ShiftProductionData.id))
        .filter(ShiftProductionData.business_date == target_date, ShiftProductionData.data_status == 'rejected')
        .scalar()
        or 0
    )
    voided_shift_count = int(
        db.query(func.count(ShiftProductionData.id))
        .filter(ShiftProductionData.business_date == target_date, ShiftProductionData.data_status == 'voided')
        .scalar()
        or 0
    )
    attendance_exception_count = int(
        db.query(func.count(AttendanceException.id))
        .filter(AttendanceException.business_date == target_date, AttendanceException.status == 'open')
        .scalar()
        or 0
    )
    production_exception_count = int(
        db.query(func.count(ProductionException.id))
        .filter(ProductionException.business_date == target_date, ProductionException.status == 'open')
        .scalar()
        or 0
    )
    pending_attendance_review = int(
        db.query(func.count(AttendanceResult.id))
        .filter(AttendanceResult.business_date == target_date, AttendanceResult.data_status == 'pending_review')
        .scalar()
        or 0
    )
    open_reconciliation = int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(DataReconciliationItem.business_date == target_date, DataReconciliationItem.status == 'open')
        .scalar()
        or 0
    )
    processed_reconciliation = int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(
            DataReconciliationItem.business_date == target_date,
            DataReconciliationItem.status.in_(['confirmed', 'ignored', 'corrected']),
        )
        .scalar()
        or 0
    )
    quality_open_count = quality_service.count_open_issues(db, business_date=target_date)
    blocker_count = quality_service.count_open_blockers(db, business_date=target_date)
    delivery_status = build_delivery_status(db, target_date=target_date)
    mobile_summary = mobile_report_service.summarize_mobile_reporting(db, target_date=target_date)
    contract_lane = build_contract_projection(db, target_date=target_date)
    contract_progress = build_contract_progress_projection(db, target_date=target_date)
    yield_matrix_lane = build_yield_matrix_projection(db, target_date=target_date)
    reminder_summary = mobile_reminder_service.summarize_reminders(db, target_date=target_date)
    sync_status = _safe_latest_mes_sync_status(db)
    management_estimate = build_management_estimate(
        contract_progress=contract_progress,
        contract_lane=contract_lane,
        energy_summary=_safe_energy_summary_for_date(db, target_date=target_date),
        mobile_summary=mobile_summary,
        total_attendance=0,
        sync_status=sync_status,
        runtime_settings=settings,
    )

    recent_batches = _safe_recent_import_batches(db, limit=10)
    pending_shift_items = _safe_pending_shift_items(db, target_date=target_date, limit=20)
    recent_reports = _safe_recent_reports(db, limit=10)
    latest_published_time = _safe_latest_published_report_time(db)

    return {
        'target_date': target_date.isoformat(),
        'pending_shift_count': pending_shift_count,
        'reviewed_shift_count': reviewed_shift_count,
        'confirmed_shift_count': confirmed_shift_count,
        'rejected_shift_count': rejected_shift_count,
        'voided_shift_count': voided_shift_count,
        'pending_attendance_review': pending_attendance_review,
        'attendance_exception_count': attendance_exception_count,
        'production_exception_count': production_exception_count,
        'open_reconciliation_count': open_reconciliation,
        'processed_reconciliation_count': processed_reconciliation,
        'quality_open_count': quality_open_count,
        'blocker_count': blocker_count,
        'delivery_ready': delivery_status.get('delivery_ready', False),
        'missing_steps': delivery_status.get('missing_steps', []),
        'can_finalize': open_reconciliation == 0 and blocker_count == 0,
        'mobile_reporting_summary': mobile_summary,
        'unreported_shift_count': reminder_summary.get('unreported_count', 0),
        'late_report_count': reminder_summary.get('late_report_count', 0),
        'today_reminder_count': reminder_summary.get('today_reminder_count', 0),
        'reminder_summary': reminder_summary,
        'latest_report_published_at': latest_published_time,
        'pending_shift_items': [
            {
                'id': item.id,
                'business_date': item.business_date.isoformat(),
                'workshop_id': item.workshop_id,
                'shift_config_id': item.shift_config_id,
                'data_status': item.data_status,
                'version_no': item.version_no,
            }
            for item in pending_shift_items
        ],
        'recent_reports': [
            {
                'id': report.id,
                'report_date': report.report_date.isoformat(),
                'report_type': report.report_type,
                'status': report.status,
                'generated_scope': report.generated_scope,
                'published_at': report.published_at,
                'text_summary': report.text_summary,
            }
            for report in recent_reports
        ],
        'contract_lane': contract_lane,
        'contract_progress': contract_progress,
        'management_estimate': management_estimate,
        'mes_sync_status': sync_status,
        'yield_matrix_lane': yield_matrix_lane,
        'recent_import_batches': [
            {
                'id': batch.id,
                'batch_no': batch.batch_no,
                'import_type': batch.import_type,
                'file_name': batch.file_name,
                'status': batch.status,
                'total_rows': batch.total_rows,
                'created_at': batch.created_at,
            }
            for batch in recent_batches
        ],
    }
