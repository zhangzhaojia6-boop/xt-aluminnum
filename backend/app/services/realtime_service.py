from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.scope import (
    build_scope_summary,
    can_view_all_work_order_entries,
    can_view_work_order_entries,
    resolve_work_order_entry_workshop_scope,
)
from app.models.attendance import AttendanceSchedule, EmployeeAttendanceDetail, ShiftAttendanceConfirmation
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import attendance_confirm_service
from app.services import master_service
from app.services import mes_sync_service
from app.services.yield_matrix_canonical_service import build_yield_matrix_projection
from app.utils.tracking_cards import tracking_card_lookup_key

LOCAL_SHIFT_DATA_SOURCE = 'mobile_coil_agg'
LOCAL_SHIFT_DATA_STATUSES = {'pending', 'submitted', 'reviewed', 'confirmed'}
FORMAL_ENTRY_STATUSES = {'submitted', 'verified', 'approved'}
ACTIVE_DATE_LOOKBACK_HOURS = 36


def _to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _entry_weight_tons(item: dict, field_name: str) -> float:
    value = _to_float(item.get(field_name))
    if item.get('weight_unit') == 'kg':
        return value / 1000
    return value


def _is_formal_entry(item: dict) -> bool:
    return item.get('entry_status') in FORMAL_ENTRY_STATUSES or item.get('entry_type') == 'mes_projection'


def _entry_count_summary(items: list[dict]) -> dict:
    formal_count = len([item for item in items if _is_formal_entry(item)])
    draft_count = len([item for item in items if item.get('entry_status') == 'draft'])
    return {
        'formal_entry_count': formal_count,
        'draft_entry_count': draft_count,
        'total_entry_count': len(items),
    }


def _optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.DEFAULT_TIMEZONE))


def resolve_live_business_date(
    db: Session,
    *,
    today: date | None = None,
    now: datetime | None = None,
    lookback_hours: int = ACTIVE_DATE_LOOKBACK_HOURS,
) -> dict:
    resolved_now = now or _local_now()
    resolved_today = today or resolved_now.date()
    cutoff = resolved_now - timedelta(hours=max(int(lookback_hours or ACTIVE_DATE_LOOKBACK_HOURS), 1))

    recent_entry = (
        db.query(
            WorkOrderEntry.business_date,
            func.count(WorkOrderEntry.id).label('entry_count'),
            func.max(WorkOrderEntry.created_at).label('last_created_at'),
        )
        .filter(
            WorkOrderEntry.business_date <= resolved_today,
            WorkOrderEntry.created_at >= cutoff,
        )
        .group_by(WorkOrderEntry.business_date)
        .order_by(func.max(WorkOrderEntry.created_at).desc(), WorkOrderEntry.business_date.desc())
        .first()
    )
    if recent_entry is not None and recent_entry.business_date is not None:
        return {
            'business_date': recent_entry.business_date.isoformat(),
            'source': 'recent_upload',
            'recent_entry_count': int(recent_entry.entry_count or 0),
        }

    recent_shift = (
        db.query(
            ShiftProductionData.business_date,
            func.count(ShiftProductionData.id).label('entry_count'),
            func.max(ShiftProductionData.updated_at).label('last_updated_at'),
        )
        .filter(
            ShiftProductionData.business_date <= resolved_today,
            ShiftProductionData.updated_at >= cutoff,
            ShiftProductionData.data_status != 'voided',
        )
        .group_by(ShiftProductionData.business_date)
        .order_by(func.max(ShiftProductionData.updated_at).desc(), ShiftProductionData.business_date.desc())
        .first()
    )
    if recent_shift is not None and recent_shift.business_date is not None:
        return {
            'business_date': recent_shift.business_date.isoformat(),
            'source': 'recent_shift_data',
            'recent_entry_count': int(recent_shift.entry_count or 0),
        }

    return {
        'business_date': resolved_today.isoformat(),
        'source': 'current_date',
        'recent_entry_count': 0,
    }


def _build_pending_assignment_summary(*, entries: list[dict], workshops, shifts) -> dict:
    pending_entries = [
        item
        for item in entries
        if item.get('machine_id') is None or item.get('shift_id') is None
    ]
    entry_count = len(pending_entries)
    if entry_count == 0:
        return {'entry_count': 0}

    workshop_name_by_id = {
        int(item.id): item.name
        for item in workshops
        if getattr(item, 'id', None) is not None
    }
    shift_name_by_id = {
        int(item.id): item.name
        for item in shifts
        if getattr(item, 'id', None) is not None
    }
    rows: dict[tuple[int | None, int | None], dict] = {}
    workshop_ids: set[int] = set()
    shift_ids: set[int] = set()
    input_total = 0.0
    output_total = 0.0
    formal_count = 0
    draft_count = 0
    missing_machine_count = 0
    missing_shift_count = 0

    for item in pending_entries:
        workshop_id = _optional_int(item.get('workshop_id'))
        shift_id = _optional_int(item.get('shift_id'))
        if workshop_id is not None:
            workshop_ids.add(workshop_id)
        if shift_id is not None:
            shift_ids.add(shift_id)

        input_weight = _entry_weight_tons(item, 'input_weight')
        output_weight = _entry_weight_tons(item, 'output_weight')
        input_total += input_weight
        output_total += output_weight
        is_formal = _is_formal_entry(item)
        is_draft = item.get('entry_status') == 'draft'
        formal_count += 1 if is_formal else 0
        draft_count += 1 if is_draft else 0
        missing_machine = item.get('machine_id') is None
        missing_shift = item.get('shift_id') is None
        missing_machine_count += 1 if missing_machine else 0
        missing_shift_count += 1 if missing_shift else 0

        key = (workshop_id, shift_id)
        row = rows.setdefault(
            key,
            {
                'workshop_id': workshop_id,
                'workshop_name': workshop_name_by_id.get(workshop_id, '未标记车间'),
                'shift_id': shift_id,
                'shift_name': shift_name_by_id.get(shift_id, '未标记班次'),
                'entry_count': 0,
                'draft_entry_count': 0,
                'formal_entry_count': 0,
                'missing_machine_count': 0,
                'missing_shift_count': 0,
                'input': 0.0,
                'output': 0.0,
            },
        )
        row['entry_count'] += 1
        row['draft_entry_count'] += 1 if is_draft else 0
        row['formal_entry_count'] += 1 if is_formal else 0
        row['missing_machine_count'] += 1 if missing_machine else 0
        row['missing_shift_count'] += 1 if missing_shift else 0
        row['input'] += input_weight
        row['output'] += output_weight

    row_items = []
    for row in rows.values():
        row_items.append(
            {
                **row,
                'input': round(row['input'], 2),
                'output': round(row['output'], 2),
            }
        )
    row_items.sort(key=lambda item: (-item['output'], -item['entry_count'], str(item['workshop_name']), str(item['shift_name'])))

    return {
        'entry_count': entry_count,
        'draft_entry_count': draft_count,
        'formal_entry_count': formal_count,
        'missing_machine_count': missing_machine_count,
        'missing_shift_count': missing_shift_count,
        'workshop_count': len(workshop_ids),
        'shift_count': len(shift_ids),
        'input': round(input_total, 2),
        'output': round(output_total, 2),
        'rows': row_items,
    }


def _round_rate(input_total: float, output_total: float) -> float | None:
    if input_total <= 0:
        return None
    return round((output_total / input_total) * 100, 2)


def _prefer_number(primary: Decimal | float | int | None, fallback: Decimal | float | int | None) -> float:
    if primary is not None:
        return _to_float(primary)
    return _to_float(fallback)


def _build_cell_status(*, is_applicable: bool, submission_status: str, attendance_status: str, attendance_exception_count: int) -> dict:
    if not is_applicable:
        return {'status_tone': 'muted', 'status_text': '不适用'}
    if attendance_exception_count > 0:
        return {'status_tone': 'danger', 'status_text': '考勤异常'}
    if submission_status == 'not_started':
        return {'status_tone': 'danger', 'status_text': '缺报'}
    if submission_status == 'in_progress':
        return {'status_tone': 'warning', 'status_text': '进行中'}
    if attendance_status in {'pending', 'not_started'}:
        return {'status_tone': 'warning', 'status_text': '考勤待确认'}
    return {'status_tone': 'success', 'status_text': '已填'}


def _resolve_workshop_filter(*, current_user: User, workshop_id: int | None) -> int | None:
    summary = build_scope_summary(current_user)
    if not can_view_work_order_entries(summary):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='work order entry access denied')
    scoped_id = resolve_work_order_entry_workshop_scope(summary)
    if can_view_all_work_order_entries(summary):
        return workshop_id
    if scoped_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='workshop scope denied')
    if workshop_id is not None and workshop_id != scoped_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='workshop scope denied')
    return scoped_id


def aggregate_live_payload(
    *,
    workshops,
    machines,
    shifts,
    entries: list[dict],
    attendance: dict[tuple[int, int], dict],
    expected_counts: dict[tuple[int, int, int], int],
) -> dict:
    machine_map: dict[int, list] = defaultdict(list)
    for machine in machines:
        machine_map[machine.workshop_id].append(machine)

    cell_entries: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
    for item in entries:
        if item.get('machine_id') is None or item.get('shift_id') is None:
            continue
        cell_entries[(item['workshop_id'], item['machine_id'], item['shift_id'])].append(item)

    workshop_entries: dict[int, list[dict]] = defaultdict(list)
    for item in entries:
        workshop_id = _optional_int(item.get('workshop_id'))
        if workshop_id is None:
            continue
        workshop_entries[workshop_id].append(item)

    workshop_items: list[dict] = []
    submitted_cells = 0
    total_cells = 0
    missing_cell_count = 0
    attention_cell_count = 0
    factory_input = 0.0
    factory_output = 0.0
    factory_scrap = 0.0
    overall_entry_counts = _entry_count_summary(entries)
    pending_assignment = _build_pending_assignment_summary(entries=entries, workshops=workshops, shifts=shifts)
    ordered_shifts = sorted(shifts, key=lambda item: (getattr(item, 'sort_order', 0), item.id))

    for workshop in sorted(workshops, key=lambda item: item.id):
        workshop_input = 0.0
        workshop_output = 0.0
        workshop_scrap = 0.0
        workshop_entry_counts = _entry_count_summary(workshop_entries.get(int(workshop.id), []))
        machine_items: list[dict] = []

        for machine in sorted(machine_map.get(workshop.id, []), key=lambda item: (getattr(item, 'sort_order', 0), item.id)):
            shift_items: list[dict] = []
            machine_input = 0.0
            machine_output = 0.0
            machine_scrap = 0.0
            applicable_shift_ids = {
                int(item) for item in (getattr(machine, 'assigned_shift_ids', None) or [shift.id for shift in ordered_shifts])
            }

            for shift in ordered_shifts:
                is_applicable = shift.id in applicable_shift_ids
                attendance_state = attendance.get((workshop.id, shift.id), {'status': 'not_applicable', 'exception_count': 0})
                if not is_applicable:
                    cell_status = _build_cell_status(
                        is_applicable=False,
                        submission_status='not_applicable',
                        attendance_status='not_applicable',
                        attendance_exception_count=0,
                    )
                    shift_items.append(
                        {
                            'shift_id': shift.id,
                            'shift_name': shift.name,
                            'submitted_count': 0,
                            'draft_count': 0,
                            'total_expected': 0,
                            'total_input': 0.0,
                            'total_output': 0.0,
                            'total_scrap': 0.0,
                            'yield_rate': None,
                            'yield_rate_source': 'runtime_compat',
                            'attendance_status': 'not_applicable',
                            'attendance_exception_count': 0,
                            'submission_status': 'not_applicable',
                            'is_applicable': False,
                            **cell_status,
                        }
                    )
                    continue

                total_cells += 1
                rows = cell_entries.get((workshop.id, machine.id, shift.id), [])
                submitted_count = len(
                    [
                        item
                        for item in rows
                        if _is_formal_entry(item)
                    ]
                )
                draft_count = len([item for item in rows if item.get('entry_status') == 'draft'])
                total_count = len(rows)
                input_total = round(sum(_entry_weight_tons(item, 'input_weight') for item in rows), 2)
                output_total = round(sum(_entry_weight_tons(item, 'output_weight') for item in rows), 2)
                scrap_total = round(sum(_entry_weight_tons(item, 'scrap_weight') for item in rows), 2)
                expected_total = int(expected_counts.get((workshop.id, machine.id, shift.id), 0))
                if expected_total <= 0 and total_count > 0:
                    expected_total = total_count

                if total_count == 0:
                    submission_status = 'not_started'
                elif submitted_count >= max(expected_total, 1) and submitted_count == total_count:
                    submission_status = 'all_submitted'
                else:
                    submission_status = 'in_progress'
                if submitted_count > 0:
                    submitted_cells += 1
                attendance_status = attendance_state['status']
                attendance_exception_count = int(attendance_state.get('exception_count', 0))
                cell_status = _build_cell_status(
                    is_applicable=True,
                    submission_status=submission_status,
                    attendance_status=attendance_status,
                    attendance_exception_count=attendance_exception_count,
                )
                if submission_status == 'not_started':
                    missing_cell_count += 1
                if cell_status['status_tone'] in {'danger', 'warning'}:
                    attention_cell_count += 1

                machine_input += input_total
                machine_output += output_total
                machine_scrap += scrap_total
                shift_items.append(
                    {
                        'shift_id': shift.id,
                        'shift_name': shift.name,
                        'submitted_count': submitted_count,
                        'draft_count': draft_count,
                        'total_expected': expected_total,
                        'total_input': input_total,
                        'total_output': output_total,
                        'total_scrap': scrap_total,
                        'yield_rate': _round_rate(input_total, output_total),
                        'yield_rate_source': 'runtime_compat',
                        'attendance_status': attendance_status,
                        'attendance_exception_count': attendance_exception_count,
                        'submission_status': submission_status,
                        'is_applicable': True,
                        **cell_status,
                    }
                )

            workshop_input += machine_input
            workshop_output += machine_output
            workshop_scrap += machine_scrap
            machine_binding_status = getattr(machine, 'machine_binding_status', None)
            if not machine_binding_status:
                machine_binding_status = 'unbound' if int(machine.id) < 0 else 'bound'
            machine_items.append(
                {
                    'machine_id': machine.id,
                    'machine_name': machine.name,
                    'machine_binding_status': machine_binding_status,
                    'shifts': shift_items,
                    'day_total': {
                        'input': round(machine_input, 2),
                        'output': round(machine_output, 2),
                        'scrap': round(machine_scrap, 2),
                        'yield_rate': _round_rate(machine_input, machine_output),
                        'yield_rate_source': 'runtime_compat',
                    },
                }
            )

        factory_input += workshop_input
        factory_output += workshop_output
        factory_scrap += workshop_scrap
        shift_totals: list[dict] = []
        for shift in ordered_shifts:
            is_applicable = False
            shift_input = 0.0
            shift_output = 0.0
            shift_scrap = 0.0
            for machine in machine_items:
                target = next((item for item in machine['shifts'] if item['shift_id'] == shift.id), None)
                if not target or not target.get('is_applicable'):
                    continue
                is_applicable = True
                shift_input += _to_float(target.get('total_input'))
                shift_output += _to_float(target.get('total_output'))
                shift_scrap += _to_float(target.get('total_scrap'))
            shift_totals.append(
                {
                    'shift_id': shift.id,
                    'shift_name': shift.name,
                    'is_applicable': is_applicable,
                    'total_input': round(shift_input, 2),
                    'total_output': round(shift_output, 2),
                    'total_scrap': round(shift_scrap, 2),
                    'yield_rate': _round_rate(shift_input, shift_output),
                    'yield_rate_source': 'runtime_compat',
                }
            )
        workshop_items.append(
            {
                'workshop_id': workshop.id,
                'workshop_name': workshop.name,
                'machines': machine_items,
                'shift_totals': shift_totals,
                'workshop_total': {
                    'input': round(workshop_input, 2),
                    'output': round(workshop_output, 2),
                    'scrap': round(workshop_scrap, 2),
                    'yield_rate': _round_rate(workshop_input, workshop_output),
                    'yield_rate_source': 'runtime_work_order',
                    **workshop_entry_counts,
                },
            }
        )

    overall_progress = {
        'submitted_cells': submitted_cells,
        'total_cells': total_cells,
        'missing_cell_count': missing_cell_count,
        'attention_cell_count': attention_cell_count,
        'completion_rate': round((submitted_cells / total_cells) * 100, 2) if total_cells else 0.0,
        **overall_entry_counts,
    }
    if pending_assignment['entry_count'] > 0:
        overall_progress['pending_assignment'] = pending_assignment

    return {
        'overall_progress': overall_progress,
        'workshops': workshop_items,
        'factory_total': {
            'input': round(factory_input, 2),
            'output': round(factory_output, 2),
            'scrap': round(factory_scrap, 2),
            'yield_rate': _round_rate(factory_input, factory_output),
            'yield_rate_source': 'runtime_work_order',
        },
    }


def _resolve_yield_matrix_workshop_key(workshop: Workshop) -> str | None:
    code = str(getattr(workshop, 'code', '') or '').upper()
    name = str(getattr(workshop, 'name', '') or '')
    text = f'{code} {name}'
    if '1450' in text:
        return 'cold_roll_1450'
    if '1650' in text or '2050' in text:
        return 'cold_roll_1650_2050'
    if '1850' in text:
        return 'cold_roll_1850'
    if '拉矫' in text:
        return 'stretch'
    if '精整' in text:
        return 'finishing'
    if '飞剪' in text or '剪切' in text or code in {'JQ', 'CPK'}:
        return 'park_cutting'
    return None


def _apply_yield_matrix_authority(payload: dict, workshops: list[Workshop], yield_matrix_lane: dict) -> dict:
    matrix_ready = yield_matrix_lane.get('quality_status') == 'ready'
    if not matrix_ready:
        payload['yield_matrix_lane'] = yield_matrix_lane
        return payload

    workshop_truth = dict(yield_matrix_lane.get('workshop_yields') or {})
    company_total = yield_matrix_lane.get('company_total_yield')
    workshop_key_by_id = {item.id: _resolve_yield_matrix_workshop_key(item) for item in workshops}

    for workshop_payload in payload.get('workshops', []):
        workshop_key = workshop_key_by_id.get(workshop_payload.get('workshop_id'))
        workshop_total = dict(workshop_payload.get('workshop_total') or {})
        if workshop_key and workshop_key in workshop_truth:
            workshop_total['yield_rate'] = workshop_truth[workshop_key]
            workshop_total['yield_rate_source'] = 'yield_matrix_lane'
            workshop_total['yield_matrix_key'] = workshop_key
            workshop_payload['workshop_total'] = workshop_total

    factory_total = dict(payload.get('factory_total') or {})
    if company_total is not None:
        factory_total['yield_rate'] = company_total
        factory_total['yield_rate_source'] = 'yield_matrix_lane'
        payload['factory_total'] = factory_total

    payload['yield_matrix_lane'] = yield_matrix_lane
    return payload


def _load_entry_rows(db: Session, *, business_date: date, workshop_id: int | None) -> list[dict]:
    query = (
        db.query(WorkOrderEntry, WorkOrder)
        .join(WorkOrder, WorkOrder.id == WorkOrderEntry.work_order_id)
        .filter(WorkOrderEntry.business_date == business_date)
    )
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)
    return [
        {
            'id': entry.id,
            'tracking_card_no': work_order.tracking_card_no,
            'work_order_id': entry.work_order_id,
            'workshop_id': entry.workshop_id,
            'machine_id': entry.machine_id,
            'shift_id': entry.shift_id,
            'business_date': entry.business_date.isoformat(),
            'input_weight': _prefer_number(entry.verified_input_weight, entry.input_weight),
            'output_weight': _prefer_number(entry.verified_output_weight, entry.output_weight),
            'scrap_weight': _to_float(entry.scrap_weight),
            'yield_rate': float(entry.yield_rate) if entry.yield_rate is not None else None,
            'yield_rate_source': 'runtime_compat',
            'entry_status': entry.entry_status,
            'entry_type': entry.entry_type,
            'weight_unit': 'kg',
            'tracking_card_status': work_order.overall_status,
        }
        for entry, work_order in query.all()
    ]


def _entry_weight_kg_to_tons(entry: WorkOrderEntry, field_name: str) -> float:
    value = getattr(entry, field_name)
    if field_name == 'input_weight':
        value = _prefer_number(entry.verified_input_weight, entry.input_weight)
    elif field_name == 'output_weight':
        value = _prefer_number(entry.verified_output_weight, entry.output_weight)
    return _to_float(value) / 1000


def _iso_datetime(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def build_pending_assignment_detail(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
    current_user: User,
) -> dict:
    scoped_workshop_id = _resolve_workshop_filter(current_user=current_user, workshop_id=workshop_id)
    query = (
        db.query(WorkOrderEntry, WorkOrder, Workshop, ShiftConfig)
        .join(WorkOrder, WorkOrder.id == WorkOrderEntry.work_order_id)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .outerjoin(ShiftConfig, ShiftConfig.id == WorkOrderEntry.shift_id)
        .filter(
            WorkOrderEntry.business_date == business_date,
            or_(WorkOrderEntry.machine_id.is_(None), WorkOrderEntry.shift_id.is_(None)),
        )
    )
    if scoped_workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == scoped_workshop_id)

    items = []
    input_total = 0.0
    output_total = 0.0
    scrap_total = 0.0
    draft_count = 0
    formal_count = 0
    missing_machine_count = 0
    missing_shift_count = 0

    rows = query.order_by(Workshop.sort_order.asc(), Workshop.id.asc(), WorkOrderEntry.id.desc()).all()
    for entry, work_order, workshop, shift in rows:
        input_weight = _entry_weight_kg_to_tons(entry, 'input_weight')
        output_weight = _entry_weight_kg_to_tons(entry, 'output_weight')
        scrap_weight = _entry_weight_kg_to_tons(entry, 'scrap_weight')
        input_total += input_weight
        output_total += output_weight
        scrap_total += scrap_weight

        missing_fields = []
        if entry.machine_id is None:
            missing_fields.append('machine_id')
            missing_machine_count += 1
        if entry.shift_id is None:
            missing_fields.append('shift_id')
            missing_shift_count += 1

        entry_status = entry.entry_status
        entry_type = entry.entry_type
        is_formal = _is_formal_entry({'entry_status': entry_status, 'entry_type': entry_type})
        formal_count += 1 if is_formal else 0
        draft_count += 1 if entry_status == 'draft' else 0
        items.append(
            {
                'entry_id': entry.id,
                'work_order_id': entry.work_order_id,
                'tracking_card_no': work_order.tracking_card_no,
                'business_date': entry.business_date.isoformat(),
                'workshop_id': entry.workshop_id,
                'workshop_name': workshop.name,
                'shift_id': entry.shift_id,
                'shift_name': shift.name if shift is not None else None,
                'machine_id': entry.machine_id,
                'entry_status': entry_status,
                'entry_type': entry_type,
                'input_weight': round(input_weight, 2),
                'output_weight': round(output_weight, 2),
                'scrap_weight': round(scrap_weight, 2),
                'missing_fields': missing_fields,
                'created_by_user_id': entry.created_by_user_id,
                'created_at': _iso_datetime(entry.created_at),
            }
        )

    return {
        'business_date': business_date.isoformat(),
        'workshop_id': scoped_workshop_id,
        'total': len(items),
        'summary': {
            'entry_count': len(items),
            'draft_entry_count': draft_count,
            'formal_entry_count': formal_count,
            'missing_machine_count': missing_machine_count,
            'missing_shift_count': missing_shift_count,
            'input': round(input_total, 2),
            'output': round(output_total, 2),
            'scrap': round(scrap_total, 2),
        },
        'items': items,
    }


def _load_local_shift_rows(db: Session, *, business_date: date, workshop_id: int | None) -> list[ShiftProductionData]:
    query = db.query(ShiftProductionData).filter(
        ShiftProductionData.business_date == business_date,
        ShiftProductionData.data_source == LOCAL_SHIFT_DATA_SOURCE,
        ShiftProductionData.data_status.in_(LOCAL_SHIFT_DATA_STATUSES),
    )
    if workshop_id is not None:
        query = query.filter(ShiftProductionData.workshop_id == workshop_id)
    return query.all()


def _unbound_shift_machine_id(workshop_id: int, shift_id: int) -> int:
    return -((int(workshop_id) * 1000) + int(shift_id))


def _build_local_shift_runtime_inputs(*, machines, shifts, rows) -> tuple[list, list[dict]]:
    machine_items = list(machines)
    shift_by_id = {int(item.id): item for item in shifts if getattr(item, 'id', None) is not None}
    unbound_keys: set[tuple[int, int]] = set()
    entries: list[dict] = []

    for row in rows:
        workshop_id = getattr(row, 'workshop_id', None)
        shift_id = getattr(row, 'shift_config_id', None)
        if workshop_id is None or shift_id is None:
            continue
        workshop_id = int(workshop_id)
        shift_id = int(shift_id)
        machine_id = getattr(row, 'equipment_id', None)
        if machine_id is None:
            machine_id = _unbound_shift_machine_id(workshop_id, shift_id)
            key = (workshop_id, shift_id)
            if key not in unbound_keys:
                shift = shift_by_id.get(shift_id)
                shift_name = getattr(shift, 'name', None) or f'{shift_id}班'
                shift_sort = int(getattr(shift, 'sort_order', shift_id) or shift_id)
                machine_items.append(
                    SimpleNamespace(
                        id=machine_id,
                        workshop_id=workshop_id,
                        name=f'未绑定机列 / {shift_name}',
                        machine_binding_status='unbound',
                        assigned_shift_ids=[shift_id],
                        sort_order=100000 + shift_sort,
                    )
                )
                unbound_keys.add(key)
        else:
            machine_id = int(machine_id)

        business_date_value = getattr(row, 'business_date', None)
        yield_value = getattr(row, 'yield_rate', None)
        entries.append(
            {
                'id': getattr(row, 'id', None),
                'tracking_card_no': f"SHIFT-{getattr(row, 'id', '')}",
                'work_order_id': None,
                'workshop_id': workshop_id,
                'machine_id': machine_id,
                'shift_id': shift_id,
                'business_date': business_date_value.isoformat() if business_date_value else None,
                'input_weight': _to_float(getattr(row, 'input_weight', None)),
                'output_weight': _to_float(getattr(row, 'output_weight', None)),
                'scrap_weight': _to_float(getattr(row, 'scrap_weight', None)),
                'yield_rate': float(yield_value) if yield_value is not None else None,
                'yield_rate_source': 'local_shift_data',
                'entry_status': 'submitted',
                'entry_type': LOCAL_SHIFT_DATA_SOURCE,
                'weight_unit': 'kg',
                'tracking_card_status': getattr(row, 'data_status', None) or 'pending',
                'data_source': LOCAL_SHIFT_DATA_SOURCE,
            }
        )

    return machine_items, entries


def _drop_local_entries_for_existing_cells(entry_rows: list[dict], local_entries: list[dict]) -> list[dict]:
    occupied = {
        (item.get('workshop_id'), item.get('machine_id'), item.get('shift_id'))
        for item in entry_rows
        if item.get('workshop_id') is not None and item.get('machine_id') is not None and item.get('shift_id') is not None
    }
    return [
        item
        for item in local_entries
        if (item.get('workshop_id'), item.get('machine_id'), item.get('shift_id')) not in occupied
    ]


def _tracking_card_key(value) -> str:
    return tracking_card_lookup_key(value)


def _merge_runtime_entries(*, entry_rows: list[dict], local_entries: list[dict], mes_rows: list[dict]) -> tuple[list[dict], str]:
    mes_row_by_card = {
        _tracking_card_key(item.get('tracking_card_no')): item
        for item in mes_rows
        if _tracking_card_key(item.get('tracking_card_no'))
    }

    def apply_mes_binding(items: list[dict]) -> tuple[list[dict], bool]:
        enriched: list[dict] = []
        has_mes_binding = False
        for item in items:
            tracking_card = _tracking_card_key(item.get('tracking_card_no'))
            mes_item = mes_row_by_card.get(tracking_card)
            if not mes_item:
                enriched.append(item)
                continue
            updated = dict(item)
            mes_workshop_id = mes_item.get('workshop_id')
            current_workshop_id = updated.get('workshop_id')
            workshop_matches = mes_workshop_id is None or current_workshop_id is None or current_workshop_id == mes_workshop_id
            for field_name in ('workshop_id', 'machine_id', 'shift_id'):
                if field_name in {'machine_id', 'shift_id'} and not workshop_matches:
                    continue
                if updated.get(field_name) is None and mes_item.get(field_name) is not None:
                    updated[field_name] = mes_item[field_name]
                    has_mes_binding = True
            enriched.append(updated)
        return enriched, has_mes_binding

    entry_rows, entry_has_mes_binding = apply_mes_binding(entry_rows)
    local_entries, local_has_mes_binding = apply_mes_binding(local_entries)
    has_mes_binding = entry_has_mes_binding or local_has_mes_binding
    fill_tracking_cards = {
        _tracking_card_key(item.get('tracking_card_no'))
        for item in [*entry_rows, *local_entries]
        if _tracking_card_key(item.get('tracking_card_no'))
    }
    filtered_mes_rows = [
        item
        for item in mes_rows
        if _tracking_card_key(item.get('tracking_card_no')) not in fill_tracking_cards
    ]
    entries = [*entry_rows, *local_entries, *filtered_mes_rows]
    has_fill = bool(entry_rows or local_entries)
    has_mes = bool(filtered_mes_rows)
    if has_fill and (has_mes or has_mes_binding):
        return entries, 'mixed'
    if has_mes:
        return entries, 'mes_projection'
    if local_entries:
        return entries, 'local_shift_data'
    return entries, 'work_order_runtime'


def _load_mes_snapshot_rows(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
    tracking_card_nos: set[str] | None = None,
) -> list[dict]:
    workshop_rows = db.query(Workshop).filter(Workshop.is_active.is_(True)).all()
    workshop_id_by_code = {str(item.code or '').strip().upper(): item.id for item in workshop_rows if item.code}
    workshop_name_by_id = {item.id: item.name for item in workshop_rows}
    machine_rows = db.query(Equipment).filter(Equipment.is_active.is_(True)).all()
    machine_id_by_code = {str(item.code or '').strip().upper(): item.id for item in machine_rows if item.code}
    shift_rows = db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).all()
    shift_id_by_code = {str(item.code or '').strip().upper(): item.id for item in shift_rows if item.code}
    work_order_by_card = {
        str(item.tracking_card_no or '').strip().upper(): item
        for item in db.query(WorkOrder).all()
        if item.tracking_card_no
    }
    resolved_workshop_code_by_raw: dict[str, str] = {}
    resolved_machine_code_by_raw: dict[str, str] = {}

    def resolve_mes_code(entity_type: str, raw_code: object | None, cache: dict[str, str]) -> str:
        raw_text = str(raw_code or '').strip()
        if raw_text not in cache:
            cache[raw_text] = master_service.resolve_canonical_code(
                db,
                entity_type=entity_type,
                value=raw_text,
                source_type='mes_mvc',
            ) or raw_text
        return cache[raw_text]

    requested_tracking_cards = {_tracking_card_key(item) for item in (tracking_card_nos or set()) if _tracking_card_key(item)}
    query = db.query(MesCoilSnapshot)
    snapshots = []
    for item in query.all():
        snapshot_date = item.business_date or (item.event_time.date() if item.event_time else None)
        tracking_card_no = _tracking_card_key(item.tracking_card_no)
        if snapshot_date != business_date and tracking_card_no not in requested_tracking_cards:
            continue
        canonical_workshop_code = resolve_mes_code('workshop', item.workshop_code, resolved_workshop_code_by_raw)
        snapshot_workshop_id = workshop_id_by_code.get(canonical_workshop_code.strip().upper())
        if workshop_id is not None and snapshot_workshop_id != workshop_id:
            continue
        snapshots.append(item)

    payload: list[dict] = []
    for item in snapshots:
        source_payload = dict(item.source_payload or {})
        metadata = dict(source_payload.get('metadata') or {})
        tracking_card_no = str(item.tracking_card_no or '').strip().upper()
        work_order = work_order_by_card.get(tracking_card_no)
        canonical_workshop_code = resolve_mes_code('workshop', item.workshop_code, resolved_workshop_code_by_raw)
        canonical_machine_code = resolve_mes_code('equipment', item.machine_code, resolved_machine_code_by_raw)
        resolved_workshop_id = workshop_id_by_code.get(canonical_workshop_code.strip().upper())
        resolved_machine_id = machine_id_by_code.get(canonical_machine_code.strip().upper())
        resolved_shift_id = shift_id_by_code.get(str(item.shift_code or '').strip().upper())
        payload.append(
            {
                'id': item.id,
                'tracking_card_no': tracking_card_no,
                'work_order_id': work_order.id if work_order else None,
                'workshop_id': resolved_workshop_id,
                'machine_id': resolved_machine_id,
                'shift_id': resolved_shift_id,
                'business_date': business_date.isoformat(),
                'input_weight': _to_float(source_payload.get('input_weight') or metadata.get('input_weight')),
                'output_weight': _to_float(source_payload.get('output_weight') or metadata.get('output_weight')),
                'scrap_weight': _to_float(source_payload.get('scrap_weight') or metadata.get('scrap_weight')),
                'yield_rate': None,
                'yield_rate_source': 'mes_projection',
                'entry_status': item.status or 'synced',
                'entry_type': 'mes_projection',
                'tracking_card_status': item.status or 'synced',
            }
        )
    return payload


def _build_attendance_summary(db: Session, *, business_date: date, workshop_id: int | None) -> dict[tuple[int, int], dict]:
    summary: dict[tuple[int, int], dict] = {}

    confirmation_query = (
        db.query(ShiftAttendanceConfirmation.workshop_id, ShiftAttendanceConfirmation.shift_id, ShiftAttendanceConfirmation.status)
        .filter(ShiftAttendanceConfirmation.business_date == business_date)
    )
    if workshop_id is not None:
        confirmation_query = confirmation_query.filter(ShiftAttendanceConfirmation.workshop_id == workshop_id)
    confirmation_rows = confirmation_query.all()

    detail_query = (
        db.query(EmployeeAttendanceDetail, ShiftAttendanceConfirmation, ShiftConfig)
        .join(ShiftAttendanceConfirmation, ShiftAttendanceConfirmation.id == EmployeeAttendanceDetail.confirmation_id)
        .join(ShiftConfig, ShiftConfig.id == ShiftAttendanceConfirmation.shift_id)
        .filter(ShiftAttendanceConfirmation.business_date == business_date)
    )
    if workshop_id is not None:
        detail_query = detail_query.filter(ShiftAttendanceConfirmation.workshop_id == workshop_id)

    anomaly_map: dict[tuple[int, int], int] = {}
    for detail, confirmation, shift in detail_query.all():
        auto = attendance_confirm_service.calculate_auto_status(
            shift=shift,
            business_date=confirmation.business_date,
            clock_in=detail.dingtalk_clock_in,
            clock_out=detail.dingtalk_clock_out,
        )
        if detail.leader_status == auto['status']:
            continue
        key = (confirmation.workshop_id, confirmation.shift_id)
        anomaly_map[key] = int(anomaly_map.get(key, 0)) + 1

    for row in confirmation_rows:
        key = (row.workshop_id, row.shift_id)
        exception_count = int(anomaly_map.get(key, 0))
        summary[key] = {
            'status': 'confirmed' if row.status in {'confirmed', 'hr_reviewed'} and exception_count == 0 else 'pending',
            'exception_count': exception_count,
        }

    schedule_query = (
        db.query(AttendanceSchedule.workshop_id, AttendanceSchedule.shift_config_id)
        .filter(AttendanceSchedule.business_date == business_date)
    )
    if workshop_id is not None:
        schedule_query = schedule_query.filter(AttendanceSchedule.workshop_id == workshop_id)
    for row in schedule_query.group_by(AttendanceSchedule.workshop_id, AttendanceSchedule.shift_config_id).all():
        summary.setdefault((row.workshop_id, row.shift_config_id), {'status': 'not_started', 'exception_count': 0})
    return summary


def _build_expected_count_map(db: Session, *, business_date: date, workshop_id: int | None) -> dict[tuple[int, int, int], int]:
    planned_counts = _build_planned_count_map(db, business_date=business_date, workshop_id=workshop_id)
    query = (
        db.query(
            WorkOrderEntry.workshop_id,
            WorkOrderEntry.machine_id,
            WorkOrderEntry.shift_id,
            func.count(WorkOrderEntry.id).label('entry_count'),
            func.count(func.distinct(WorkOrderEntry.business_date)).label('day_count'),
        )
        .filter(
            WorkOrderEntry.business_date >= business_date - timedelta(days=14),
            WorkOrderEntry.business_date < business_date,
            WorkOrderEntry.machine_id.is_not(None),
            WorkOrderEntry.shift_id.is_not(None),
        )
        .group_by(WorkOrderEntry.workshop_id, WorkOrderEntry.machine_id, WorkOrderEntry.shift_id)
    )
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)

    payload: dict[tuple[int, int, int], int] = {}
    for row in query.all():
        day_count = max(int(row.day_count or 0), 1)
        average_count = round(int(row.entry_count or 0) / day_count)
        payload[(row.workshop_id, row.machine_id, row.shift_id)] = max(average_count, 1)
    planned_counts.update({key: value for key, value in payload.items() if key not in planned_counts})
    return planned_counts


def _build_planned_count_map(db: Session, *, business_date: date, workshop_id: int | None) -> dict[tuple[int, int, int], int]:
    # The current schema does not yet include machine+shift production targets.
    # This hook preserves the plan-first contract so a dedicated plan source can be
    # dropped in without changing the aggregation API or frontend behavior.
    del db, business_date, workshop_id
    return {}


def build_live_aggregation(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
    current_user: User,
) -> dict:
    scoped_workshop_id = _resolve_workshop_filter(current_user=current_user, workshop_id=workshop_id)
    workshops_query = db.query(Workshop).filter(Workshop.is_active.is_(True))
    if scoped_workshop_id is not None:
        workshops_query = workshops_query.filter(Workshop.id == scoped_workshop_id)
    workshops = workshops_query.order_by(Workshop.sort_order.asc(), Workshop.id.asc()).all()
    workshop_ids = [item.id for item in workshops]

    machines_query = db.query(Equipment).filter(Equipment.is_active.is_(True))
    if workshop_ids:
        machines_query = machines_query.filter(Equipment.workshop_id.in_(workshop_ids))
    else:
        machines_query = machines_query.filter(Equipment.id == -1)

    machines = machines_query.order_by(Equipment.id.asc()).all()
    shifts = db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).order_by(ShiftConfig.sort_order.asc(), ShiftConfig.id.asc()).all()
    entry_rows = _load_entry_rows(db, business_date=business_date, workshop_id=scoped_workshop_id)
    local_machines, local_entries = _build_local_shift_runtime_inputs(
        machines=machines,
        shifts=shifts,
        rows=_load_local_shift_rows(db, business_date=business_date, workshop_id=scoped_workshop_id),
    )
    local_entries = _drop_local_entries_for_existing_cells(entry_rows, local_entries)
    fill_tracking_cards = {
        _tracking_card_key(item.get('tracking_card_no'))
        for item in [*entry_rows, *local_entries]
        if _tracking_card_key(item.get('tracking_card_no'))
    }
    mes_rows = _load_mes_snapshot_rows(
        db,
        business_date=business_date,
        workshop_id=scoped_workshop_id,
        tracking_card_nos=fill_tracking_cards,
    )
    machines = local_machines
    entries, data_source = _merge_runtime_entries(
        entry_rows=entry_rows,
        local_entries=local_entries,
        mes_rows=mes_rows,
    )
    payload = aggregate_live_payload(
        workshops=workshops,
        machines=machines,
        shifts=shifts,
        entries=entries,
        attendance=_build_attendance_summary(db, business_date=business_date, workshop_id=scoped_workshop_id),
        expected_counts=_build_expected_count_map(db, business_date=business_date, workshop_id=scoped_workshop_id),
    )
    payload = _apply_yield_matrix_authority(
        payload,
        workshops=workshops,
        yield_matrix_lane=build_yield_matrix_projection(db, target_date=business_date),
    )
    payload['business_date'] = business_date.isoformat()
    payload['mes_sync_status'] = mes_sync_service.latest_sync_status(db)
    payload['data_source'] = data_source
    return payload


def build_live_cell_detail(
    db: Session,
    *,
    business_date: date,
    workshop_id: int,
    machine_id: int,
    shift_id: int,
    current_user: User,
) -> dict:
    scoped_workshop_id = _resolve_workshop_filter(current_user=current_user, workshop_id=workshop_id)
    workshop = db.get(Workshop, scoped_workshop_id)
    machine = db.get(Equipment, machine_id)
    shift = db.get(ShiftConfig, shift_id)
    workshop_code = str(workshop.code or '').strip().upper() if workshop and workshop.code else ''
    machine_code = str(machine.code or '').strip().upper() if machine and machine.code else ''
    shift_code = str(shift.code or '').strip().upper() if shift and shift.code else ''
    mes_items = []
    if workshop_code and machine_code and shift_code:
        mes_query = db.query(MesCoilSnapshot).filter(
            MesCoilSnapshot.workshop_code == workshop_code,
            MesCoilSnapshot.machine_code == machine_code,
            MesCoilSnapshot.shift_code == shift_code,
        ).order_by(MesCoilSnapshot.updated_from_mes_at.desc().nullslast(), MesCoilSnapshot.id.desc())
        work_order_by_card = {
            str(item.tracking_card_no or '').strip().upper(): item
            for item in db.query(WorkOrder).all()
            if item.tracking_card_no
        }
        for item in mes_query.all():
            snapshot_date = item.business_date or (item.event_time.date() if item.event_time else None)
            if snapshot_date != business_date:
                continue
            source_payload = dict(item.source_payload or {})
            metadata = dict(source_payload.get('metadata') or {})
            tracking_card_no = str(item.tracking_card_no or '').strip().upper()
            work_order = work_order_by_card.get(tracking_card_no)
            mes_items.append(
                {
                    'tracking_card_no': tracking_card_no,
                    'entry_id': item.id,
                    'work_order_id': work_order.id if work_order else None,
                    'entry_status': item.status or 'synced',
                    'entry_type': 'mes_projection',
                    'input_weight': _to_float(source_payload.get('input_weight') or metadata.get('input_weight')),
                    'output_weight': _to_float(source_payload.get('output_weight') or metadata.get('output_weight')),
                    'scrap_weight': _to_float(source_payload.get('scrap_weight') or metadata.get('scrap_weight')),
                    'yield_rate': None,
                    'yield_rate_source': 'mes_projection',
                    'machine_id': machine_id,
                    'shift_id': shift_id,
                }
            )
    if mes_items:
        return {
            'business_date': business_date.isoformat(),
            'workshop_id': scoped_workshop_id,
            'machine_id': machine_id,
            'shift_id': shift_id,
            'items': mes_items,
        }

    query = (
        db.query(WorkOrderEntry, WorkOrder)
        .join(WorkOrder, WorkOrder.id == WorkOrderEntry.work_order_id)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.workshop_id == scoped_workshop_id,
            WorkOrderEntry.machine_id == machine_id,
            WorkOrderEntry.shift_id == shift_id,
        )
        .order_by(WorkOrderEntry.id.desc())
    )
    return {
        'business_date': business_date.isoformat(),
        'workshop_id': scoped_workshop_id,
        'machine_id': machine_id,
        'shift_id': shift_id,
        'items': [
            {
                'tracking_card_no': work_order.tracking_card_no,
                'entry_id': entry.id,
                'work_order_id': entry.work_order_id,
                'entry_status': entry.entry_status,
                'entry_type': entry.entry_type,
                'input_weight': _prefer_number(entry.verified_input_weight, entry.input_weight),
                'output_weight': _prefer_number(entry.verified_output_weight, entry.output_weight),
                'scrap_weight': _to_float(entry.scrap_weight),
                'yield_rate': float(entry.yield_rate) if entry.yield_rate is not None else _round_rate(
                    _prefer_number(entry.verified_input_weight, entry.input_weight),
                    _prefer_number(entry.verified_output_weight, entry.output_weight),
                ),
                'yield_rate_source': 'runtime_compat',
                'machine_id': entry.machine_id,
                'shift_id': entry.shift_id,
            }
            for entry, work_order in query.all()
        ],
    }
