from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, or_
from sqlalchemy.orm import Session

from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord

LOCAL_TZ = ZoneInfo('Asia/Shanghai')


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _text(value: Any) -> str:
    return str(value or '').strip()


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: _plain(value) for key, value in payload.items() if value not in (None, '')}


def _has_table(db: Session, table_name: str) -> bool:
    return inspect(db.get_bind()).has_table(table_name)


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value
    text = _text(value)
    if not text:
        return None
    if text.endswith('Z'):
        text = f'{text[:-1]}+00:00'
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _time_text(value: Any) -> str | None:
    dt = _parse_datetime(value)
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.strftime('%H:%M')
    return dt.astimezone(LOCAL_TZ).strftime('%H:%M')


def _off_machine_time_text(process: MesWorkshopProcessRecord, source_payload: dict[str, Any]) -> str | None:
    end_time = _parse_datetime(process.end_time)
    if end_time is not None and end_time.tzinfo is not None:
        return _time_text(end_time)
    return _time_text(source_payload.get('EndDatetime') or end_time)


def _latest_snapshot(db: Session, identifier: str) -> MesCoilSnapshot | None:
    value = _text(identifier)
    if not value:
        return None
    return (
        db.query(MesCoilSnapshot)
        .filter(
            or_(
                MesCoilSnapshot.tracking_card_no == value,
                MesCoilSnapshot.qr_code == value,
                MesCoilSnapshot.material_code == value,
                MesCoilSnapshot.batch_no == value,
            )
        )
        .order_by(
            MesCoilSnapshot.updated_from_mes_at.is_(None).asc(),
            MesCoilSnapshot.updated_from_mes_at.desc(),
            MesCoilSnapshot.id.desc(),
        )
        .first()
    )


def _latest_process(db: Session, snapshot: MesCoilSnapshot) -> MesWorkshopProcessRecord | None:
    if not _has_table(db, MesWorkshopProcessRecord.__tablename__):
        return None
    batch_no = _text(snapshot.batch_no)
    if not batch_no:
        return None
    return (
        db.query(MesWorkshopProcessRecord)
        .filter(MesWorkshopProcessRecord.batch_no == batch_no)
        .order_by(
            MesWorkshopProcessRecord.end_time.is_(None).asc(),
            MesWorkshopProcessRecord.end_time.desc(),
            MesWorkshopProcessRecord.id.desc(),
        )
        .first()
    )


def build_assisted_fill(db: Session, *, identifier: str) -> dict[str, Any]:
    if not _has_table(db, MesCoilSnapshot.__tablename__):
        return {'source': 'none', 'fields': {}, 'lock_keys': []}
    snapshot = _latest_snapshot(db, identifier)
    if snapshot is None:
        return {'source': 'none', 'fields': {}, 'lock_keys': []}

    process = _latest_process(db, snapshot)
    process_payload = dict(process.source_payload or {}) if process is not None else {}

    fields = _compact(
        {
            'tracking_card_no': snapshot.tracking_card_no,
            'alloy_grade': snapshot.alloy_grade,
            'input_spec': process_payload.get('BeginSpecification') if process is not None else snapshot.spec_display,
            'output_spec': process_payload.get('EndSpecification') if process is not None else None,
            'input_weight': process.input_weight_kg if process is not None else None,
            'output_weight': process.output_weight_kg if process is not None else None,
            'on_machine_time': _time_text(process_payload.get('BeginDatetime')) if process is not None else None,
            'off_machine_time': _off_machine_time_text(process, process_payload) if process is not None else None,
            'material_state': snapshot.material_state,
            'current_workshop': process.workshop_name if process is not None else snapshot.current_workshop,
            'current_process': process.process_name if process is not None else snapshot.current_process,
            'machine_line_name': process.device_name if process is not None else None,
        }
    )

    if process is not None and not fields.get('input_spec') and snapshot.spec_display:
        fields['input_spec'] = snapshot.spec_display

    return {
        'source': 'mes_process_record' if process is not None else 'mes_coil_snapshot',
        'fields': fields,
        'lock_keys': [],
    }
