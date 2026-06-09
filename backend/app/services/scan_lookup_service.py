from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect, or_
from sqlalchemy.orm import Session

from app.models.master import Equipment
from app.models.mes import MesCoilSnapshot
from app.services import master_service, mes_assisted_fill_service
from app.services.realtime_service import _infer_mes_machine_id_from_route
from app.utils.tracking_cards import tracking_card_lookup_key, tracking_card_sql_lookup_key


class ScanLookupNotFound(RuntimeError):
    pass


class ScanLookupUnavailable(RuntimeError):
    pass


def _to_plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: _to_plain(value) for key, value in payload.items() if value not in (None, '')}


def _spec_display(row: MesCoilSnapshot) -> str | None:
    if row.spec_display:
        return row.spec_display
    if row.spec_thickness is None and row.spec_width is None:
        return None
    parts = []
    if row.spec_thickness is not None:
        parts.append(str(_to_plain(row.spec_thickness)).rstrip('0').rstrip('.'))
    if row.spec_width is not None:
        parts.append(str(_to_plain(row.spec_width)).rstrip('0').rstrip('.'))
    return '×'.join(parts) if parts else None


def _coil_payload(
    db: Session,
    row: MesCoilSnapshot,
    *,
    source: str,
    tracking_card_no_override: str | None = None,
) -> dict:
    spec_display = _spec_display(row)
    header_fields = _compact(
        {
            'tracking_card_no': tracking_card_no_override or row.tracking_card_no,
            'batch_no': row.batch_no,
            'material_code': row.material_code,
            'alloy_grade': row.alloy_grade,
            'spec_thickness': row.spec_thickness,
            'spec_width': row.spec_width,
            'spec_display': spec_display,
            'input_spec': spec_display,
            'contract_no': row.contract_no,
            'current_workshop': row.current_workshop,
            'current_process': row.current_process,
            'next_workshop': row.next_workshop,
            'next_process': row.next_process,
            'material_weight': row.material_weight,
        }
    )
    assist_identifier = row.qr_code or row.tracking_card_no
    assisted_fields = dict(mes_assisted_fill_service.build_assisted_fill(db, identifier=assist_identifier)['fields'])
    if tracking_card_no_override:
        assisted_fields.pop('tracking_card_no', None)
    header_fields.update(assisted_fields)
    binding = _resolve_machine_binding_for_snapshot(db, row)
    return {
        'source': source,
        'header_fields': header_fields,
        'lock_keys': [],
        'lock_token': None,
        'machine_line_id': binding['machine_line_id'],
        'machine_line_code': binding['machine_line_code'],
        'machine_line_name': binding['machine_line_name'],
        'machine_binding_source': binding['machine_binding_source'],
    }


def _machine_payload(row: Equipment) -> dict:
    header_fields = _compact(
        {
            'equipment_code': row.code,
            'equipment_name': row.name,
            'workshop_id': row.workshop_id,
        }
    )
    return {
        'source': 'machine_identity',
        'header_fields': header_fields,
        'lock_keys': [],
        'lock_token': None,
    }


def _has_coil_snapshot_table(db: Session) -> bool:
    bind = db.get_bind()
    return inspect(bind).has_table(MesCoilSnapshot.__tablename__)


def _safe_resolve_canonical(db: Session, *, entity_type: str, value: object | None) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    try:
        return master_service.resolve_canonical_code(
            db, entity_type=entity_type, value=raw, source_type='mes_mvc'
        ) or raw
    except Exception:
        return raw


def _resolve_machine_binding_for_snapshot(db: Session, row: MesCoilSnapshot) -> dict:
    empty = {
        'machine_line_id': None,
        'machine_line_code': None,
        'machine_line_name': None,
        'machine_binding_source': 'unresolved',
    }

    workshop_rows = db.query(Equipment).filter(Equipment.is_active.is_(True)).all()
    if not workshop_rows:
        return empty

    machine_id_by_code: dict[str, Equipment] = {}
    machines_by_workshop: dict[int, list[Equipment]] = defaultdict(list)
    for machine in workshop_rows:
        if machine.code:
            machine_id_by_code[str(machine.code).strip().upper()] = machine
        if machine.workshop_id is not None:
            machines_by_workshop[machine.workshop_id].append(machine)

    raw_machine_code = _safe_resolve_canonical(db, entity_type='equipment', value=row.machine_code)
    direct = machine_id_by_code.get(raw_machine_code.strip().upper()) if raw_machine_code else None
    if direct is not None:
        return {
            'machine_line_id': direct.id,
            'machine_line_code': direct.code,
            'machine_line_name': direct.name,
            'machine_binding_source': 'direct_machine_code',
        }

    raw_workshop = row.workshop_code or row.current_workshop or row.next_workshop
    canonical_workshop = _safe_resolve_canonical(db, entity_type='workshop', value=raw_workshop)
    if not canonical_workshop:
        return empty

    from app.models.master import Workshop

    workshop = (
        db.query(Workshop)
        .filter(Workshop.is_active.is_(True))
        .filter(or_(Workshop.code == canonical_workshop, Workshop.name == canonical_workshop))
        .first()
    )
    if workshop is None:
        return empty

    process_hint = row.current_process or row.process_code or row.next_process
    inferred_id = _infer_mes_machine_id_from_route(
        machines=machines_by_workshop.get(workshop.id, []),
        process_hint=process_hint,
    )
    if inferred_id is None:
        return empty

    inferred = next((m for m in machines_by_workshop[workshop.id] if m.id == inferred_id), None)
    if inferred is None:
        return empty
    return {
        'machine_line_id': inferred.id,
        'machine_line_code': inferred.code,
        'machine_line_name': inferred.name,
        'machine_binding_source': 'route_inferred',
    }


def _latest_tracking_card_snapshot(db: Session, tracking_card_no: str) -> MesCoilSnapshot | None:
    exact_row = (
        db.query(MesCoilSnapshot)
        .filter(MesCoilSnapshot.tracking_card_no == tracking_card_no)
        .order_by(
            MesCoilSnapshot.updated_from_mes_at.is_(None).asc(),
            MesCoilSnapshot.updated_from_mes_at.desc(),
            MesCoilSnapshot.id.desc(),
        )
        .first()
    )
    if exact_row is not None:
        return exact_row

    lookup_key = tracking_card_lookup_key(tracking_card_no)
    if not lookup_key:
        return None
    return (
        db.query(MesCoilSnapshot)
        .filter(tracking_card_sql_lookup_key(MesCoilSnapshot.tracking_card_no) == lookup_key)
        .order_by(
            MesCoilSnapshot.updated_from_mes_at.is_(None).asc(),
            MesCoilSnapshot.updated_from_mes_at.desc(),
            MesCoilSnapshot.id.desc(),
        )
        .first()
    )


def _latest_identifier_snapshot(db: Session, identifier: str) -> MesCoilSnapshot | None:
    lookup_key = tracking_card_lookup_key(identifier)
    if not lookup_key:
        return None
    identifier_fields = (
        MesCoilSnapshot.tracking_card_no,
        MesCoilSnapshot.material_code,
        MesCoilSnapshot.batch_no,
        MesCoilSnapshot.coil_id,
        MesCoilSnapshot.qr_code,
    )
    return (
        db.query(MesCoilSnapshot)
        .filter(or_(*(tracking_card_sql_lookup_key(field) == lookup_key for field in identifier_fields)))
        .order_by(
            MesCoilSnapshot.updated_from_mes_at.is_(None).asc(),
            MesCoilSnapshot.updated_from_mes_at.desc(),
            MesCoilSnapshot.id.desc(),
        )
        .first()
    )


def _latest_qr_snapshot(db: Session, qr_code: str) -> MesCoilSnapshot | None:
    return (
        db.query(MesCoilSnapshot)
        .filter(MesCoilSnapshot.qr_code == qr_code)
        .order_by(
            MesCoilSnapshot.updated_from_mes_at.is_(None).asc(),
            MesCoilSnapshot.updated_from_mes_at.desc(),
            MesCoilSnapshot.id.desc(),
        )
        .first()
    )


def submission_locked_snapshot_for_tracking_card(db: Session, *, tracking_card_no: str) -> dict[str, Any]:
    return {}


def flow_context_for_identifier(db: Session, *, identifier: str) -> dict[str, Any]:
    value = str(identifier or '').strip()
    if not value:
        return {}
    if not _has_coil_snapshot_table(db):
        raise ScanLookupUnavailable('mes_coil_snapshots_missing')
    row = _latest_identifier_snapshot(db, value)
    if row is None:
        return {}
    header_fields = _coil_payload(db, row, source='coil_identifier')['header_fields']
    flow = _compact(
        {
            'current_workshop': header_fields.get('current_workshop'),
            'current_process': header_fields.get('current_process'),
            'next_workshop': header_fields.get('next_workshop'),
            'next_process': header_fields.get('next_process'),
            'flow_source': 'mes_projection',
        }
    )
    mes_reference = _compact(
        {
            'tracking_card_no': row.tracking_card_no,
            'material_code': row.material_code,
            'batch_no': row.batch_no,
            'coil_id': row.coil_id,
        }
    )
    payload: dict[str, Any] = {}
    if flow:
        payload['flow'] = flow
    if mes_reference:
        payload['mes_reference'] = mes_reference
    return payload


def _material_code_as_scanned_card(row: MesCoilSnapshot, scanned_value: str) -> str | None:
    lookup_key = tracking_card_lookup_key(scanned_value)
    material_key = tracking_card_lookup_key(row.material_code or '')
    if lookup_key and material_key and lookup_key == material_key:
        return str(scanned_value or '').strip()
    return None


def lookup_qr(db: Session, *, qr: str) -> dict:
    value = str(qr or '').strip()
    if not value:
        raise ScanLookupNotFound('qr_not_found')

    if _has_coil_snapshot_table(db):
        row = _latest_qr_snapshot(db, value)
        if row is not None:
            return _coil_payload(db, row, source='coil_snapshot')

        row = _latest_tracking_card_snapshot(db, value)
        if row is not None:
            return _coil_payload(db, row, source='tracking_card')

        row = _latest_identifier_snapshot(db, value)
        if row is not None:
            return _coil_payload(
                db,
                row,
                source='coil_identifier',
                tracking_card_no_override=_material_code_as_scanned_card(row, value),
            )

    equipment = db.query(Equipment).filter(Equipment.qr_code == value).order_by(Equipment.id.asc()).first()
    if equipment is not None:
        return _machine_payload(equipment)

    raise ScanLookupNotFound('qr_not_found')
