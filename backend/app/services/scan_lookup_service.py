from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.master import Equipment
from app.models.mes import MesCoilSnapshot
from app.services.locked_fields_service import sign_locked_fields

SUBMISSION_LOCK_KEYS = ('tracking_card_no', 'alloy_grade', 'input_spec')


class ScanLookupNotFound(RuntimeError):
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


def _coil_payload(row: MesCoilSnapshot, *, source: str) -> dict:
    spec_display = _spec_display(row)
    header_fields = _compact(
        {
            'tracking_card_no': row.tracking_card_no,
            'batch_no': row.batch_no,
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
    lock_keys = [key for key in SUBMISSION_LOCK_KEYS if header_fields.get(key) not in (None, '')]
    locked_snapshot = _submission_locked_snapshot(header_fields)
    return {
        'source': source,
        'header_fields': header_fields,
        'lock_keys': lock_keys,
        'lock_token': sign_locked_fields(locked_snapshot) if locked_snapshot else None,
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


def _submission_locked_snapshot(header_fields: dict[str, Any]) -> dict[str, Any]:
    return {key: header_fields[key] for key in SUBMISSION_LOCK_KEYS if header_fields.get(key) not in (None, '')}


def _has_coil_snapshot_table(db: Session) -> bool:
    bind = db.get_bind()
    return inspect(bind).has_table(MesCoilSnapshot.__tablename__)


def submission_locked_snapshot_for_tracking_card(db: Session, *, tracking_card_no: str) -> dict[str, Any]:
    value = str(tracking_card_no or '').strip()
    if not value:
        return {}
    if not _has_coil_snapshot_table(db):
        return {}
    row = (
        db.query(MesCoilSnapshot)
        .filter(MesCoilSnapshot.tracking_card_no == value)
        .order_by(MesCoilSnapshot.id.asc())
        .first()
    )
    if row is None:
        return {}
    return _submission_locked_snapshot(_coil_payload(row, source='tracking_card')['header_fields'])


def lookup_qr(db: Session, *, qr: str) -> dict:
    value = str(qr or '').strip()
    if not value:
        raise ScanLookupNotFound('qr_not_found')

    row = db.query(MesCoilSnapshot).filter(MesCoilSnapshot.qr_code == value).order_by(MesCoilSnapshot.id.asc()).first()
    if row is not None:
        return _coil_payload(row, source='coil_snapshot')

    row = (
        db.query(MesCoilSnapshot)
        .filter(MesCoilSnapshot.tracking_card_no == value)
        .order_by(MesCoilSnapshot.id.asc())
        .first()
    )
    if row is not None:
        return _coil_payload(row, source='tracking_card')

    equipment = db.query(Equipment).filter(Equipment.qr_code == value).order_by(Equipment.id.asc()).first()
    if equipment is not None:
        return _machine_payload(equipment)

    raise ScanLookupNotFound('qr_not_found')
