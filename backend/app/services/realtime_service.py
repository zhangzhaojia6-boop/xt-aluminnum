from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.scope import (
    build_scope_summary,
    can_view_all_work_order_entries,
    can_view_work_order_entries,
    resolve_work_order_entry_workshop_scope,
)
from app.models.attendance import AttendanceSchedule, EmployeeAttendanceDetail, ShiftAttendanceConfirmation
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import attendance_confirm_service
from app.services import mes_sync_service
from app.services.yield_matrix_canonical_service import build_yield_matrix_projection


def _to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _round_rate(input_total: float, output_total: float) -> float | None:
    if input_total <= 0:
        return None
    return round((output_total / input_total) * 100, 2)


def _prefer_number(primary: Decimal | float | int | None, fallback: Decimal | float | int | None) -> float:
    if primary is not None:
        return _to_float(primary)
    return _to_float(fallback)


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

    workshop_items: list[dict] = []
    submitted_cells = 0
    total_cells = 0
    factory_input = 0.0
    factory_output = 0.0
    factory_scrap = 0.0
    ordered_shifts = sorted(shifts, key=lambda item: (getattr(item, 'sort_order', 0), item.id))

    for workshop in sorted(workshops, key=lambda item: item.id):
        workshop_input = 0.0
        workshop_output = 0.0
        workshop_scrap = 0.0
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
                attendance_state = attendance.get((workshop.id, shift.id), {'status': 'not_started', 'exception_count': 0})
                if not is_applicable:
                    shift_items.append(
                        {
                            'shift_id': shift.id,
                            'shift_name': shift.name,
                            'submitted_count': 0,
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
                        }
                    )
                    continue

                total_cells += 1
                rows = cell_entries.get((workshop.id, machine.id, shift.id), [])
                submitted_count = len(
                    [
                        item
                        for item in rows
                        if item.get('entry_status') in {'submitted', 'verified', 'approved'}
                        or item.get('entry_type') == 'mes_projection'
                    ]
                )
                total_count = len(rows)
                input_total = round(sum(_to_float(item.get('input_weight')) for item in rows), 2)
                output_total = round(sum(_to_float(item.get('output_weight')) for item in rows), 2)
                scrap_total = round(sum(_to_float(item.get('scrap_weight')) for item in rows), 2)
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

                machine_input += input_total
                machine_output += output_total
                machine_scrap += scrap_total
                shift_items.append(
                    {
                        'shift_id': shift.id,
                        'shift_name': shift.name,
                        'submitted_count': submitted_count,
                        'total_expected': expected_total,
                        'total_input': input_total,
                        'total_output': output_total,
                        'total_scrap': scrap_total,
                        'yield_rate': _round_rate(input_total, output_total),
                        'yield_rate_source': 'runtime_compat',
                        'attendance_status': attendance_state['status'],
                        'attendance_exception_count': int(attendance_state.get('exception_count', 0)),
                        'submission_status': submission_status,
                        'is_applicable': True,
                    }
                )

            workshop_input += machine_input
            workshop_output += machine_output
            workshop_scrap += machine_scrap
            machine_items.append(
                {
                    'machine_id': machine.id,
                    'machine_name': machine.name,
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
                },
            }
        )

    return {
        'overall_progress': {'submitted_cells': submitted_cells, 'total_cells': total_cells},
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
            'tracking_card_status': work_order.overall_status,
        }
        for entry, work_order in query.all()
    ]


def _load_mes_snapshot_rows(db: Session, *, business_date: date, workshop_id: int | None) -> list[dict]:
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

    query = db.query(MesCoilSnapshot)
    snapshots = []
    for item in query.all():
        snapshot_date = item.business_date or (item.event_time.date() if item.event_time else None)
        if snapshot_date != business_date:
            continue
        snapshot_workshop_id = workshop_id_by_code.get(str(item.workshop_code or '').strip().upper())
        if workshop_id is not None and snapshot_workshop_id != workshop_id:
            continue
        snapshots.append(item)

    payload: list[dict] = []
    for item in snapshots:
        source_payload = dict(item.source_payload or {})
        metadata = dict(source_payload.get('metadata') or {})
        tracking_card_no = str(item.tracking_card_no or '').strip().upper()
        work_order = work_order_by_card.get(tracking_card_no)
        resolved_workshop_id = workshop_id_by_code.get(str(item.workshop_code or '').strip().upper())
        resolved_machine_id = machine_id_by_code.get(str(item.machine_code or '').strip().upper())
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

    mes_rows = _load_mes_snapshot_rows(db, business_date=business_date, workshop_id=scoped_workshop_id)
    payload = aggregate_live_payload(
        workshops=workshops,
        machines=machines_query.order_by(Equipment.id.asc()).all(),
        shifts=db.query(ShiftConfig).filter(ShiftConfig.is_active.is_(True)).order_by(ShiftConfig.sort_order.asc(), ShiftConfig.id.asc()).all(),
        entries=mes_rows or _load_entry_rows(db, business_date=business_date, workshop_id=scoped_workshop_id),
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
    payload['data_source'] = 'mes_projection' if mes_rows else 'work_order_runtime'
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
