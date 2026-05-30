from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import case, func
from sqlalchemy.exc import SQLAlchemyError
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
from app.services.report import daily_overview_builder
from app.services.report._utils import CANONICAL_REPORT_SCOPE, _shift_weight_tons, _to_float


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

_SHIFT_LABEL_MAP = {'A': '白班', 'B': '中班', 'C': '晚班'}
_SHIFT_DISPLAY_ORDER = ['A', 'B', 'C']

# 铸轧分厂 = 上游铸造工序（铸锭/铸二/铸三/铸五/铸六）。
# 全厂日产量按"铸轧分厂出料"算，避免下游车间过工序量重复计入。
_PLANT_OUTPUT_WORKSHOP_CODES = {'ZD', 'ZR2', 'ZR3', 'ZR5', 'ZR6'}


def _build_yesterday_shift_breakdown(db: Session, *, target_date: date) -> dict:
    """三班分解：返回 target_date 当天的白/中/晚三班产量、能耗、异常拆分。
    7:30 是日循环节点 —— 主操实时填报后，到 7:30 时 target_date(=昨日) 的三班数据自然完整。
    上层 useDashboardSnapshot 默认 target_date = 昨天，所以每天 7:30 看到的就是
    昨日三班的精准数据；切换日期则按所选日返回。

    全厂日产量口径：按"铸轧分厂出料"（上游铸造工序）求和，避免下游过工序量重复计入。
    """
    rows = (
        db.query(ShiftProductionData)
        .join(Workshop, Workshop.id == ShiftProductionData.workshop_id)
        .filter(
            ShiftProductionData.business_date == target_date,
            ShiftProductionData.data_status.in_(['pending', 'reviewed', 'confirmed']),
            Workshop.is_active.is_(True),
        )
        .all()
    )
    shifts = db.query(ShiftConfig).all()
    shift_by_id = {s.id: s for s in shifts}

    workshops = db.query(Workshop).filter(Workshop.is_active.is_(True)).all()
    workshop_code_by_id = {w.id: w.code for w in workshops}
    plant_output_workshop_ids = {
        w.id for w in workshops if w.code in _PLANT_OUTPUT_WORKSHOP_CODES
    }

    grouped: dict[str, list[ShiftProductionData]] = {code: [] for code in _SHIFT_DISPLAY_ORDER}
    for row in rows:
        cfg = shift_by_id.get(row.shift_config_id)
        if not cfg or cfg.code not in grouped:
            continue
        grouped[cfg.code].append(row)

    workshop_total = sum(1 for w in workshops if getattr(w, 'is_active', False))

    exception_counts = dict(
        db.query(ProductionException.shift_config_id, func.count(ProductionException.id))
        .filter(
            ProductionException.business_date == target_date,
            ProductionException.shift_config_id.isnot(None),
        )
        .group_by(ProductionException.shift_config_id)
        .all()
    )

    breakdown = []
    grand_output = 0.0
    grand_throughput = 0.0
    grand_energy_kwh = 0.0
    for code in _SHIFT_DISPLAY_ORDER:
        items = grouped[code]
        plant_items = [it for it in items if it.workshop_id in plant_output_workshop_ids]
        total_output = round(
            sum(_shift_weight_tons(it, 'output_weight') for it in plant_items), 2
        )
        total_throughput = round(
            sum(_shift_weight_tons(it, 'output_weight') for it in items), 2
        )
        total_energy = round(sum(float(it.electricity_kwh or 0) for it in items), 1)
        energy_per_ton = round(total_energy / total_output, 1) if total_output > 0 and total_energy > 0 else None
        reported_workshops = len({it.workshop_id for it in items})
        ex_count = 0
        for sid, sc in shift_by_id.items():
            if sc.code == code:
                ex_count += int(exception_counts.get(sid, 0) or 0)
        cfg_match = next((s for s in shifts if s.code == code), None)
        breakdown.append(
            {
                'shift_code': code,
                'shift_name': _SHIFT_LABEL_MAP.get(code, code),
                'shift_window': (
                    f"{cfg_match.start_time.strftime('%H:%M')}-{cfg_match.end_time.strftime('%H:%M')}"
                    if cfg_match
                    else None
                ),
                'total_output': total_output,
                'total_throughput': total_throughput,
                'total_energy_kwh': total_energy,
                'energy_per_ton': energy_per_ton,
                'reported_workshops': reported_workshops,
                'expected_workshops': workshop_total,
                'shift_count': len(items),
                'exception_count': ex_count,
            }
        )
        grand_output += total_output
        grand_throughput += total_throughput
        grand_energy_kwh += total_energy

    grand_energy_per_ton = round(grand_energy_kwh / grand_output, 1) if grand_output > 0 and grand_energy_kwh > 0 else None
    return {
        'business_date': target_date.isoformat(),
        'total_output': round(grand_output, 2),
        'total_throughput': round(grand_throughput, 2),
        'output_basis': 'casting_plant',
        'output_basis_label': '铸轧分厂日产量',
        'total_energy_kwh': round(grand_energy_kwh, 1),
        'energy_per_ton': grand_energy_per_ton,
        'shifts': breakdown,
    }


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
    coil_output_by_workshop, mobile_coil_entry_count = _mobile_coil_output_by_workshop(
        db,
        target_date=target_date,
        workshop_id=workshop_id,
    )
    uses_mobile_coil_chain = mobile_coil_entry_count > 0
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
    legacy_unreported_count = mobile_summary.get('unreported_count', 0)
    legacy_returned_count = mobile_summary.get('returned_count', 0)
    legacy_late_count = mobile_summary.get('late_count', 0)
    legacy_exception_count = mobile_summary.get('exception_count', 0)
    reminder_unreported_count = reminder_summary.get('unreported_count', 0)
    reminder_late_count = reminder_summary.get('late_report_count', 0)
    today_reminder_count = reminder_summary.get('today_reminder_count', 0)
    return {
        'unreported_shift_count': 0 if uses_mobile_coil_chain else legacy_unreported_count,
        'returned_shift_count': 0 if uses_mobile_coil_chain else legacy_returned_count,
        'late_shift_count': 0 if uses_mobile_coil_chain else legacy_late_count,
        'mobile_exception_count': 0 if uses_mobile_coil_chain else legacy_exception_count,
        'legacy_unreported_shift_count': legacy_unreported_count,
        'legacy_returned_shift_count': legacy_returned_count,
        'legacy_late_shift_count': legacy_late_count,
        'legacy_mobile_exception_count': legacy_exception_count,
        'mobile_coil_entry_count': mobile_coil_entry_count,
        'mobile_coil_workshop_count': len(coil_output_by_workshop),
        'reporting_source': 'mobile_coil' if uses_mobile_coil_chain else 'mobile_shift_reports',
        'reminder_unreported_count': 0 if uses_mobile_coil_chain else reminder_unreported_count,
        'reminder_late_count': 0 if uses_mobile_coil_chain else reminder_late_count,
        'today_reminder_count': 0 if uses_mobile_coil_chain else today_reminder_count,
        'production_exception_count': mobile_report_service.count_linked_open_production_exceptions(
            db,
            target_date=target_date,
            workshop_id=workshop_id,
        ),
        'reconciliation_open_count': open_reconciliation,
        'pending_report_publish_count': unpublished_reports,
        'returned_items': [] if uses_mobile_coil_chain else mobile_summary.get('returned_items', []),
        'reminder_items': [] if uses_mobile_coil_chain else reminder_summary.get('recent_items', []),
        'recent_items': [] if uses_mobile_coil_chain else mobile_report_service.recent_mobile_exceptions(
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
    'not_applicable': 5,
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

def _coil_reporting_meta() -> dict[str, str]:
    return {
        'source_label': '主操直录',
        'source_variant': 'mobile',
        'status_hint': '现场扫码数据已进入管理端',
    }

def _coil_idle_meta() -> dict[str, str]:
    return {
        'source_label': '主操直录',
        'source_variant': 'mobile',
        'status_hint': '本日暂无扫码成品产出',
    }

def _mobile_coil_output_by_workshop(
    db: Session,
    *,
    target_date: date,
    workshop_id: int | None = None,
) -> tuple[dict[int, float], int]:
    output_by_workshop: dict[int, float] = {}
    entry_count = 0
    try:
        rows = daily_overview_builder._query_latest_mobile_coil_rows(db, target_date, target_date)
    except SQLAlchemyError:
        return {}, 0
    for row in rows:
        if workshop_id and row.workshop_id != workshop_id:
            continue
        if row.workshop_id is None:
            continue
        entry_count += 1
        wid = int(row.workshop_id)
        output_by_workshop[wid] = output_by_workshop.get(wid, 0.0) + (_to_float(row.output_weight) / 1000)
    return output_by_workshop, entry_count

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

    coil_output_by_workshop, _entry_count = _mobile_coil_output_by_workshop(db, target_date=target_date)
    uses_mobile_coil_chain = bool(coil_output_by_workshop)
    if not uses_mobile_coil_chain:
        coil_rows = (
            db.query(ShiftProductionData)
            .filter(
                ShiftProductionData.business_date == target_date,
                ShiftProductionData.data_status == 'pending',
                ShiftProductionData.data_source == 'mobile_coil_agg',
            )
            .all()
        )
        for row in coil_rows:
            wid = int(row.workshop_id)
            coil_output_by_workshop[wid] = coil_output_by_workshop.get(wid, 0.0) + _shift_weight_tons(row, 'output_weight')

    merged: list[dict] = []
    for workshop in workshops:
        wid = int(workshop.id)
        workshop_reports = reports_by_workshop.get(wid, [])
        coil_output = coil_output_by_workshop.get(wid)
        expected_keys = expected_by_workshop.get(wid, set())
        statuses = [_mobile_report_decision_status(row) for row in workshop_reports]
        if uses_mobile_coil_chain:
            statuses = ['submitted'] if coil_output is not None else ['not_applicable']
        elif not statuses and coil_output is not None:
            statuses.append('draft')
        elif expected_keys:
            for key in expected_keys:
                if (wid, key[0], key[1]) not in report_key_status:
                    statuses.append('unreported')
        if not statuses:
            statuses.append('unreported')
        report_status = min(statuses, key=lambda item: _REPORT_STATUS_PRIORITY.get(item, 99))
        output_weight = round(sum(_to_float(row.output_weight) for row in workshop_reports), 2) if workshop_reports else None
        source_meta = _workshop_reporting_meta(report_status)
        if uses_mobile_coil_chain:
            output_weight = round(coil_output, 2) if coil_output is not None else None
            source_meta = _coil_reporting_meta() if coil_output is not None else _coil_idle_meta()
        elif not workshop_reports and coil_output is not None:
            output_weight = round(coil_output, 2)
            source_meta = _coil_reporting_meta()
        merged.append(
            {
                'workshop_id': wid,
                'workshop_name': workshop.name,
                'workshop_code': workshop.code,
                'report_status': report_status,
                'output_weight': output_weight,
                **source_meta,
            }
        )

    return merged
