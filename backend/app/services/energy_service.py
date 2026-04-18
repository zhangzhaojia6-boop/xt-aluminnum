from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.energy import EnergyImportRecord
from app.models.imports import ImportRow
from app.models.master import Workshop
from app.models.production import ShiftProductionData, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import import_service
from app.services import master_service
from app.services.audit_service import record_audit
from app.utils.date_utils import parse_date


VALID_ENERGY_TYPES = {'electricity', 'gas', 'water', 'other'}


@dataclass(slots=True)
class EnergyImportResult:
    batch_id: int
    batch_no: str
    import_type: str
    summary: dict


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_mapped_data(mapped: dict) -> dict:
    return {str(key): import_service._normalize_value(value) for key, value in (mapped or {}).items()}


def import_energy_data(
    db: Session,
    *,
    upload_file: UploadFile,
    current_user: User,
) -> EnergyImportResult:
    stored_path, content, stored_filename = import_service._save_upload_file(upload_file)
    resolved_template_code, mappings = import_service._resolve_template_mapping(
        db, 'energy', None, source_type='energy'
    )
    batch = import_service._create_batch(
        db,
        import_type='energy',
        file_name=upload_file.filename or stored_filename,
        file_size=len(content),
        file_path=str(stored_path),
        imported_by=current_user.id,
        template_code=resolved_template_code,
        mapping_template_code=resolved_template_code,
        source_type='energy',
    )

    df = import_service._read_dataframe(stored_path)
    raw_rows = df.to_dict(orient='records')
    success = 0
    failed = 0
    canonical_fields = {
        'business_date',
        'workshop_code',
        'shift_code',
        'energy_type',
        'energy_value',
        'unit',
        'source_row_no',
    }

    for index, raw in enumerate(raw_rows, start=1):
        cleaned = {str(key): import_service._normalize_value(value) for key, value in raw.items()}
        mapped, missing_required = import_service._map_row(
            cleaned, mappings, canonical_fields, return_missing=True
        )
        mapped_data = _normalize_mapped_data(mapped)
        row = ImportRow(
            batch_id=batch.id,
            row_number=index,
            raw_data=cleaned,
            mapped_data=mapped_data,
            status='pending',
        )
        db.add(row)
        try:
            if missing_required:
                raise ValueError(f'missing required fields: {", ".join(missing_required)}')

            business_date = parse_date(mapped.get('business_date'))
            energy_type = (mapped.get('energy_type') or '').strip().lower()
            if energy_type not in VALID_ENERGY_TYPES:
                raise ValueError('energy_type must be electricity/gas/water/other')

            workshop_code = master_service.resolve_canonical_code(
                db,
                entity_type='workshop',
                value=mapped.get('workshop_code'),
                source_type='energy',
            )
            if not workshop_code:
                raise ValueError('workshop_code not found')
            shift_code = master_service.resolve_canonical_code(
                db,
                entity_type='shift',
                value=mapped.get('shift_code'),
                source_type='energy',
            )
            if not shift_code:
                raise ValueError('shift_code not found')

            record = EnergyImportRecord(
                import_batch_id=batch.id,
                business_date=business_date,
                workshop_code=workshop_code,
                shift_code=shift_code,
                energy_type=energy_type,
                energy_value=_to_float(mapped.get('energy_value')),
                unit=(mapped.get('unit') or '').strip() or None,
                source_row_no=mapped.get('source_row_no') or index,
                raw_payload=cleaned,
            )
            db.add(record)
            row.status = 'success'
            row.error_msg = None
            success += 1
        except Exception as exc:  # noqa: BLE001
            row.status = 'failed'
            row.error_msg = str(exc)
            failed += 1

    import_service._finalize_batch(
        db,
        batch=batch,
        total_rows=len(raw_rows),
        success_rows=success,
        failed_rows=failed,
        skipped_rows=0,
        error_summary=None if failed == 0 else f'failed_rows={failed}',
    )
    db.commit()
    db.refresh(batch)

    record_audit(
        db,
        user=current_user,
        action='import_energy',
        module='energy',
        entity_type='import_batches',
        entity_id=batch.id,
        detail={'batch_no': batch.batch_no, 'success': success, 'failed': failed},
    )

    return EnergyImportResult(
        batch_id=batch.id,
        batch_no=batch.batch_no,
        import_type=batch.import_type,
        summary={
            'batch_no': batch.batch_no,
            'total_rows': len(raw_rows),
            'success_rows': success,
            'failed_rows': failed,
            'columns': list(df.columns),
        },
    )


def _workshop_code_map(db: Session) -> dict[int, str]:
    return {item.id: item.code for item in db.query(Workshop).all()}


def _shift_code_map(db: Session) -> dict[int, str]:
    return {item.id: item.code for item in db.query(ShiftConfig).all()}


def _resolve_workshop_id(db: Session) -> dict[str, int]:
    return {item.code: item.id for item in db.query(Workshop).all()}


def _resolve_shift_id(db: Session) -> dict[str, int]:
    return {item.code: item.id for item in db.query(ShiftConfig).all()}


def _load_owner_only_energy_rows(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None = None,
) -> list[dict]:
    workshop_code_map = _workshop_code_map(db)
    shift_code_map = _shift_code_map(db)
    target_workshop_code = workshop_code_map.get(workshop_id) if workshop_id else None
    output_by_workshop: dict[int, float] = {}

    rows = (
        db.query(WorkOrderEntry, Workshop)
        .join(Workshop, Workshop.id == WorkOrderEntry.workshop_id)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
            Workshop.workshop_type == 'inventory',
        )
        .all()
    )

    grouped: dict[tuple[int, int | None], dict] = {}
    for entry, workshop in rows:
        if target_workshop_code and workshop.code != target_workshop_code:
            continue
        payload = dict(entry.extra_payload or {})
        electricity_value = _to_float(payload.get('total_electricity_kwh'))
        if electricity_value is None:
            electricity_value = (_to_float(payload.get('new_plant_electricity_kwh')) or 0.0) + (
                _to_float(payload.get('park_electricity_kwh')) or 0.0
            )
        gas_value = _to_float(payload.get('total_gas_m3'))
        if gas_value is None:
            gas_value = sum(
                _to_float(payload.get(field_name)) or 0.0
                for field_name in ('cast_roll_gas_m3', 'smelting_gas_m3', 'heating_furnace_gas_m3', 'boiler_gas_m3')
            )
        water_value = (_to_float(payload.get('groundwater_ton')) or 0.0) + (_to_float(payload.get('tap_water_ton')) or 0.0)
        if not any(value for value in (electricity_value, gas_value, water_value)):
            continue

        key = (entry.workshop_id, entry.shift_id)
        bucket = grouped.setdefault(
            key,
            {
                'business_date': business_date.isoformat(),
                'workshop_id': entry.workshop_id,
                'workshop_code': workshop.code,
                'shift_config_id': entry.shift_id,
                'shift_code': shift_code_map.get(entry.shift_id),
                'electricity_value': 0.0,
                'gas_value': 0.0,
                'water_value': 0.0,
                'total_energy': 0.0,
                'output_weight': 0.0,
                'energy_per_ton': None,
                'source': 'owner_only',
            },
        )
        bucket['electricity_value'] += electricity_value or 0.0
        bucket['gas_value'] += gas_value or 0.0
        bucket['water_value'] += water_value
        bucket['total_energy'] += (electricity_value or 0.0) + (gas_value or 0.0) + water_value

    for (workshop_key, _shift_key), bucket in grouped.items():
        output_weight = output_by_workshop.get(workshop_key)
        if output_weight is None:
            output_weight = float(
                db.query(func.sum(ShiftProductionData.output_weight))
                .filter(
                    ShiftProductionData.business_date == business_date,
                    ShiftProductionData.workshop_id == workshop_key,
                    ShiftProductionData.data_status != 'voided',
                )
                .scalar()
                or 0
            )
            output_by_workshop[workshop_key] = output_weight
        bucket['output_weight'] = output_weight
        bucket['energy_per_ton'] = bucket['total_energy'] / output_weight if output_weight else None

    return list(grouped.values())


def get_energy_summary(
    db: Session,
    *,
    business_date: date | None = None,
    workshop_id: int | None = None,
    shift_config_id: int | None = None,
) -> list[dict]:
    query = db.query(EnergyImportRecord)
    if business_date:
        query = query.filter(EnergyImportRecord.business_date == business_date)
    if workshop_id:
        workshop_code_map = _workshop_code_map(db)
        workshop_code = workshop_code_map.get(workshop_id)
        if workshop_code:
            query = query.filter(EnergyImportRecord.workshop_code == workshop_code)
    if shift_config_id:
        shift_code_map = _shift_code_map(db)
        shift_code = shift_code_map.get(shift_config_id)
        if shift_code:
            query = query.filter(EnergyImportRecord.shift_code == shift_code)

    rows = query.all()
    if not rows and business_date is not None:
        return _load_owner_only_energy_rows(db, business_date=business_date, workshop_id=workshop_id)
    workshop_id_map = _resolve_workshop_id(db)
    shift_id_map = _resolve_shift_id(db)

    grouped: dict[tuple[str | None, str | None], dict] = {}
    for item in rows:
        key = (item.workshop_code, item.shift_code)
        payload = grouped.setdefault(
            key,
            {
                'business_date': item.business_date,
                'workshop_code': item.workshop_code,
                'shift_code': item.shift_code,
                'electricity_value': 0.0,
                'gas_value': 0.0,
                'water_value': 0.0,
                'total_energy': 0.0,
                'output_weight': 0.0,
                'energy_per_ton': None,
            },
        )
        energy_val = float(item.energy_value or 0)
        if item.energy_type == 'electricity':
            payload['electricity_value'] += energy_val
        elif item.energy_type == 'gas':
            payload['gas_value'] += energy_val
        elif item.energy_type == 'water':
            payload['water_value'] += energy_val
        payload['total_energy'] += energy_val

    for key, payload in grouped.items():
        workshop_code, shift_code = key
        workshop_id_val = workshop_id_map.get(workshop_code) if workshop_code else None
        shift_id_val = shift_id_map.get(shift_code) if shift_code else None
        output_weight = float(
            db.query(func.sum(ShiftProductionData.output_weight))
            .filter(
                ShiftProductionData.business_date == payload['business_date'],
                ShiftProductionData.workshop_id == workshop_id_val,
                ShiftProductionData.shift_config_id == shift_id_val,
                ShiftProductionData.data_status != 'voided',
            )
            .scalar()
            or 0
        )
        payload['workshop_id'] = workshop_id_val
        payload['shift_config_id'] = shift_id_val
        payload['output_weight'] = output_weight
        payload['energy_per_ton'] = payload['total_energy'] / output_weight if output_weight else None
        if hasattr(payload['business_date'], 'isoformat'):
            payload['business_date'] = payload['business_date'].isoformat()

    return list(grouped.values())


def summarize_energy_for_date(db: Session, *, business_date: date) -> dict:
    rows = get_energy_summary(db, business_date=business_date)

    electricity_value = sum(_to_float(item.get('electricity_value')) or 0.0 for item in rows)
    gas_value = sum(_to_float(item.get('gas_value')) or 0.0 for item in rows)
    water_value = sum(_to_float(item.get('water_value')) or 0.0 for item in rows)
    total_energy = sum(item['total_energy'] for item in rows)
    total_output = sum(item['output_weight'] for item in rows)
    energy_per_ton = total_energy / total_output if total_output else None
    return {
        'electricity_value': electricity_value,
        'gas_value': gas_value,
        'water_value': water_value,
        'total_energy': total_energy,
        'total_output_weight': total_output,
        'energy_per_ton': energy_per_ton,
        'rows': rows,
    }


def workshop_energy_summary(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
) -> dict:
    rows = get_energy_summary(db, business_date=business_date, workshop_id=workshop_id)
    totals = {
        'electricity_value': sum(_to_float(item.get('electricity_value')) or 0.0 for item in rows),
        'gas_value': sum(_to_float(item.get('gas_value')) or 0.0 for item in rows),
        'water_value': sum(_to_float(item.get('water_value')) or 0.0 for item in rows),
        'total_energy': sum(_to_float(item.get('total_energy')) or 0.0 for item in rows),
    }
    output_weight = float(
        db.query(func.sum(ShiftProductionData.output_weight))
        .filter(
            ShiftProductionData.business_date == business_date,
            ShiftProductionData.workshop_id == workshop_id,
            ShiftProductionData.data_status != 'voided',
        )
        .scalar()
        or 0
    )
    totals['output_weight'] = output_weight
    totals['energy_per_ton'] = totals['total_energy'] / output_weight if output_weight else None
    return totals
