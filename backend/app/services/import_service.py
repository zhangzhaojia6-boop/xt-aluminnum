from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models.attendance import AttendanceSchedule, ClockRecord
from app.models.imports import FieldMappingTemplate, ImportBatch, ImportRow
from app.models.master import Employee, Team, Workshop
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.audit_service import record_audit
from app.services import master_service
from app.services.contract_canonical_service import contract_row_summary_fields, parse_contract_workbook
from app.services.yield_matrix_canonical_service import (
    parse_yield_matrix_workbook,
    yield_matrix_row_summary_fields,
)
from app.utils.date_utils import normalize_clock_type, parse_date, parse_datetime


ALLOWED_SUFFIXES = {'.csv', '.xlsx', '.xls'}
DEFAULT_TEMPLATE_CODES = {
    'attendance_schedule': 'attendance_schedule_default',
    'attendance_clock': 'attendance_clock_default',
    'production_shift': 'production_shift_default',
    'energy': 'energy_default',
    'mes_export': 'mes_export_default',
}
DEFAULT_MAPPINGS = {
    'attendance_schedule': {
        'employee_no': 'employee_no',
        'dingtalk_user_id': 'dingtalk_user_id',
        'schedule_date': 'schedule_date',
        'shift_code': 'shift_code',
        'team_code': 'team_code',
        'workshop_code': 'workshop_code',
    },
    'attendance_clock': {
        'employee_no': 'employee_no',
        'dingtalk_user_id': 'dingtalk_user_id',
        'clock_datetime': 'clock_datetime',
        'clock_type': 'clock_type',
        'dingtalk_record_id': 'dingtalk_record_id',
        'device_id': 'device_id',
        'location_name': 'location_name',
    },
    'production_shift': {
        'business_date': 'business_date',
        'shift_code': 'shift_code',
        'workshop_code': 'workshop_code',
        'team_code': 'team_code',
        'equipment_code': 'equipment_code',
        'input_weight': 'input_weight',
        'output_weight': 'output_weight',
        'qualified_weight': 'qualified_weight',
        'scrap_weight': 'scrap_weight',
        'downtime_minutes': 'downtime_minutes',
        'downtime_reason': 'downtime_reason',
        'issue_count': 'issue_count',
        'electricity_kwh': 'electricity_kwh',
        'planned_headcount': 'planned_headcount',
        'notes': 'notes',
    },
    'energy': {
        'business_date': {'source': ['business_date', 'date'], 'required': True, 'transform_rule': 'date'},
        'workshop_code': {'source': ['workshop_code', 'workshop'], 'required': True, 'transform_rule': 'strip|upper'},
        'shift_code': {'source': ['shift_code', 'shift'], 'required': True, 'transform_rule': 'strip|upper'},
        'energy_type': {'source': ['energy_type', 'type'], 'required': True, 'transform_rule': 'strip|lower'},
        'energy_value': {'source': ['energy_value', 'value'], 'required': True, 'transform_rule': 'float'},
        'unit': {'source': ['unit'], 'required': False, 'transform_rule': 'strip'},
        'source_row_no': {'source': ['source_row_no', 'row_no'], 'required': False, 'transform_rule': 'int'},
    },
    'mes_export': {
        'business_date': {'source': ['business_date', 'date'], 'required': True, 'transform_rule': 'date'},
        'workshop_code': {'source': ['workshop_code', 'workshop'], 'required': True, 'transform_rule': 'strip|upper'},
        'shift_code': {'source': ['shift_code', 'shift'], 'required': True, 'transform_rule': 'strip|upper'},
        'metric_code': {'source': ['metric_code', 'metric'], 'required': True, 'transform_rule': 'strip'},
        'metric_name': {'source': ['metric_name', 'metric_name_cn'], 'required': False, 'transform_rule': 'strip'},
        'metric_value': {'source': ['metric_value', 'value'], 'required': True, 'transform_rule': 'float'},
        'unit': {'source': ['unit'], 'required': False, 'transform_rule': 'strip'},
        'source_row_no': {'source': ['source_row_no', 'row_no'], 'required': False, 'transform_rule': 'int'},
    },
}


@dataclass(slots=True)
class ImportResult:
    batch: ImportBatch
    summary: dict


def _normalize_value(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, 'item'):
        try:
            return value.item()
        except Exception:  # noqa: BLE001
            pass
    return value


def _normalize_key(value: object) -> str:
    return str(value).strip().lower()


def _extract_mapping_fields(mappings: dict) -> dict:
    if isinstance(mappings, dict) and 'fields' in mappings and isinstance(mappings['fields'], dict):
        return mappings['fields']
    return mappings


def _resolve_source_value(raw_row: dict, sources: list[str]) -> object | None:
    if not sources:
        return None
    normalized = {_normalize_key(key): key for key in raw_row.keys()}
    for source in sources:
        if source in raw_row:
            return raw_row.get(source)
        lower = _normalize_key(source)
        origin_key = normalized.get(lower)
        if origin_key is not None:
            return raw_row.get(origin_key)
    return None


def _apply_transform(value: object | None, rule: str | None) -> object | None:
    if value is None or rule is None:
        return value
    rules = [item.strip() for item in str(rule).split('|') if item.strip()]
    current = value
    for item in rules:
        if current is None:
            break
        if item == 'strip':
            current = str(current).strip()
        elif item == 'upper':
            current = str(current).strip().upper()
        elif item == 'lower':
            current = str(current).strip().lower()
        elif item in {'int', 'integer'}:
            text = str(current).strip()
            current = int(float(text)) if text else None
        elif item in {'float', 'number', 'decimal'}:
            text = str(current).strip()
            current = float(text) if text else None
        elif item == 'date':
            current = parse_date(current)
        elif item == 'datetime':
            current = parse_datetime(current)
    return current


def _read_dataframe(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == '.csv':
        return pd.read_csv(path, encoding='utf-8-sig')
    if suffix == '.xlsx':
        return pd.read_excel(path, engine='openpyxl')
    if suffix == '.xls':
        try:
            import xlrd  # noqa: F401
        except ModuleNotFoundError as exc:
            raise HTTPException(
                status_code=400,
                detail='当前运行环境不支持直接读取历史 .xls，请先转换为 .xlsx 后上传。',
            ) from exc
        return pd.read_excel(path, engine='xlrd')
    raise HTTPException(status_code=400, detail='Only csv/xlsx/xls files are supported')


def _save_upload_file(upload_file: UploadFile) -> tuple[Path, bytes, str]:
    suffix = Path(upload_file.filename or '').suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail='Only csv/xlsx/xls files are supported')

    upload_dir = settings.upload_dir_path
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f'{uuid4().hex}{suffix}'
    stored_path = upload_dir / stored_filename

    content = upload_file.file.read()
    stored_path.write_bytes(content)
    return stored_path, content, stored_filename


def _create_batch(
    db: Session,
    *,
    import_type: str,
    file_name: str,
    file_size: int,
    file_path: str,
    imported_by: int | None,
    template_code: str | None,
    mapping_template_code: str | None = None,
    source_type: str | None = None,
    quality_status: str = 'pending_check',
) -> ImportBatch:
    batch = ImportBatch(
        batch_no=f'IMP-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}-{uuid4().hex[:6]}',
        import_type=import_type,
        template_code=template_code,
        mapping_template_code=mapping_template_code or template_code,
        source_type=source_type or import_type,
        file_name=file_name,
        file_size=file_size,
        file_path=file_path,
        total_rows=0,
        success_rows=0,
        failed_rows=0,
        skipped_rows=0,
        status='processing',
        quality_status=quality_status,
        parsed_successfully=False,
        error_summary=None,
        imported_by=imported_by,
    )
    db.add(batch)
    db.flush()
    return batch


def _finalize_batch(
    db: Session,
    *,
    batch: ImportBatch,
    total_rows: int,
    success_rows: int,
    failed_rows: int,
    skipped_rows: int,
    error_summary: str | None,
) -> None:
    batch.total_rows = total_rows
    batch.success_rows = success_rows
    batch.failed_rows = failed_rows
    batch.skipped_rows = skipped_rows
    batch.error_summary = error_summary
    batch.status = 'completed' if failed_rows == 0 else 'partial_success'
    batch.quality_status = 'pending_check' if failed_rows == 0 else 'warning'
    batch.parsed_successfully = failed_rows == 0
    batch.completed_at = datetime.utcnow()
    db.flush()


def _resolve_template_mapping(
    db: Session,
    import_type: str,
    template_code: str | None,
    source_type: str | None = None,
) -> tuple[str | None, dict]:
    if template_code:
        template_query = db.query(FieldMappingTemplate).filter(
            FieldMappingTemplate.template_code == template_code,
            FieldMappingTemplate.import_type == import_type,
            FieldMappingTemplate.is_active.is_(True),
        )
        if source_type:
            template_query = template_query.filter(
                (FieldMappingTemplate.source_type == source_type) | (FieldMappingTemplate.source_type.is_(None))
            )
        template = template_query.first()
        if not template:
            raise HTTPException(status_code=400, detail=f'Field mapping template not found: {template_code}')
        return template.template_code, template.mappings

    default_code = DEFAULT_TEMPLATE_CODES.get(import_type)
    if default_code:
        template_query = db.query(FieldMappingTemplate).filter(
            FieldMappingTemplate.template_code == default_code,
            FieldMappingTemplate.import_type == import_type,
            FieldMappingTemplate.is_active.is_(True),
        )
        if source_type:
            template_query = template_query.filter(
                (FieldMappingTemplate.source_type == source_type) | (FieldMappingTemplate.source_type.is_(None))
            )
        template = template_query.first()
        if template:
            return template.template_code, template.mappings

    return default_code, DEFAULT_MAPPINGS.get(import_type, {})


def _map_row(
    raw_row: dict,
    mappings: dict,
    canonical_fields: set[str],
    *,
    return_missing: bool = False,
) -> dict | tuple[dict, list[str]]:
    if not mappings:
        mapped = {field: raw_row.get(field) for field in canonical_fields}
        if return_missing:
            return mapped, []
        return mapped

    mapped: dict = {}
    missing_required: list[str] = []
    mapping_fields = _extract_mapping_fields(mappings)
    # canonical -> source
    if isinstance(mapping_fields, dict) and any(key in canonical_fields for key in mapping_fields.keys()):
        for canonical_key in canonical_fields:
            spec = mapping_fields.get(canonical_key, canonical_key)
            if isinstance(spec, dict):
                sources = spec.get('source') or spec.get('sources') or spec.get('source_aliases') or spec.get('aliases')
                if sources is None:
                    sources = canonical_key
                if not isinstance(sources, list):
                    sources = [sources]
                value = _resolve_source_value(raw_row, [str(item) for item in sources])
                if (value is None or value == '') and 'default_value' in spec:
                    value = spec.get('default_value')
                value = _apply_transform(value, spec.get('transform_rule'))
                mapped[canonical_key] = value
                if spec.get('required') and (value is None or value == ''):
                    missing_required.append(canonical_key)
            else:
                source_key = spec
                mapped[canonical_key] = raw_row.get(source_key)
        if return_missing:
            return mapped, missing_required
        return mapped

    # source -> canonical
    reverse_map = {str(src): str(target) for src, target in mapping_fields.items()} if isinstance(mapping_fields, dict) else {}
    for source_key, value in raw_row.items():
        canonical_key = reverse_map.get(str(source_key))
        if canonical_key:
            mapped[canonical_key] = value
    for canonical_key in canonical_fields:
        mapped.setdefault(canonical_key, raw_row.get(canonical_key))
    if return_missing:
        return mapped, missing_required
    return mapped


async def process_import(
    db: Session,
    upload_file: UploadFile,
    import_type: str,
    user_id: int,
) -> ImportBatch:
    user = db.query(User).filter(User.id == user_id).first()
    result = store_import_file(upload_file=upload_file, db=db, current_user=user, import_type=import_type)
    return result.batch


def store_import_file(
    upload_file: UploadFile,
    db: Session,
    current_user: User | None = None,
    import_type: str = 'generic',
) -> ImportResult:
    stored_path, content, stored_filename = _save_upload_file(upload_file)
    batch = _create_batch(
        db,
        import_type=import_type,
        file_name=upload_file.filename or stored_filename,
        file_size=len(content),
        file_path=str(stored_path),
        imported_by=current_user.id if current_user else None,
        template_code=None,
        mapping_template_code=None,
        source_type=import_type,
    )

    rows = []
    summary_columns: list[str]
    if import_type == 'contract_report':
        parsed_rows = parse_contract_workbook(
            stored_path,
            source_batch_id=batch.id,
            year_hint=(batch.created_at.year if batch.created_at else None),
        )
        summary_columns = contract_row_summary_fields()
        for index, item in enumerate(parsed_rows, start=1):
            row = ImportRow(
                batch_id=batch.id,
                row_number=index,
                raw_data=item.raw_data,
                mapped_data=item.mapped_data,
                status=item.status,
                error_msg=item.error_msg,
            )
            rows.append(row)
            db.add(row)
        failed_rows = len([item for item in rows if item.status != 'success'])
        error_summary = '; '.join(filter(None, [item.error_msg for item in rows])) or None
    elif import_type == 'yield_rate_matrix':
        parsed_rows = parse_yield_matrix_workbook(
            stored_path,
            source_batch_id=batch.id,
            year_hint=(batch.created_at.year if batch.created_at else None),
        )
        summary_columns = yield_matrix_row_summary_fields()
        for index, item in enumerate(parsed_rows, start=1):
            row = ImportRow(
                batch_id=batch.id,
                row_number=index,
                raw_data=item.raw_data,
                mapped_data=item.mapped_data,
                status=item.status,
                error_msg=item.error_msg,
            )
            rows.append(row)
            db.add(row)
        failed_rows = len([item for item in rows if item.status != 'success'])
        error_summary = '; '.join(filter(None, [item.error_msg for item in rows])) or None
    else:
        df = _read_dataframe(stored_path)
        summary_columns = list(df.columns)
        for index, record in enumerate(df.to_dict(orient='records'), start=1):
            cleaned = {str(key): _normalize_value(value) for key, value in record.items()}
            row = ImportRow(
                batch_id=batch.id,
                row_number=index,
                raw_data=cleaned,
                mapped_data=cleaned,
                status='success',
                error_msg=None,
            )
            rows.append(row)
            db.add(row)
        failed_rows = 0
        error_summary = None

    _finalize_batch(
        db,
        batch=batch,
        total_rows=len(rows),
        success_rows=len(rows) - failed_rows,
        failed_rows=failed_rows,
        skipped_rows=0,
        error_summary=error_summary,
    )
    db.commit()
    db.refresh(batch)

    if current_user:
        record_audit(
            db,
            user=current_user,
            action='upload',
            module='imports',
            entity_type='import_batches',
            entity_id=batch.id,
            detail={'import_type': import_type, 'batch_no': batch.batch_no, 'rows': batch.total_rows},
        )

    return ImportResult(
        batch=batch,
        summary={
            'batch_no': batch.batch_no,
            'total_rows': batch.total_rows,
            'success_rows': batch.success_rows,
            'failed_rows': batch.failed_rows,
            'skipped_rows': batch.skipped_rows,
            'columns': summary_columns,
        },
    )


def import_attendance_schedules(
    db: Session,
    upload_file: UploadFile,
    current_user: User,
    template_code: str | None = None,
) -> ImportResult:
    stored_path, content, stored_filename = _save_upload_file(upload_file)
    resolved_template_code, mappings = _resolve_template_mapping(
        db, 'attendance_schedule', template_code, source_type='attendance_schedule'
    )

    batch = _create_batch(
        db,
        import_type='attendance_schedule',
        file_name=upload_file.filename or stored_filename,
        file_size=len(content),
        file_path=str(stored_path),
        imported_by=current_user.id,
        template_code=resolved_template_code,
        mapping_template_code=resolved_template_code,
        source_type='attendance_schedule',
    )

    df = _read_dataframe(stored_path)
    raw_rows = df.to_dict(orient='records')

    canonical_fields = {'employee_no', 'dingtalk_user_id', 'schedule_date', 'shift_code', 'team_code', 'workshop_code'}

    success = 0
    failed = 0
    skipped = 0

    for index, raw in enumerate(raw_rows, start=1):
        normalized_raw = {str(key): _normalize_value(value) for key, value in raw.items()}
        mapped = _map_row(normalized_raw, mappings, canonical_fields)
        row = ImportRow(batch_id=batch.id, row_number=index, raw_data=normalized_raw, mapped_data=mapped, status='pending')
        db.add(row)

        try:
            employee_no = (mapped.get('employee_no') or '').strip()
            dingtalk_user_id = (mapped.get('dingtalk_user_id') or '').strip()
            if not employee_no and not dingtalk_user_id:
                raise ValueError('employee_no or dingtalk_user_id is required')

            employee_query = db.query(Employee)
            if employee_no:
                employee = employee_query.filter(Employee.employee_no == employee_no).first()
            else:
                employee = employee_query.filter(Employee.dingtalk_user_id == dingtalk_user_id).first()
            if not employee:
                raise ValueError('employee not found')

            shift_code = master_service.resolve_canonical_code(
                db,
                entity_type='shift',
                value=mapped.get('shift_code'),
                source_type='attendance_schedule',
            ) or (mapped.get('shift_code') or '').strip()
            shift = db.query(ShiftConfig).filter(ShiftConfig.code == shift_code, ShiftConfig.is_active.is_(True)).first()
            if not shift:
                raise ValueError(f'shift not found: {shift_code}')

            schedule_date = parse_date(mapped.get('schedule_date'))

            team_id = employee.team_id
            workshop_id = employee.workshop_id
            team_code = master_service.resolve_canonical_code(
                db,
                entity_type='team',
                value=mapped.get('team_code'),
                source_type='attendance_schedule',
            ) or (mapped.get('team_code') or '').strip()
            workshop_code = master_service.resolve_canonical_code(
                db,
                entity_type='workshop',
                value=mapped.get('workshop_code'),
                source_type='attendance_schedule',
            ) or (mapped.get('workshop_code') or '').strip()

            if team_code:
                team = db.query(Team).filter(Team.code == team_code).first()
                if team:
                    team_id = team.id
            if workshop_code:
                workshop = db.query(Workshop).filter(Workshop.code == workshop_code).first()
                if workshop:
                    workshop_id = workshop.id

            schedule = (
                db.query(AttendanceSchedule)
                .filter(
                    AttendanceSchedule.employee_id == employee.id,
                    AttendanceSchedule.business_date == schedule_date,
                )
                .first()
            )
            if schedule:
                schedule.shift_config_id = shift.id
                schedule.team_id = team_id
                schedule.workshop_id = workshop_id
                schedule.source = 'import'
                schedule.import_batch_id = batch.id
            else:
                schedule = AttendanceSchedule(
                    employee_id=employee.id,
                    business_date=schedule_date,
                    shift_config_id=shift.id,
                    team_id=team_id,
                    workshop_id=workshop_id,
                    source='import',
                    import_batch_id=batch.id,
                    is_rest_day=False,
                )
                db.add(schedule)

            row.status = 'success'
            row.error_msg = None
            success += 1
        except Exception as exc:  # noqa: BLE001
            row.status = 'failed'
            row.error_msg = str(exc)
            failed += 1

    _finalize_batch(
        db,
        batch=batch,
        total_rows=len(raw_rows),
        success_rows=success,
        failed_rows=failed,
        skipped_rows=skipped,
        error_summary=None if failed == 0 else f'failed_rows={failed}',
    )
    db.commit()
    db.refresh(batch)

    record_audit(
        db,
        user=current_user,
        action='import_schedule',
        module='attendance',
        entity_type='import_batches',
        entity_id=batch.id,
        detail={'batch_no': batch.batch_no, 'success': success, 'failed': failed},
    )

    return ImportResult(
        batch=batch,
        summary={
            'batch_no': batch.batch_no,
            'total_rows': len(raw_rows),
            'success_rows': success,
            'failed_rows': failed,
            'skipped_rows': skipped,
            'columns': summary_columns,
        },
    )


def import_clock_records(
    db: Session,
    upload_file: UploadFile,
    current_user: User,
    template_code: str | None = None,
) -> ImportResult:
    stored_path, content, stored_filename = _save_upload_file(upload_file)
    resolved_template_code, mappings = _resolve_template_mapping(
        db, 'attendance_clock', template_code, source_type='attendance_clock'
    )

    batch = _create_batch(
        db,
        import_type='attendance_clock',
        file_name=upload_file.filename or stored_filename,
        file_size=len(content),
        file_path=str(stored_path),
        imported_by=current_user.id,
        template_code=resolved_template_code,
        mapping_template_code=resolved_template_code,
        source_type='attendance_clock',
    )

    df = _read_dataframe(stored_path)
    raw_rows = df.to_dict(orient='records')

    canonical_fields = {
        'employee_no',
        'dingtalk_user_id',
        'clock_datetime',
        'clock_type',
        'dingtalk_record_id',
        'device_id',
        'location_name',
    }

    success = 0
    failed = 0
    skipped = 0

    for index, raw in enumerate(raw_rows, start=1):
        normalized_raw = {str(key): _normalize_value(value) for key, value in raw.items()}
        mapped = _map_row(normalized_raw, mappings, canonical_fields)
        row = ImportRow(batch_id=batch.id, row_number=index, raw_data=normalized_raw, mapped_data=mapped, status='pending')
        db.add(row)

        try:
            employee_no = (mapped.get('employee_no') or '').strip()
            dingtalk_user_id = (mapped.get('dingtalk_user_id') or '').strip()
            if not employee_no and not dingtalk_user_id:
                raise ValueError('employee_no or dingtalk_user_id is required')

            employee_query = db.query(Employee)
            if employee_no:
                employee = employee_query.filter(Employee.employee_no == employee_no).first()
            else:
                employee = employee_query.filter(Employee.dingtalk_user_id == dingtalk_user_id).first()
            if not employee:
                raise ValueError('employee not found')

            clock_datetime = parse_datetime(mapped.get('clock_datetime'))
            clock_type = normalize_clock_type(str(mapped.get('clock_type') or 'in'))
            dingtalk_record_id = (mapped.get('dingtalk_record_id') or '').strip() or None
            device_id = (mapped.get('device_id') or '').strip()
            location_name = (mapped.get('location_name') or '').strip() or None

            if dingtalk_record_id:
                exists = db.query(ClockRecord).filter(ClockRecord.dingtalk_record_id == dingtalk_record_id).first()
                if exists:
                    row.status = 'skipped'
                    row.error_msg = 'duplicate dingtalk_record_id'
                    skipped += 1
                    continue

            exists_by_key = (
                db.query(ClockRecord)
                .filter(
                    ClockRecord.employee_id == employee.id,
                    ClockRecord.clock_datetime == clock_datetime,
                    ClockRecord.clock_type == clock_type,
                    ClockRecord.device_id == device_id,
                )
                .first()
            )
            if exists_by_key:
                row.status = 'skipped'
                row.error_msg = 'duplicate unique key'
                skipped += 1
                continue

            clock = ClockRecord(
                employee_id=employee.id,
                employee_no=employee.employee_no,
                dingtalk_user_id=employee.dingtalk_user_id,
                clock_datetime=clock_datetime,
                clock_type=clock_type,
                dingtalk_record_id=dingtalk_record_id,
                device_id=device_id,
                location_name=location_name,
                source='import',
                import_batch_id=batch.id,
                raw_data=normalized_raw,
            )
            db.add(clock)
            db.flush()

            row.status = 'success'
            row.error_msg = None
            success += 1
        except Exception as exc:  # noqa: BLE001
            row.status = 'failed'
            row.error_msg = str(exc)
            failed += 1

    _finalize_batch(
        db,
        batch=batch,
        total_rows=len(raw_rows),
        success_rows=success,
        failed_rows=failed,
        skipped_rows=skipped,
        error_summary=None if failed == 0 else f'failed_rows={failed}',
    )
    db.commit()
    db.refresh(batch)

    record_audit(
        db,
        user=current_user,
        action='import_clock',
        module='attendance',
        entity_type='import_batches',
        entity_id=batch.id,
        detail={'batch_no': batch.batch_no, 'success': success, 'failed': failed, 'skipped': skipped},
    )

    return ImportResult(
        batch=batch,
        summary={
            'batch_no': batch.batch_no,
            'total_rows': len(raw_rows),
            'success_rows': success,
            'failed_rows': failed,
            'skipped_rows': skipped,
            'columns': summary_columns,
        },
    )


def import_production_shift_data(
    db: Session,
    upload_file: UploadFile,
    current_user: User,
    template_code: str | None = None,
    duplicate_strategy: str = 'reject',
):
    from app.services import production_service

    return production_service.import_shift_production_data(
        db,
        upload_file=upload_file,
        current_user=current_user,
        template_code=template_code,
        duplicate_strategy=duplicate_strategy,
    )
