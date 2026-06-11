from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.master import Equipment, MasterCodeAlias
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.system import User
from app.services import mes_machine_match_service
from app.services.equipment_service import get_reporting_machine_for_user
from app.utils.tracking_cards import tracking_card_lookup_candidates

LOCAL_TZ = ZoneInfo(settings.DEFAULT_TIMEZONE)
SUPPLEMENT_BUSINESS_DAY_START = time(9, 30)


def _text(value: Any) -> str:
    return str(value or '').strip()


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _batch_lookup_keys(value: Any) -> list[str]:
    text = _text(value).upper()
    if not text:
        return []
    keys = [text]
    if '-' in text:
        base = text.rsplit('-', 1)[0]
        if base and base != text:
            keys.append(base)
    return keys


def resolve_supplement_business_date(now: datetime | None = None) -> date:
    current = now.astimezone(LOCAL_TZ) if now is not None and now.tzinfo else (now or datetime.now(LOCAL_TZ))
    if current.time() < SUPPLEMENT_BUSINESS_DAY_START:
        return current.date() - timedelta(days=1)
    return current.date()


def _window_for_business_date(business_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(business_date, SUPPLEMENT_BUSINESS_DAY_START, tzinfo=LOCAL_TZ)
    return start, start + timedelta(days=1)


def _snapshot_by_batch(db: Session, values: list[Any]) -> dict[str, MesCoilSnapshot]:
    keys: set[str] = set()
    for value in values:
        keys.update(_batch_lookup_keys(value))
    if not keys:
        return {}
    rows = (
        db.query(MesCoilSnapshot)
        .filter(
            or_(
                MesCoilSnapshot.batch_no.in_(keys),
                MesCoilSnapshot.tracking_card_no.in_(keys),
                MesCoilSnapshot.material_code.in_(keys),
            )
        )
        .order_by(MesCoilSnapshot.updated_from_mes_at.desc(), MesCoilSnapshot.id.desc())
        .all()
    )
    payload: dict[str, MesCoilSnapshot] = {}
    for row in rows:
        for value in (row.batch_no, row.tracking_card_no, row.material_code):
            for key in _batch_lookup_keys(value):
                payload.setdefault(key, row)
    return payload


def _snapshot_for_process(
    process: MesWorkshopProcessRecord,
    snapshots: dict[str, MesCoilSnapshot],
) -> MesCoilSnapshot | None:
    return next((snapshots.get(key) for key in _batch_lookup_keys(process.batch_no) if snapshots.get(key)), None)


def _tracking_keys(*values: Any) -> set[str]:
    keys: set[str] = set()
    for value in values:
        keys.update(tracking_card_lookup_candidates(value))
    return keys


def _completed_refs(
    db: Session,
    *,
    business_date: date,
    machine_id: int,
) -> tuple[set[str], set[str], set[tuple[str, int]]]:
    rows = (
        db.query(WorkOrderEntry, WorkOrder)
        .join(WorkOrder, WorkOrder.id == WorkOrderEntry.work_order_id)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.machine_id == machine_id,
            WorkOrderEntry.entry_type == 'mobile_coil',
            WorkOrderEntry.entry_status != 'voided',
        )
        .all()
    )
    process_ids: set[str] = set()
    source_ids: set[str] = set()
    tracking_output_keys: set[tuple[str, int]] = set()
    for entry, work_order in rows:
        extra_payload = dict(entry.extra_payload or {})
        mes_ref = dict(extra_payload.get('mes_reference') or {})
        for value in (mes_ref.get('process_record_id'), mes_ref.get('mes_process_record_id')):
            if value not in (None, ''):
                process_ids.add(str(value))
        if mes_ref.get('source_id') not in (None, ''):
            source_ids.add(str(mes_ref.get('source_id')))
        if entry.output_weight is None:
            continue
        output_key = int(round(float(entry.output_weight)))
        for tracking_key in _tracking_keys(work_order.tracking_card_no):
            tracking_output_keys.add((tracking_key, output_key))
    return process_ids, source_ids, tracking_output_keys


def _is_completed(
    process: MesWorkshopProcessRecord,
    *,
    snapshot: MesCoilSnapshot | None,
    process_ids: set[str],
    source_ids: set[str],
    tracking_output_keys: set[tuple[str, int]],
) -> bool:
    if str(process.id) in process_ids or str(process.source_id) in source_ids:
        return True
    if process.output_weight_kg is None:
        return False
    output_key = int(round(float(process.output_weight_kg)))
    for tracking_key in _tracking_keys(
        snapshot.tracking_card_no if snapshot else None,
        snapshot.batch_no if snapshot else None,
        process.batch_no,
    ):
        if (tracking_key, output_key) in tracking_output_keys:
            return True
    return False


def _process_rows(db: Session, *, business_date: date) -> list[MesWorkshopProcessRecord]:
    start, end = _window_for_business_date(business_date)
    return (
        db.query(MesWorkshopProcessRecord)
        .filter(
            or_(
                and_(MesWorkshopProcessRecord.end_time >= start, MesWorkshopProcessRecord.end_time < end),
                and_(MesWorkshopProcessRecord.end_time.is_(None), MesWorkshopProcessRecord.business_date == business_date),
            )
        )
        .order_by(MesWorkshopProcessRecord.end_time.asc(), MesWorkshopProcessRecord.id.asc())
        .all()
    )


def _process_text(process: MesWorkshopProcessRecord) -> str:
    return f'{process.workshop_name or ""} {process.process_name or ""}'


def _is_cold_roll_process(process: MesWorkshopProcessRecord) -> bool:
    text = _process_text(process)
    return any(keyword in text for keyword in ('冷轧', '开坯', '中退'))


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


def _sequence_sort_key(row: MesWorkshopProcessRecord) -> tuple[datetime, int]:
    value = row.end_time
    if value is None:
        return datetime.min, row.id
    if value.tzinfo is not None:
        value = value.astimezone(LOCAL_TZ).replace(tzinfo=None)
    return value, row.id


def _build_process_sequence_map(
    process_rows: list[MesWorkshopProcessRecord],
    snapshots: dict[str, MesCoilSnapshot],
) -> dict[int, dict[str, Any]]:
    groups: dict[str, list[MesWorkshopProcessRecord]] = {}
    for process in process_rows:
        if not _is_cold_roll_process(process):
            continue
        key = _process_sequence_key(process, _snapshot_for_process(process, snapshots))
        if not key:
            continue
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


def _build_material_reference(
    process: MesWorkshopProcessRecord,
    snapshot: MesCoilSnapshot | None,
) -> dict[str, Any]:
    if snapshot is None:
        return {
            'material_category': _material_category(process),
            'batch_no': process.batch_no,
        }
    return {
        'material_category': _material_category(process),
        'material_code': snapshot.material_code,
        'coil_id': snapshot.coil_id,
        'batch_no': snapshot.batch_no or process.batch_no,
        'current_workshop': snapshot.current_workshop,
        'current_process': snapshot.current_process,
        'next_workshop': snapshot.next_workshop,
        'next_process': snapshot.next_process,
        'process_route_text': snapshot.process_route_text,
    }


def _risk_flags(snapshot: MesCoilSnapshot | None, binding: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if snapshot is None:
        flags.append('mes_batch_unmapped')
    if binding.get('confidence') in {'medium', 'low'}:
        flags.append('machine_match_needs_confirmation')
    return flags


def _build_mes_reference(
    process: MesWorkshopProcessRecord,
    snapshot: MesCoilSnapshot | None,
    binding: dict[str, Any],
    *,
    process_sequence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'process_record_id': process.id,
        'source_id': process.source_id,
        'batch_no': process.batch_no,
        'tracking_card_no': snapshot.tracking_card_no if snapshot else None,
        'material_code': snapshot.material_code if snapshot else None,
        'mes_machine_name': process.device_name,
        'mes_worker_name': process.worker_name,
        'resolved_machine_id': binding['machine_id'],
        'resolved_machine_name': binding['machine_name'],
        'machine_binding_source': binding['source'],
        'machine_binding_confidence': binding['confidence'],
        'mes_end_time': process.end_time.isoformat() if process.end_time else None,
        'material_reference': _build_material_reference(process, snapshot),
        'process_sequence': process_sequence,
    }


def build_pending_supplements(
    db: Session,
    *,
    current_user: User,
    business_date: date | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    resolved_business_date = business_date or resolve_supplement_business_date()
    machine = get_reporting_machine_for_user(db, user_id=current_user.id)
    if machine is None:
        return {
            'business_date': resolved_business_date.isoformat(),
            'business_day_start': '09:30',
            'is_machine_bound': False,
            'machine': None,
            'summary': {
                'total_mes_records': 0,
                'matched_machine_count': 0,
                'pending_count': 0,
                'completed_count': 0,
                'unmatched_machine_count': 0,
            },
            'items': [],
        }

    machines = db.query(Equipment).filter(Equipment.is_active.is_(True)).all()
    aliases = (
        db.query(MasterCodeAlias)
        .filter(MasterCodeAlias.entity_type == 'equipment', MasterCodeAlias.is_active.is_(True))
        .all()
    )
    process_rows = _process_rows(db, business_date=resolved_business_date)
    snapshots = _snapshot_by_batch(db, [process.batch_no for process in process_rows])
    process_sequences = _build_process_sequence_map(process_rows, snapshots)
    completed_process_ids, completed_source_ids, completed_tracking_output = _completed_refs(
        db,
        business_date=resolved_business_date,
        machine_id=machine.id,
    )

    items: list[dict[str, Any]] = []
    completed_count = 0
    matched_machine_count = 0
    unmatched_machine_count = 0
    for process in process_rows:
        snapshot = _snapshot_for_process(process, snapshots)
        binding = mes_machine_match_service.resolve_mes_machine_binding(
            machines=machines,
            aliases=aliases,
            device_name=process.device_name,
            process_hint=process.process_name,
            preferred_workshop_id=machine.workshop_id,
        )
        if binding['machine_id'] is None:
            unmatched_machine_count += 1
            continue
        if int(binding['machine_id']) != int(machine.id):
            continue
        matched_machine_count += 1
        if _is_completed(
            process,
            snapshot=snapshot,
            process_ids=completed_process_ids,
            source_ids=completed_source_ids,
            tracking_output_keys=completed_tracking_output,
        ):
            completed_count += 1
            continue

        source_payload = dict(process.source_payload or {})
        process_sequence = process_sequences.get(process.id)
        material_reference = _build_material_reference(process, snapshot)
        items.append(
            {
                'mes_process_record_id': process.id,
                'mes_source_id': process.source_id,
                'batch_no': process.batch_no,
                'tracking_card_no': snapshot.tracking_card_no if snapshot else None,
                'material_code': snapshot.material_code if snapshot else None,
                'material_category': material_reference['material_category'],
                'material_reference': material_reference,
                'process_sequence': process_sequence,
                'customer_alias': process.customer_alias or (snapshot.customer_alias if snapshot else None),
                'alloy_grade': snapshot.alloy_grade if snapshot else None,
                'input_spec': source_payload.get('BeginSpecification') or (snapshot.spec_display if snapshot else None),
                'output_spec': source_payload.get('EndSpecification'),
                'material_state': snapshot.material_state if snapshot else None,
                'workshop_name': process.workshop_name,
                'process_name': process.process_name,
                'mes_machine_name': process.device_name,
                'resolved_machine_id': binding['machine_id'],
                'resolved_machine_name': binding['machine_name'],
                'machine_binding_source': binding['source'],
                'machine_binding_confidence': binding['confidence'],
                'input_weight_kg': _plain(process.input_weight_kg),
                'output_weight_kg': _plain(process.output_weight_kg),
                'end_time': process.end_time.isoformat() if process.end_time else None,
                'supplement_status': 'pending',
                'risk_flags': _risk_flags(snapshot, binding),
                'mes_reference': _build_mes_reference(
                    process,
                    snapshot,
                    binding,
                    process_sequence=process_sequence,
                ),
            }
        )
        if len(items) >= max(1, min(limit, 200)):
            break

    return {
        'business_date': resolved_business_date.isoformat(),
        'business_day_start': '09:30',
        'is_machine_bound': True,
        'machine': {
            'machine_id': machine.id,
            'machine_code': machine.code,
            'machine_name': machine.name,
            'workshop_id': machine.workshop_id,
        },
        'summary': {
            'total_mes_records': len(process_rows),
            'matched_machine_count': matched_machine_count,
            'pending_count': len(items),
            'completed_count': completed_count,
            'unmatched_machine_count': unmatched_machine_count,
        },
        'items': items,
    }
