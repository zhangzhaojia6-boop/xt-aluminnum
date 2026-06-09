from __future__ import annotations

from collections import Counter
from datetime import date, time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry

WEIGHT_TOLERANCE_KG = 1.0
SHIFT_WINDOWS = (
    ('长白班', '07:30-15:30', time(7, 30), time(15, 30)),
    ('小夜班', '15:30-23:30', time(15, 30), time(23, 30)),
)


def _plain_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or '').strip()


def _shift_meta_for_end_time(value: Any) -> dict[str, str | None]:
    if value is None:
        return {'shift_name': None, 'shift_window': None, 'mes_end_time': None}
    end_time = value.time()
    for shift_name, shift_window, start, end in SHIFT_WINDOWS:
        if start <= end_time < end:
            return {'shift_name': shift_name, 'shift_window': shift_window, 'mes_end_time': value.isoformat()}
    return {'shift_name': '大夜班', 'shift_window': '23:30-07:30', 'mes_end_time': value.isoformat()}


def _snapshot_by_batch(db: Session) -> dict[str, MesCoilSnapshot]:
    rows = db.query(MesCoilSnapshot).order_by(MesCoilSnapshot.updated_from_mes_at.desc(), MesCoilSnapshot.id.desc()).all()
    payload: dict[str, MesCoilSnapshot] = {}
    for row in rows:
        batch_no = _text(row.batch_no)
        if batch_no and batch_no not in payload:
            payload[batch_no] = row
    return payload


def _workshop_maps(db: Session) -> tuple[dict[int, Workshop], dict[str, Workshop]]:
    rows = db.query(Workshop).filter(Workshop.is_active.is_(True)).all()
    by_id = {row.id: row for row in rows}
    by_name = {_text(row.name): row for row in rows if _text(row.name)}
    by_name.update({_text(row.code): row for row in rows if _text(row.code)})
    return by_id, by_name


def _machine_name_map(db: Session) -> dict[int, str]:
    return {row.id: row.name for row in db.query(Equipment).filter(Equipment.is_active.is_(True)).all()}


def _entries_by_tracking_card(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
) -> dict[str, list[tuple[WorkOrderEntry, WorkOrder]]]:
    query = (
        db.query(WorkOrderEntry, WorkOrder)
        .join(WorkOrder, WorkOrder.id == WorkOrderEntry.work_order_id)
        .filter(WorkOrderEntry.business_date == business_date)
    )
    if workshop_id is not None:
        query = query.filter(WorkOrderEntry.workshop_id == workshop_id)

    payload: dict[str, list[tuple[WorkOrderEntry, WorkOrder]]] = {}
    for entry, work_order in query.order_by(WorkOrderEntry.id.desc()).all():
        key = _text(work_order.tracking_card_no)
        if key:
            payload.setdefault(key, []).append((entry, work_order))
    return payload


def _resolve_workshop(
    *,
    process: MesWorkshopProcessRecord,
    snapshot: MesCoilSnapshot | None,
    workshop_by_name: dict[str, Workshop],
) -> Workshop | None:
    for value in (
        process.workshop_name,
        snapshot.current_workshop if snapshot is not None else None,
        snapshot.workshop_code if snapshot is not None else None,
    ):
        workshop = workshop_by_name.get(_text(value))
        if workshop is not None:
            return workshop
    return None


def _pick_local_entry(
    rows: list[tuple[WorkOrderEntry, WorkOrder]],
    *,
    workshop_id: int | None,
) -> WorkOrderEntry | None:
    if not rows:
        return None
    if workshop_id is None:
        return rows[0][0]
    return next((entry for entry, _work_order in rows if entry.workshop_id == workshop_id), None)


def _status_for(process: MesWorkshopProcessRecord, snapshot: MesCoilSnapshot | None, entry: WorkOrderEntry | None) -> str:
    if snapshot is None:
        return 'mes_batch_unmapped'
    if entry is None:
        return 'missing_local_entry'
    if entry.machine_id is None:
        return 'local_entry_unassigned'
    mes_output = _plain_number(process.output_weight_kg)
    local_output = _plain_number(entry.output_weight)
    if mes_output is not None and local_output is not None and abs(mes_output - local_output) > WEIGHT_TOLERANCE_KG:
        return 'weight_mismatch'
    return 'matched'


def build_mes_fill_gaps(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None = None,
) -> dict[str, Any]:
    _workshops_by_id, workshop_by_name = _workshop_maps(db)
    machine_names = _machine_name_map(db)
    snapshots = _snapshot_by_batch(db)
    entries = _entries_by_tracking_card(db, business_date=business_date, workshop_id=workshop_id)

    process_query = db.query(MesWorkshopProcessRecord).filter(MesWorkshopProcessRecord.business_date == business_date)
    process_rows = process_query.order_by(MesWorkshopProcessRecord.end_time.asc(), MesWorkshopProcessRecord.id.asc()).all()

    items: list[dict[str, Any]] = []
    for process in process_rows:
        snapshot = snapshots.get(_text(process.batch_no))
        workshop = _resolve_workshop(process=process, snapshot=snapshot, workshop_by_name=workshop_by_name)
        resolved_workshop_id = workshop.id if workshop is not None else None
        if workshop_id is not None and resolved_workshop_id != workshop_id:
            continue

        tracking_card_no = _text(snapshot.tracking_card_no) if snapshot is not None else None
        local_entry = _pick_local_entry(entries.get(tracking_card_no or '', []), workshop_id=resolved_workshop_id)
        status = _status_for(process, snapshot, local_entry)
        local_machine_name = machine_names.get(local_entry.machine_id) if local_entry is not None and local_entry.machine_id is not None else None
        shift_meta = _shift_meta_for_end_time(process.end_time)

        items.append(
            {
                'status': status,
                'workshop_id': resolved_workshop_id,
                'workshop_name': workshop.name if workshop is not None else _text(process.workshop_name) or None,
                'process_name': process.process_name,
                'batch_no': process.batch_no,
                'tracking_card_no': tracking_card_no,
                'local_entry_id': local_entry.id if local_entry is not None else None,
                'mes_input_weight': _plain_number(process.input_weight_kg),
                'mes_output_weight': _plain_number(process.output_weight_kg),
                'local_input_weight': _plain_number(local_entry.input_weight) if local_entry is not None else None,
                'local_output_weight': _plain_number(local_entry.output_weight) if local_entry is not None else None,
                'mes_machine_name': process.device_name,
                'local_machine_name': local_machine_name,
                **shift_meta,
            }
        )

    counts = Counter(item['status'] for item in items)
    return {
        'business_date': business_date.isoformat(),
        'workshop_id': workshop_id,
        'total': len(items),
        'summary': {
            'total': len(items),
            'status_counts': dict(counts),
        },
        'items': items,
    }
