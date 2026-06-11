from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.master import Equipment, MasterCodeAlias, Workshop
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.services import mes_machine_match_service

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


def _batch_lookup_keys(value: Any) -> list[str]:
    text = _text(value).upper()
    if not text:
        return []
    keys = [text]
    base = re.sub(r'-\d+$', '', text)
    if base and base != text:
        keys.append(base)
    return keys


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
        for value in (row.batch_no, row.tracking_card_no, row.material_code):
            for key in _batch_lookup_keys(value):
                payload.setdefault(key, row)
    return payload


def _workshop_maps(db: Session) -> tuple[dict[int, Workshop], dict[str, Workshop]]:
    rows = db.query(Workshop).filter(Workshop.is_active.is_(True)).all()
    by_id = {row.id: row for row in rows}
    by_name = {_text(row.name): row for row in rows if _text(row.name)}
    by_name.update({_text(row.code): row for row in rows if _text(row.code)})
    return by_id, by_name


def _machine_context(db: Session) -> tuple[dict[int, str], list[Equipment], list[MasterCodeAlias]]:
    machines = db.query(Equipment).filter(Equipment.is_active.is_(True)).all()
    aliases = (
        db.query(MasterCodeAlias)
        .filter(
            MasterCodeAlias.entity_type == 'equipment',
            MasterCodeAlias.is_active.is_(True),
        )
        .all()
    )
    return {row.id: row.name for row in machines}, machines, aliases


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


def _pick_local_entry_for_process(
    entries: dict[str, list[tuple[WorkOrderEntry, WorkOrder]]],
    *,
    tracking_card_no: str | None,
    process_batch_no: str | None,
    workshop_id: int | None,
) -> tuple[WorkOrderEntry | None, str | None]:
    lookup_keys = []
    if tracking_card_no:
        lookup_keys.append(tracking_card_no)
    lookup_keys.extend(_batch_lookup_keys(process_batch_no))

    seen: set[str] = set()
    for key in lookup_keys:
        if key in seen:
            continue
        seen.add(key)
        entry = _pick_local_entry(entries.get(key, []), workshop_id=workshop_id)
        if entry is not None:
            return entry, key
    return None, tracking_card_no


def _status_for(process: MesWorkshopProcessRecord, snapshot: MesCoilSnapshot | None, entry: WorkOrderEntry | None) -> str:
    if snapshot is None and entry is None:
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


def _process_text(process: MesWorkshopProcessRecord) -> str:
    return f'{process.workshop_name or ""} {process.process_name or ""}'


def _is_cold_roll_process(process: MesWorkshopProcessRecord) -> bool:
    return any(keyword in _process_text(process) for keyword in ('冷轧', '开坯', '中退'))


def _material_category(process: MesWorkshopProcessRecord) -> str:
    text = _process_text(process)
    if _is_cold_roll_process(process):
        return 'cold_roll_pass'
    if '热轧' in text:
        return 'hot_roll_process'
    if '铸轧' in text:
        return 'cast_roll_process'
    if '铸锭' in text:
        return 'casting_ingot_reference'
    if '坯' in text:
        return 'billet_reference'
    return 'coil_process'


def _process_sequence_key(process: MesWorkshopProcessRecord, snapshot: MesCoilSnapshot | None) -> str | None:
    for value in (
        snapshot.tracking_card_no if snapshot else None,
        snapshot.batch_no if snapshot else None,
        snapshot.material_code if snapshot else None,
        process.batch_no,
    ):
        keys = _batch_lookup_keys(value)
        if keys:
            return keys[-1]
    return None


def _sequence_sort_key(row: MesWorkshopProcessRecord) -> tuple[Any, int]:
    value = row.end_time
    if value is None:
        return datetime.min, row.id
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value, row.id


def _build_process_sequence_map(
    process_rows: list[MesWorkshopProcessRecord],
    snapshots: dict[str, MesCoilSnapshot],
) -> dict[int, dict[str, Any]]:
    groups: dict[str, list[MesWorkshopProcessRecord]] = {}
    for process in process_rows:
        if not _is_cold_roll_process(process):
            continue
        snapshot = next((snapshots.get(key) for key in _batch_lookup_keys(process.batch_no) if snapshots.get(key)), None)
        key = _process_sequence_key(process, snapshot)
        if key:
            groups.setdefault(key, []).append(process)

    payload: dict[int, dict[str, Any]] = {}
    for rows in groups.values():
        ordered = sorted(rows, key=_sequence_sort_key)
        total = len(ordered)
        for index, row in enumerate(ordered, start=1):
            payload[row.id] = {
                'pass_index': index,
                'pass_total': total,
                'pass_label': f'第{index}道' if total > 1 else '单道次',
                'sequence_source': 'mes_process_time',
            }
    return payload


def _payload_text(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _text(payload.get(key))
        if value:
            return value
    return None


def _gap_cause(status: str, binding: dict[str, Any]) -> str:
    if status == 'mes_batch_unmapped':
        return 'MES批号没有匹配到卷材快照'
    if status == 'missing_local_entry':
        return 'MES已有下机记录，本地补录未完成'
    if status == 'local_entry_unassigned':
        return '本地补录缺少机列归属'
    if status == 'weight_mismatch':
        return 'MES下机重量与本地补录重量超过1kg'
    if binding.get('confidence') in {'medium', 'low'}:
        return 'MES机列匹配可信度偏低，需要人工确认'
    return '已匹配'


def build_mes_fill_gaps(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None = None,
) -> dict[str, Any]:
    workshops_by_id, workshop_by_name = _workshop_maps(db)
    machine_names, machines, equipment_aliases = _machine_context(db)
    snapshots = _snapshot_by_batch(db)
    entries = _entries_by_tracking_card(db, business_date=business_date, workshop_id=workshop_id)

    process_query = db.query(MesWorkshopProcessRecord).filter(MesWorkshopProcessRecord.business_date == business_date)
    process_rows = process_query.order_by(MesWorkshopProcessRecord.end_time.asc(), MesWorkshopProcessRecord.id.asc()).all()
    process_sequences = _build_process_sequence_map(process_rows, snapshots)

    items: list[dict[str, Any]] = []
    for process in process_rows:
        snapshot = next((snapshots.get(key) for key in _batch_lookup_keys(process.batch_no) if snapshots.get(key)), None)
        workshop = _resolve_workshop(process=process, snapshot=snapshot, workshop_by_name=workshop_by_name)
        resolved_workshop_id = workshop.id if workshop is not None else None
        mes_machine = mes_machine_match_service.resolve_mes_machine_binding(
            machines=machines,
            device_name=process.device_name,
            process_hint=process.process_name,
            preferred_workshop_id=resolved_workshop_id,
            aliases=equipment_aliases,
        )
        if mes_machine['workshop_id'] is not None and mes_machine['workshop_id'] != resolved_workshop_id:
            resolved_workshop_id = mes_machine['workshop_id']
            workshop = workshops_by_id.get(resolved_workshop_id)

        if workshop_id is not None and resolved_workshop_id != workshop_id:
            continue

        tracking_card_no = _text(snapshot.tracking_card_no) if snapshot is not None else None
        local_entry, tracking_card_no = _pick_local_entry_for_process(
            entries,
            tracking_card_no=tracking_card_no,
            process_batch_no=process.batch_no,
            workshop_id=resolved_workshop_id,
        )
        status = _status_for(process, snapshot, local_entry)
        local_machine_name = machine_names.get(local_entry.machine_id) if local_entry is not None and local_entry.machine_id is not None else None
        shift_meta = _shift_meta_for_end_time(process.end_time)
        source_payload = dict(process.source_payload or {})

        items.append(
            {
                'status': status,
                'gap_cause': _gap_cause(status, mes_machine),
                'mes_process_record_id': process.id,
                'mes_source_id': process.source_id,
                'workshop_id': resolved_workshop_id,
                'workshop_name': workshop.name if workshop is not None else _text(process.workshop_name) or None,
                'process_name': process.process_name,
                'batch_no': process.batch_no,
                'tracking_card_no': tracking_card_no,
                'customer_alias': process.customer_alias or (snapshot.customer_alias if snapshot is not None else None),
                'alloy_grade': snapshot.alloy_grade if snapshot is not None else None,
                'material_code': snapshot.material_code if snapshot is not None else None,
                'material_state': snapshot.material_state if snapshot is not None else None,
                'material_category': _material_category(process),
                'input_spec': _payload_text(source_payload, 'BeginSpecification', 'InputSpecification') or (
                    snapshot.spec_display if snapshot is not None else None
                ),
                'output_spec': _payload_text(source_payload, 'EndSpecification', 'OutputSpecification'),
                'process_sequence': process_sequences.get(process.id),
                'local_entry_id': local_entry.id if local_entry is not None else None,
                'mes_input_weight': _plain_number(process.input_weight_kg),
                'mes_output_weight': _plain_number(process.output_weight_kg),
                'local_input_weight': _plain_number(local_entry.input_weight) if local_entry is not None else None,
                'local_output_weight': _plain_number(local_entry.output_weight) if local_entry is not None else None,
                'mes_machine_name': process.device_name,
                'mes_worker_name': process.worker_name,
                'mes_last_seen_at': process.last_seen_from_mes_at.isoformat() if process.last_seen_from_mes_at else None,
                'mes_resolved_machine_id': mes_machine['machine_id'],
                'mes_resolved_machine_name': mes_machine['machine_name'],
                'mes_machine_binding_source': mes_machine['source'],
                'mes_machine_binding_confidence': mes_machine['confidence'],
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
