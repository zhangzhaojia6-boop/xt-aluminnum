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
