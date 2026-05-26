from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.production import WorkOrderEntry
from app.models.master import Equipment, Workshop
from app.models.shift import ShiftConfig


def _row_pass_count(extra: dict | None) -> int:
    if not isinstance(extra, dict):
        return 0
    raw = extra.get('pass_count')
    if raw in (None, ''):
        return 0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0
    if value <= 0:
        return 0
    return int(value)


def build_shift_pass_count(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None = None,
) -> dict[str, Any]:
    query = db.query(WorkOrderEntry).filter(
        WorkOrderEntry.business_date == business_date,
        WorkOrderEntry.entry_type == 'mobile_coil',
    )
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)

    workshops = {w.id: w for w in db.query(Workshop).all()}
    machines = {m.id: m for m in db.query(Equipment).all()}
    shifts = {s.id: s for s in db.query(ShiftConfig).all()}

    buckets: dict[tuple[int, int | None, int | None], dict[str, Any]] = {}
    for entry in query.all():
        passes = _row_pass_count(entry.extra_payload)
        if passes <= 0:
            continue
        key = (entry.workshop_id, entry.machine_id, entry.shift_id)
        bucket = buckets.setdefault(
            key,
            {
                'workshop_id': entry.workshop_id,
                'workshop_name': workshops.get(entry.workshop_id).name if workshops.get(entry.workshop_id) else None,
                'machine_id': entry.machine_id,
                'machine_name': machines.get(entry.machine_id).name if entry.machine_id and machines.get(entry.machine_id) else None,
                'shift_id': entry.shift_id,
                'shift_name': shifts.get(entry.shift_id).name if entry.shift_id and shifts.get(entry.shift_id) else None,
                'pass_count_total': 0,
                'coil_count': 0,
            },
        )
        bucket['pass_count_total'] += passes
        bucket['coil_count'] += 1

    items = sorted(
        buckets.values(),
        key=lambda r: (r['workshop_id'] or 0, r['machine_id'] or 0, r['shift_id'] or 0),
    )
    total_passes = sum(item['pass_count_total'] for item in items)
    total_coils = sum(item['coil_count'] for item in items)
    return {
        'business_date': business_date.isoformat(),
        'workshop_id': workshop_id,
        'items': items,
        'totals': {
            'pass_count_total': total_passes,
            'coil_count': total_coils,
        },
    }


def build_monthly_pass_count(
    db: Session,
    *,
    year: int,
    month: int,
    workshop_id: int | None = None,
) -> dict[str, Any]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    query = db.query(WorkOrderEntry).filter(
        WorkOrderEntry.business_date >= start,
        WorkOrderEntry.business_date < end,
        WorkOrderEntry.entry_type == 'mobile_coil',
    )
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)

    workshops = {w.id: w for w in db.query(Workshop).all()}
    machines = {m.id: m for m in db.query(Equipment).all()}

    buckets: dict[tuple[int, int | None], dict[str, Any]] = {}
    for entry in query.all():
        passes = _row_pass_count(entry.extra_payload)
        if passes <= 0:
            continue
        key = (entry.workshop_id, entry.machine_id)
        bucket = buckets.setdefault(
            key,
            {
                'workshop_id': entry.workshop_id,
                'workshop_name': workshops.get(entry.workshop_id).name if workshops.get(entry.workshop_id) else None,
                'machine_id': entry.machine_id,
                'machine_name': machines.get(entry.machine_id).name if entry.machine_id and machines.get(entry.machine_id) else None,
                'pass_count_total': 0,
                'coil_count': 0,
            },
        )
        bucket['pass_count_total'] += passes
        bucket['coil_count'] += 1

    items = sorted(
        buckets.values(),
        key=lambda r: (r['workshop_id'] or 0, r['machine_id'] or 0),
    )
    total_passes = sum(item['pass_count_total'] for item in items)
    total_coils = sum(item['coil_count'] for item in items)
    return {
        'year': year,
        'month': month,
        'workshop_id': workshop_id,
        'items': items,
        'totals': {
            'pass_count_total': total_passes,
            'coil_count': total_coils,
        },
    }
