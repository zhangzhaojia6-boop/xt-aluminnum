from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy import func
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.consumable import DailyConsumableLog
from app.models.energy import EnergyImportRecord, IotEnergySnapshot, MachineEnergyRecord
from app.models.imports import ImportRow
from app.models.master import Workshop
from app.models.mes import MesStockRecord, MesWorkshopProcessRecord
from app.models.production import MobileShiftReport, ShiftProductionData, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.core.event_bus import event_bus
from app.services import import_service
from app.services import master_service
from app.services.audit_service import record_audit
from app.utils.date_utils import parse_date


VALID_ENERGY_TYPES = {'electricity', 'gas', 'water', 'other'}
FINAL_PACKAGING_WORKSHOP_CODES = {'JZ', 'LJ', 'JQ'}
FINAL_PACKAGING_MES_WORKSHOP_NAMES = {'精整', '拉矫', '园区剪切', '剪切'}
MES_PACKAGING_PROCESS_KEYWORDS = ('包装', '入库')
MES_STOCK_OUTPUT_FROM_DEPARTMENT_KEYWORDS = ('精整', '拉矫', '剪切')
PACKAGING_INBOUND_OUTPUT_FIELD = 'packaging_inbound_output_tons'
SUBMITTED_ENTRY_STATUSES = {'submitted', 'approved', 'auto_confirmed', 'confirmed'}
SUBMITTED_REPORT_STATUSES = {'submitted', 'approved', 'auto_confirmed', 'confirmed'}


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


_KG_DATA_SOURCES = {'mobile_coil_agg'}


def _is_missing_iot_shadow_table(error: Exception) -> bool:
    message = str(error).lower()
    return 'iot_energy_snapshots' in message and (
        'no such table' in message
        or 'does not exist' in message
        or 'undefined table' in message
    )


def _shift_weight_tons(item: ShiftProductionData, field_name: str) -> float:
    value = _to_float(getattr(item, field_name, None)) or 0.0
    if getattr(item, 'data_source', None) in _KG_DATA_SOURCES:
        return value / 1000
    return value


def _sum_shift_output_tons(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None = None,
    shift_config_id: int | None = None,
) -> float:
    query = db.query(ShiftProductionData).filter(
        ShiftProductionData.business_date == business_date,
        ShiftProductionData.data_status != 'voided',
    )
    if workshop_id is not None:
        query = query.filter(ShiftProductionData.workshop_id == workshop_id)
    if shift_config_id is not None:
        query = query.filter(ShiftProductionData.shift_config_id == shift_config_id)
    return sum(_shift_weight_tons(item, 'output_weight') for item in query.all())


def _payload_number(payload: dict, field_name: str) -> float | None:
    value = _to_float(payload.get(field_name))
    return value if value is not None else None


def _owner_storage_inbound_tons(payload: dict) -> float:
    direct_value = _payload_number(payload, 'storage_inbound_weight')
    if direct_value is not None:
        return direct_value
    total = 0.0
    has_component = False
    for field_name in ('park_inbound_daily', 'new_plant_inbound_daily', 'park_to_storage_inbound_weight'):
        value = _payload_number(payload, field_name)
        if value is None:
            continue
        total += value
        has_component = True
    return total if has_component else 0.0


def _plain_text(value) -> str:
    return str(value or '').strip()


def _source_payload(row) -> dict:
    return dict(getattr(row, 'source_payload', None) or {})


def _status_key(value) -> str:
    return _plain_text(value).lower()


def _mes_output_tons(row: MesWorkshopProcessRecord) -> float:
    value = _to_float(row.output_weight_tons)
    if value is not None:
        return value
    kg_value = _to_float(row.output_weight_kg)
    return (kg_value or 0.0) / 1000


def _mes_stock_output_tons(row: MesStockRecord) -> float:
    value = _to_float(row.net_weight_tons)
    if value is not None:
        return value
    kg_value = _to_float(row.net_weight_kg)
    return (kg_value or 0.0) / 1000


def _is_mes_packaging_output(row: MesWorkshopProcessRecord) -> bool:
    process_name = _plain_text(row.process_name)
    workshop_name = _plain_text(row.workshop_name)
    if not any(keyword in process_name for keyword in MES_PACKAGING_PROCESS_KEYWORDS):
        return False
    return any(name in workshop_name for name in FINAL_PACKAGING_MES_WORKSHOP_NAMES)


def _is_mes_stock_packaging_output(row: MesStockRecord) -> bool:
    payload = _source_payload(row)
    status = _status_key(row.status_name or payload.get('Status') or payload.get('status'))
    if status not in {'', '1', 'done', 'finished', '入库', '已入库', '正常'}:
        return False
    from_department = _plain_text(
        payload.get('FromDepartment')
        or payload.get('from_department')
        or payload.get('fromDept')
    )
    to_department = _plain_text(
        payload.get('ToDepartment')
        or payload.get('to_department')
        or payload.get('toDept')
    )
    if '成品' in to_department or '入库' in to_department:
        return any(keyword in from_department for keyword in MES_STOCK_OUTPUT_FROM_DEPARTMENT_KEYWORDS)
    return False


def _query_mes_stock_packaging_output_by_date(db: Session, *, business_date: date) -> float:
    rows = db.query(MesStockRecord).filter(MesStockRecord.business_date == business_date).all()
    return sum(_mes_stock_output_tons(row) for row in rows if _is_mes_stock_packaging_output(row))


def _query_mes_process_packaging_output_by_date(db: Session, *, business_date: date) -> float:
    rows = db.query(MesWorkshopProcessRecord).filter(MesWorkshopProcessRecord.business_date == business_date).all()
    return sum(_mes_output_tons(row) for row in rows if _is_mes_packaging_output(row))


def _mes_packaging_output_tons(db: Session, *, business_date: date) -> float:
    try:
        stock_output = _query_mes_stock_packaging_output_by_date(db, business_date=business_date)
        if stock_output > 0:
            return stock_output
        return _query_mes_process_packaging_output_by_date(db, business_date=business_date)
    except (OperationalError, ProgrammingError):
        return 0.0


def _factory_final_output_tons(db: Session, *, business_date: date) -> float:
    total = 0.0
    rows = (
        db.query(DailyConsumableLog.payload)
        .join(Workshop, Workshop.id == DailyConsumableLog.workshop_id)
        .filter(
            DailyConsumableLog.business_date == business_date,
            Workshop.code.in_(tuple(FINAL_PACKAGING_WORKSHOP_CODES)),
            Workshop.is_active.is_(True),
        )
        .all()
    )
    for (payload,) in rows:
        value = _payload_number(dict(payload or {}), PACKAGING_INBOUND_OUTPUT_FIELD)
        if value is not None and value > 0:
            total += value
    if total > 0:
        return total

    owner_rows = (
        db.query(WorkOrderEntry)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.entry_type == 'owner_daily',
            WorkOrderEntry.entry_status.in_(tuple(SUBMITTED_ENTRY_STATUSES)),
        )
        .all()
    )
    owner_total = sum(_owner_storage_inbound_tons(dict(row.extra_payload or {})) for row in owner_rows)
    if owner_total > 0:
        return owner_total

    storage_finished = (
        db.query(func.sum(MobileShiftReport.storage_finished))
        .filter(
            MobileShiftReport.business_date == business_date,
            MobileShiftReport.storage_finished.isnot(None),
            MobileShiftReport.report_status.in_(tuple(SUBMITTED_REPORT_STATUSES)),
        )
        .scalar()
    )
    return _to_float(storage_finished) or 0.0


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
    affected_business_dates: set[date] = set()
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
            affected_business_dates.add(business_date)
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
    business_dates = sorted(item.isoformat() for item in affected_business_dates)
    event_bus.publish('energy_changed', {
        'business_date': business_dates[0] if len(business_dates) == 1 else None,
        'business_dates': business_dates,
        'source': 'energy_import',
        'success_rows': success,
        'failed_rows': failed,
    })

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


def _load_machine_energy_totals(db: Session, report_ids: list[int]) -> dict[int, dict[str, float | int | None]]:
    if not report_ids:
        return {}
    rows = (
        db.query(
            MachineEnergyRecord.shift_report_id,
            func.sum(MachineEnergyRecord.energy_kwh).label('energy_kwh'),
            func.sum(MachineEnergyRecord.gas_m3).label('gas_m3'),
            func.count(MachineEnergyRecord.id).label('row_count'),
        )
        .filter(MachineEnergyRecord.shift_report_id.in_(report_ids))
        .group_by(MachineEnergyRecord.shift_report_id)
        .all()
    )
    return {
        row.shift_report_id: {
            'energy_kwh': _to_float(row.energy_kwh),
            'gas_m3': _to_float(row.gas_m3),
            'row_count': int(row.row_count or 0),
        }
        for row in rows
    }


def _prefer_machine_detail_total(report_value, detail_value) -> float:
    report_num = _to_float(report_value)
    detail_num = _to_float(detail_value)
    if detail_num is not None and detail_num > 0 and (report_num is None or report_num == 0):
        return detail_num
    return report_num or 0.0


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
            WorkOrderEntry.entry_type == 'owner_daily',
            WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved')),
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
            output_weight = _sum_shift_output_tons(
                db,
                business_date=business_date,
                workshop_id=workshop_key,
            )
            output_by_workshop[workshop_key] = output_weight
        bucket['output_weight'] = output_weight
        bucket['energy_per_ton'] = bucket['total_energy'] / output_weight if output_weight else None

    return list(grouped.values())


def _load_iot_shadow_energy_rows(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None = None,
    shift_config_id: int | None = None,
) -> list[dict]:
    if shift_config_id is not None:
        return []

    workshop_code_map = _workshop_code_map(db)
    query = db.query(IotEnergySnapshot).filter(IotEnergySnapshot.business_date == business_date)
    if workshop_id is not None:
        query = query.filter(IotEnergySnapshot.workshop_id == workshop_id)

    try:
        snapshots = query.all()
    except (OperationalError, ProgrammingError) as error:
        if _is_missing_iot_shadow_table(error):
            return []
        raise

    grouped: dict[int | None, dict] = {}
    for snapshot in snapshots:
        key = snapshot.workshop_id
        bucket = grouped.setdefault(
            key,
            {
                'business_date': business_date.isoformat(),
                'workshop_id': snapshot.workshop_id,
                'workshop_code': workshop_code_map.get(snapshot.workshop_id) if snapshot.workshop_id else None,
                'shift_config_id': None,
                'shift_code': None,
                'electricity_value': 0.0,
                'gas_value': 0.0,
                'water_value': 0.0,
                'total_energy': 0.0,
                'output_weight': 0.0,
                'energy_per_ton': None,
                'source': 'iot_shadow',
                'source_label': '物联网采集',
                'source_updated_at': None,
            },
        )
        electricity_value = _to_float(snapshot.electricity_kwh) or 0.0
        gas_value = _to_float(snapshot.gas_m3) or 0.0
        water_value = _to_float(snapshot.water_m3) or 0.0
        bucket['electricity_value'] += electricity_value
        bucket['gas_value'] += gas_value
        bucket['water_value'] += water_value
        bucket['total_energy'] += electricity_value + gas_value + water_value
        if snapshot.reading_at and (
            bucket['source_updated_at'] is None or snapshot.reading_at > bucket['source_updated_at']
        ):
            bucket['source_updated_at'] = snapshot.reading_at

    for workshop_key, bucket in grouped.items():
        output_weight = _sum_shift_output_tons(
            db,
            business_date=business_date,
            workshop_id=workshop_key,
        ) if workshop_key is not None else 0.0
        bucket['output_weight'] = output_weight
        bucket['energy_per_ton'] = bucket['total_energy'] / output_weight if output_weight else None

    return list(grouped.values())


def _load_mobile_shift_energy_rows(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None = None,
    shift_config_id: int | None = None,
) -> list[dict]:
    query = (
        db.query(MobileShiftReport, Workshop, ShiftConfig)
        .join(Workshop, Workshop.id == MobileShiftReport.workshop_id)
        .join(ShiftConfig, ShiftConfig.id == MobileShiftReport.shift_config_id)
        .filter(
            MobileShiftReport.business_date == business_date,
            MobileShiftReport.report_status.in_(('submitted', 'approved', 'auto_confirmed')),
        )
    )
    if workshop_id is not None:
        query = query.filter(MobileShiftReport.workshop_id == workshop_id)
    if shift_config_id is not None:
        query = query.filter(MobileShiftReport.shift_config_id == shift_config_id)

    report_rows = query.all()
    machine_totals = _load_machine_energy_totals(db, [report.id for report, _workshop, _shift in report_rows])

    grouped: dict[tuple[int, int], dict] = {}
    for report, workshop, shift in report_rows:
        key = (report.workshop_id, report.shift_config_id)
        bucket = grouped.setdefault(
            key,
            {
                'business_date': business_date.isoformat(),
                'workshop_id': report.workshop_id,
                'workshop_code': workshop.code,
                'shift_config_id': report.shift_config_id,
                'shift_code': shift.code,
                'electricity_value': 0.0,
                'gas_value': 0.0,
                'water_value': 0.0,
                'total_energy': 0.0,
                'output_weight': 0.0,
                'energy_per_ton': None,
                'source': 'mobile_shift_report',
            },
        )
        detail_totals = machine_totals.get(report.id) or {}
        electricity_value = _prefer_machine_detail_total(report.electricity_daily, detail_totals.get('energy_kwh'))
        gas_value = _prefer_machine_detail_total(report.gas_daily, detail_totals.get('gas_m3'))
        if not electricity_value and not gas_value:
            continue
        bucket['electricity_value'] += electricity_value
        bucket['gas_value'] += gas_value
        bucket['total_energy'] += electricity_value + gas_value

    for (workshop_key, shift_key), bucket in grouped.items():
        output_weight = _sum_shift_output_tons(
            db,
            business_date=business_date,
            workshop_id=workshop_key,
            shift_config_id=shift_key,
        )
        bucket['output_weight'] = output_weight
        bucket['energy_per_ton'] = bucket['total_energy'] / output_weight if output_weight else None

    return list(grouped.values())


def _primary_energy_rows(*, mobile_rows: list[dict], system_rows: list[dict], owner_rows: list[dict]) -> list[dict]:
    if mobile_rows:
        return mobile_rows
    if owner_rows:
        return owner_rows
    return system_rows


def _with_mes_packaging_output_basis(
    db: Session,
    *,
    business_date: date | None,
    rows: list[dict],
    workshop_id: int | None = None,
    shift_config_id: int | None = None,
) -> list[dict]:
    if business_date is None or workshop_id is not None or shift_config_id is not None:
        return rows
    if sum(_to_float(item.get('output_weight')) or 0.0 for item in rows) > 0:
        return rows

    packaging_output = _mes_packaging_output_tons(db, business_date=business_date)
    if packaging_output <= 0:
        return rows
    total_energy = sum(_to_float(item.get('total_energy')) or 0.0 for item in rows)
    return [
        *rows,
        {
            'business_date': business_date.isoformat(),
            'workshop_id': None,
            'workshop_code': 'FACTORY',
            'shift_config_id': None,
            'shift_code': None,
            'electricity_value': 0.0,
            'gas_value': 0.0,
            'water_value': 0.0,
            'total_energy': 0.0,
            'output_weight': packaging_output,
            'energy_per_ton': total_energy / packaging_output if total_energy else None,
            'source': 'mes_packaging_output_basis',
            'source_label': 'MES包装产量',
        },
    ]


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
    mobile_rows = (
        _load_mobile_shift_energy_rows(
            db,
            business_date=business_date,
            workshop_id=workshop_id,
            shift_config_id=shift_config_id,
        )
        if business_date is not None
        else []
    )
    owner_rows = (
        _load_owner_only_energy_rows(db, business_date=business_date, workshop_id=workshop_id)
        if business_date is not None
        else []
    )
    iot_rows = (
        _load_iot_shadow_energy_rows(
            db,
            business_date=business_date,
            workshop_id=workshop_id,
            shift_config_id=shift_config_id,
        )
        if business_date is not None
        else []
    )
    if shift_config_id is not None:
        owner_rows = [row for row in owner_rows if row.get('shift_config_id') == shift_config_id]
    if not rows and not mobile_rows:
        return _with_mes_packaging_output_basis(
            db,
            business_date=business_date,
            rows=[*owner_rows, *iot_rows],
            workshop_id=workshop_id,
            shift_config_id=shift_config_id,
        )
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
                'source': 'energy_import',
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
        output_weight = _sum_shift_output_tons(
            db,
            business_date=payload['business_date'],
            workshop_id=workshop_id_val,
            shift_config_id=shift_id_val,
        )
        payload['workshop_id'] = workshop_id_val
        payload['shift_config_id'] = shift_id_val
        payload['output_weight'] = output_weight
        payload['energy_per_ton'] = payload['total_energy'] / output_weight if output_weight else None
        if hasattr(payload['business_date'], 'isoformat'):
            payload['business_date'] = payload['business_date'].isoformat()

    return _with_mes_packaging_output_basis(
        db,
        business_date=business_date,
        rows=[*grouped.values(), *mobile_rows, *owner_rows, *iot_rows],
        workshop_id=workshop_id,
        shift_config_id=shift_config_id,
    )


def summarize_energy_for_date(db: Session, *, business_date: date) -> dict:
    rows = get_energy_summary(db, business_date=business_date)
    owner_rows = [item for item in rows if item.get('source') == 'owner_only']
    mobile_rows = [item for item in rows if item.get('source') == 'mobile_shift_report']
    system_rows = [item for item in rows if item.get('source') == 'energy_import' or item.get('source') is None]
    primary_rows = _primary_energy_rows(mobile_rows=mobile_rows, system_rows=system_rows, owner_rows=owner_rows)

    electricity_value = sum(_to_float(item.get('electricity_value')) or 0.0 for item in primary_rows)
    gas_value = sum(_to_float(item.get('gas_value')) or 0.0 for item in primary_rows)
    water_value = sum(_to_float(item.get('water_value')) or 0.0 for item in primary_rows)
    total_energy = sum(_to_float(item.get('total_energy')) or 0.0 for item in primary_rows)
    row_total_output = sum(_to_float(item.get('output_weight')) or 0.0 for item in primary_rows)
    mes_packaging_output = _mes_packaging_output_tons(db, business_date=business_date)
    factory_final_output = _factory_final_output_tons(db, business_date=business_date)
    if mes_packaging_output > 0:
        total_output = mes_packaging_output
        output_basis = 'mes_packaging_output'
    elif factory_final_output > 0:
        total_output = factory_final_output
        output_basis = 'factory_final_packaging_inbound'
    else:
        total_output = row_total_output
        output_basis = 'energy_rows'
    energy_per_ton = total_energy / total_output if total_output else None
    owner_electricity_value = sum(_to_float(item.get('electricity_value')) or 0.0 for item in owner_rows)
    owner_gas_value = sum(_to_float(item.get('gas_value')) or 0.0 for item in owner_rows)
    owner_water_value = sum(_to_float(item.get('water_value')) or 0.0 for item in owner_rows)
    owner_total_energy = sum(_to_float(item.get('total_energy')) or 0.0 for item in owner_rows)
    owner_total_output = sum(_to_float(item.get('output_weight')) or 0.0 for item in owner_rows)
    system_total_energy = sum(_to_float(item.get('total_energy')) or 0.0 for item in system_rows)
    system_total_output = sum(_to_float(item.get('output_weight')) or 0.0 for item in system_rows)
    mobile_total_energy = sum(_to_float(item.get('total_energy')) or 0.0 for item in mobile_rows)
    mobile_total_output = sum(_to_float(item.get('output_weight')) or 0.0 for item in mobile_rows)
    primary_source = (
        'mobile_shift_report'
        if mobile_rows
        else 'owner_only'
        if owner_rows
        else 'system'
        if system_rows
        else 'none'
    )
    return {
        'electricity_value': electricity_value,
        'gas_value': gas_value,
        'water_value': water_value,
        'total_energy': total_energy,
        'total_output_weight': total_output,
        'output_basis': output_basis,
        'energy_per_ton': energy_per_ton,
        'primary_source': primary_source,
        'system_totals': {
            'total_energy': system_total_energy,
            'total_output_weight': system_total_output,
            'energy_per_ton': system_total_energy / system_total_output if system_total_output else None,
            'row_count': len(system_rows),
        },
        'owner_totals': {
            'electricity_value': owner_electricity_value,
            'gas_value': owner_gas_value,
            'water_value': owner_water_value,
            'total_energy': owner_total_energy,
            'total_output_weight': owner_total_output,
            'energy_per_ton': owner_total_energy / owner_total_output if owner_total_output else None,
            'row_count': len(owner_rows),
        },
        'mobile_totals': {
            'total_energy': mobile_total_energy,
            'total_output_weight': mobile_total_output,
            'energy_per_ton': mobile_total_energy / mobile_total_output if mobile_total_output else None,
            'row_count': len(mobile_rows),
        },
        'rows': rows,
    }


def workshop_energy_summary(
    db: Session,
    *,
    business_date: date,
    workshop_id: int | None,
) -> dict:
    rows = get_energy_summary(db, business_date=business_date, workshop_id=workshop_id)
    owner_rows = [item for item in rows if item.get('source') == 'owner_only']
    mobile_rows = [item for item in rows if item.get('source') == 'mobile_shift_report']
    system_rows = [item for item in rows if item.get('source') == 'energy_import' or item.get('source') is None]
    primary_rows = _primary_energy_rows(mobile_rows=mobile_rows, system_rows=system_rows, owner_rows=owner_rows)
    totals = {
        'electricity_value': sum(_to_float(item.get('electricity_value')) or 0.0 for item in primary_rows),
        'gas_value': sum(_to_float(item.get('gas_value')) or 0.0 for item in primary_rows),
        'water_value': sum(_to_float(item.get('water_value')) or 0.0 for item in primary_rows),
        'total_energy': sum(_to_float(item.get('total_energy')) or 0.0 for item in primary_rows),
        'primary_source': (
            'mobile_shift_report'
            if mobile_rows
            else 'owner_only'
            if owner_rows
            else 'system'
            if system_rows
            else 'none'
        ),
    }
    output_weight = _sum_shift_output_tons(
        db,
        business_date=business_date,
        workshop_id=workshop_id,
    )
    totals['output_weight'] = output_weight
    totals['energy_per_ton'] = totals['total_energy'] / output_weight if output_weight else None
    return totals
