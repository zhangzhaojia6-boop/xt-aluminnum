from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException, UploadFile
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.permissions import assert_manage_override_access, assert_review_access
from app.core.workflow_events import attach_workflow_event, build_workflow_event
from app.models.attendance import AttendanceException, AttendanceResult, AttendanceSchedule
from app.models.imports import ImportRow
from app.models.master import Equipment, Team, Workshop
from app.models.production import ProductionException, ShiftProductionData
from app.models.shift import ShiftConfig
from app.models.system import AuditLog, User
from app.services import import_service
from app.services import master_service
from app.services.audit_service import record_audit
from app.services.exception_service import (
    bulk_update_production_exception_status,
    create_duplicate_production_exception,
    replace_production_exceptions,
)
from app.services.mobile_report_service import sync_mobile_status_from_review
from app.utils.date_utils import parse_date

VALID_DUPLICATE_STRATEGIES = {'reject', 'supersede'}
ACTION_STATUS_MAP = {
    'review': 'reviewed',
    'confirm': 'confirmed',
    'reject': 'rejected',
    'void': 'voided',
}


@dataclass(slots=True)
class ProductionImportResult:
    batch_id: int
    batch_no: str
    import_type: str
    summary: dict


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == '':
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f'invalid numeric value: {value}') from exc


def _to_int(value: object, default: int | None = None) -> int | None:
    if value is None:
        return default
    text = str(value).strip()
    if text == '':
        return default
    try:
        return int(float(text))
    except ValueError as exc:
        raise ValueError(f'invalid integer value: {value}') from exc


def _key_filter(query, equipment_id: int | None):
    if equipment_id is None:
        return query.filter(ShiftProductionData.equipment_id.is_(None))
    return query.filter(ShiftProductionData.equipment_id == equipment_id)


def _count_actual_headcount(
    db: Session,
    *,
    business_date: date,
    shift_config_id: int,
    workshop_id: int,
    team_id: int | None,
) -> int:
    query = db.query(func.count(AttendanceResult.id)).filter(
        AttendanceResult.business_date == business_date,
        AttendanceResult.shift_config_id == shift_config_id,
        AttendanceResult.workshop_id == workshop_id,
        AttendanceResult.attendance_status != 'absent',
    )
    if team_id is not None:
        query = query.filter(AttendanceResult.team_id == team_id)
    return int(query.scalar() or 0)


def _count_planned_headcount(
    db: Session,
    *,
    business_date: date,
    shift_config_id: int,
    workshop_id: int,
    team_id: int | None,
) -> int:
    query = db.query(func.count(AttendanceSchedule.id)).filter(
        AttendanceSchedule.business_date == business_date,
        AttendanceSchedule.shift_config_id == shift_config_id,
        AttendanceSchedule.workshop_id == workshop_id,
    )
    if team_id is not None:
        query = query.filter(AttendanceSchedule.team_id == team_id)
    return int(query.scalar() or 0)


def _to_number(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _count_open_attendance_exceptions_for_shift(db: Session, *, item: ShiftProductionData) -> int:
    query = (
        db.query(func.count(AttendanceException.id))
        .join(AttendanceResult, AttendanceResult.id == AttendanceException.attendance_result_id)
        .filter(
            AttendanceResult.business_date == item.business_date,
            AttendanceResult.workshop_id == item.workshop_id,
            AttendanceResult.shift_config_id == item.shift_config_id,
            AttendanceException.status == 'open',
        )
    )
    if item.team_id is not None:
        query = query.filter(AttendanceResult.team_id == item.team_id)
    return int(query.scalar() or 0)


def _build_attendance_confirmed_event(
    db: Session,
    *,
    item: ShiftProductionData,
    exception_count: int,
    actor: User | None = None,
) -> dict:
    workshop = db.get(Workshop, item.workshop_id) if hasattr(db, 'get') else None
    machine = db.get(Equipment, item.equipment_id) if item.equipment_id and hasattr(db, 'get') else None
    shift = db.get(ShiftConfig, item.shift_config_id) if hasattr(db, 'get') else None
    base_payload = {
        'workshop_id': item.workshop_id,
        'team_id': item.team_id,
        'machine_id': item.equipment_id,
        'shift_id': item.shift_config_id,
        'business_date': item.business_date.isoformat(),
        'workshop': workshop.name if workshop else str(item.workshop_id),
        'machine': machine.name if machine else (str(item.equipment_id) if item.equipment_id else None),
        'shift': shift.name if shift else str(item.shift_config_id),
        'exception_count': int(exception_count),
    }
    workflow_event = build_workflow_event(
        event_type='attendance_confirmed',
        actor_role=getattr(actor, 'role', None),
        actor_id=getattr(actor, 'id', None),
        scope_type='machine' if item.equipment_id else ('team' if item.team_id else 'workshop'),
        workshop_id=item.workshop_id,
        team_id=item.team_id,
        shift_id=item.shift_config_id,
        entity_type='shift_production_data',
        entity_id=item.id,
        status='confirmed',
        payload={
            'business_date': base_payload['business_date'],
            'exception_count': int(exception_count),
        },
    )
    return attach_workflow_event(base_payload, workflow_event)


def _serialize_shift_data(
    item: ShiftProductionData,
    *,
    workshop_map: dict[int, Workshop],
    team_map: dict[int, Team],
    equipment_map: dict[int, Equipment],
    shift_map: dict[int, ShiftConfig],
) -> dict:
    workshop = workshop_map.get(item.workshop_id)
    team = team_map.get(item.team_id) if item.team_id else None
    equipment = equipment_map.get(item.equipment_id) if item.equipment_id else None
    shift = shift_map.get(item.shift_config_id)
    return {
        'id': item.id,
        'business_date': item.business_date,
        'shift_config_id': item.shift_config_id,
        'shift_code': shift.code if shift else None,
        'shift_name': shift.name if shift else None,
        'workshop_id': item.workshop_id,
        'workshop_code': workshop.code if workshop else None,
        'workshop_name': workshop.name if workshop else None,
        'team_id': item.team_id,
        'team_code': team.code if team else None,
        'team_name': team.name if team else None,
        'equipment_id': item.equipment_id,
        'equipment_code': equipment.code if equipment else None,
        'equipment_name': equipment.name if equipment else None,
        'input_weight': _to_number(item.input_weight),
        'output_weight': _to_number(item.output_weight),
        'qualified_weight': _to_number(item.qualified_weight),
        'scrap_weight': _to_number(item.scrap_weight),
        'planned_headcount': item.planned_headcount,
        'actual_headcount': item.actual_headcount,
        'downtime_minutes': item.downtime_minutes,
        'downtime_reason': item.downtime_reason,
        'issue_count': item.issue_count,
        'electricity_kwh': _to_number(item.electricity_kwh),
        'data_source': item.data_source,
        'import_batch_id': item.import_batch_id,
        'data_status': item.data_status,
        'version_no': item.version_no,
        'superseded_by_id': item.superseded_by_id,
        'reviewed_by': item.reviewed_by,
        'reviewed_at': item.reviewed_at,
        'confirmed_by': item.confirmed_by,
        'confirmed_at': item.confirmed_at,
        'rejected_by': item.rejected_by,
        'rejected_at': item.rejected_at,
        'rejected_reason': item.rejected_reason,
        'voided_by': item.voided_by,
        'voided_at': item.voided_at,
        'voided_reason': item.voided_reason,
        'published_by': item.published_by,
        'published_at': item.published_at,
        'notes': item.notes,
        'created_at': item.created_at,
        'updated_at': item.updated_at,
    }


def _query_active_duplicate(
    db: Session,
    *,
    business_date: date,
    shift_config_id: int,
    workshop_id: int,
    equipment_id: int | None,
) -> ShiftProductionData | None:
    query = db.query(ShiftProductionData).filter(
        ShiftProductionData.business_date == business_date,
        ShiftProductionData.shift_config_id == shift_config_id,
        ShiftProductionData.workshop_id == workshop_id,
        ShiftProductionData.data_status != 'voided',
    )
    query = _key_filter(query, equipment_id)
    return query.order_by(ShiftProductionData.version_no.desc(), ShiftProductionData.id.desc()).first()


def _resolve_refs(db: Session, mapped: dict) -> tuple[date, ShiftConfig, Workshop, Team | None, Equipment | None]:
    business_date = parse_date(mapped.get('business_date'))
    shift_code = master_service.resolve_canonical_code(
        db,
        entity_type='shift',
        value=mapped.get('shift_code'),
        source_type='production_shift',
    ) or str(mapped.get('shift_code') or '').strip()
    workshop_code = master_service.resolve_canonical_code(
        db,
        entity_type='workshop',
        value=mapped.get('workshop_code'),
        source_type='production_shift',
    ) or str(mapped.get('workshop_code') or '').strip()
    if not shift_code or not workshop_code:
        raise ValueError('shift_code and workshop_code are required')

    shift = db.query(ShiftConfig).filter(ShiftConfig.code == shift_code, ShiftConfig.is_active.is_(True)).first()
    if not shift:
        raise ValueError(f'shift not found: {shift_code}')
    workshop = db.query(Workshop).filter(Workshop.code == workshop_code, Workshop.is_active.is_(True)).first()
    if not workshop:
        raise ValueError(f'workshop not found: {workshop_code}')

    team = None
    team_code = master_service.resolve_canonical_code(
        db,
        entity_type='team',
        value=mapped.get('team_code'),
        source_type='production_shift',
    ) or str(mapped.get('team_code') or '').strip()
    if team_code:
        team = db.query(Team).filter(Team.code == team_code, Team.workshop_id == workshop.id).first()
        if not team:
            raise ValueError(f'team not found in workshop: {team_code}')

    equipment = None
    equipment_code = master_service.resolve_canonical_code(
        db,
        entity_type='equipment',
        value=mapped.get('equipment_code'),
        source_type='production_shift',
    ) or str(mapped.get('equipment_code') or '').strip()
    if equipment_code:
        equipment = db.query(Equipment).filter(Equipment.code == equipment_code).first()
        if not equipment:
            raise ValueError(f'equipment not found: {equipment_code}')
    return business_date, shift, workshop, team, equipment


def _build_shift_entity(
    db: Session,
    *,
    mapped: dict,
    batch_id: int,
    shift: ShiftConfig,
    workshop: Workshop,
    team: Team | None,
    equipment: Equipment | None,
    business_date: date,
    version_no: int,
) -> ShiftProductionData:
    planned_headcount = _to_int(mapped.get('planned_headcount'), default=None)
    actual_headcount = _count_actual_headcount(
        db,
        business_date=business_date,
        shift_config_id=shift.id,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
    )
    if planned_headcount is None:
        planned_headcount = _count_planned_headcount(
            db,
            business_date=business_date,
            shift_config_id=shift.id,
            workshop_id=workshop.id,
            team_id=team.id if team else None,
        )

    return ShiftProductionData(
        business_date=business_date,
        shift_config_id=shift.id,
        workshop_id=workshop.id,
        team_id=team.id if team else None,
        equipment_id=equipment.id if equipment else None,
        input_weight=_to_float(mapped.get('input_weight')),
        output_weight=_to_float(mapped.get('output_weight')),
        qualified_weight=_to_float(mapped.get('qualified_weight')),
        scrap_weight=_to_float(mapped.get('scrap_weight')),
        planned_headcount=planned_headcount,
        actual_headcount=actual_headcount,
        downtime_minutes=_to_int(mapped.get('downtime_minutes'), default=0) or 0,
        downtime_reason=str(mapped.get('downtime_reason') or '').strip() or None,
        issue_count=_to_int(mapped.get('issue_count'), default=0) or 0,
        electricity_kwh=_to_float(mapped.get('electricity_kwh')),
        data_source='import',
        import_batch_id=batch_id,
        data_status='pending',
        version_no=version_no,
        notes=str(mapped.get('notes') or '').strip() or None,
    )


def import_shift_production_data(
    db: Session,
    *,
    upload_file: UploadFile,
    current_user: User,
    template_code: str | None = None,
    duplicate_strategy: str = 'reject',
) -> ProductionImportResult:
    duplicate_strategy = (duplicate_strategy or 'reject').strip().lower()
    if duplicate_strategy not in VALID_DUPLICATE_STRATEGIES:
        raise HTTPException(status_code=400, detail='duplicate_strategy must be reject or supersede')

    stored_path, content, stored_filename = import_service._save_upload_file(upload_file)
    resolved_template_code, mappings = import_service._resolve_template_mapping(
        db, 'production_shift', template_code, source_type='production_shift'
    )

    batch = import_service._create_batch(
        db,
        import_type='production_shift',
        file_name=upload_file.filename or stored_filename,
        file_size=len(content),
        file_path=str(stored_path),
        imported_by=current_user.id,
        template_code=resolved_template_code,
        mapping_template_code=resolved_template_code,
        source_type='production_shift',
    )

    df = import_service._read_dataframe(stored_path)
    raw_rows = df.to_dict(orient='records')

    canonical_fields = {
        'business_date',
        'shift_code',
        'workshop_code',
        'team_code',
        'equipment_code',
        'input_weight',
        'output_weight',
        'qualified_weight',
        'scrap_weight',
        'downtime_minutes',
        'downtime_reason',
        'issue_count',
        'electricity_kwh',
        'planned_headcount',
        'notes',
    }

    success = 0
    failed = 0
    skipped = 0
    today = date.today()

    for index, raw in enumerate(raw_rows, start=1):
        normalized_raw = {str(key): import_service._normalize_value(value) for key, value in raw.items()}
        mapped = import_service._map_row(normalized_raw, mappings, canonical_fields)
        row = ImportRow(batch_id=batch.id, row_number=index, raw_data=normalized_raw, mapped_data=mapped, status='pending')
        db.add(row)

        try:
            business_date, shift, workshop, team, equipment = _resolve_refs(db, mapped)
            existed = _query_active_duplicate(
                db,
                business_date=business_date,
                shift_config_id=shift.id,
                workshop_id=workshop.id,
                equipment_id=equipment.id if equipment else None,
            )
            next_version = 1
            if existed:
                next_version = (existed.version_no or 1) + 1
                if duplicate_strategy == 'reject':
                    create_duplicate_production_exception(
                        db,
                        data=existed,
                        message='Duplicate key in production import: business_date + shift + workshop + equipment',
                    )
                    row.status = 'skipped'
                    row.error_msg = 'duplicate record'
                    skipped += 1
                    continue

                existed.data_status = 'voided'
                existed.voided_by = current_user.id
                existed.voided_at = datetime.utcnow()
                existed.voided_reason = f'superseded by import batch {batch.batch_no}'

            entity = _build_shift_entity(
                db,
                mapped=mapped,
                batch_id=batch.id,
                shift=shift,
                workshop=workshop,
                team=team,
                equipment=equipment,
                business_date=business_date,
                version_no=next_version,
            )
            db.add(entity)
            db.flush()
            if existed and duplicate_strategy == 'supersede':
                existed.superseded_by_id = entity.id
            replace_production_exceptions(db, data=entity, today=today)

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
        skipped_rows=skipped,
        error_summary=None if failed == 0 else f'failed_rows={failed}',
    )
    db.commit()
    db.refresh(batch)

    record_audit(
        db,
        user=current_user,
        action='import_production',
        module='production',
        entity_type='import_batches',
        entity_id=batch.id,
        detail={
            'batch_no': batch.batch_no,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'duplicate_strategy': duplicate_strategy,
        },
    )

    return ProductionImportResult(
        batch_id=batch.id,
        batch_no=batch.batch_no,
        import_type=batch.import_type,
        summary={
            'batch_no': batch.batch_no,
            'total_rows': len(raw_rows),
            'success_rows': success,
            'failed_rows': failed,
            'skipped_rows': skipped,
            'columns': list(df.columns),
        },
    )


def list_shift_data(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    workshop_id: int | None = None,
    team_id: int | None = None,
    data_status: str | None = None,
) -> list[dict]:
    query = db.query(ShiftProductionData)
    if start_date:
        query = query.filter(ShiftProductionData.business_date >= start_date)
    if end_date:
        query = query.filter(ShiftProductionData.business_date <= end_date)
    if workshop_id:
        query = query.filter(ShiftProductionData.workshop_id == workshop_id)
    if team_id:
        query = query.filter(ShiftProductionData.team_id == team_id)
    if data_status:
        query = query.filter(ShiftProductionData.data_status == data_status)

    items = query.order_by(ShiftProductionData.business_date.desc(), ShiftProductionData.id.desc()).limit(1000).all()
    workshop_ids = {item.workshop_id for item in items}
    team_ids = {item.team_id for item in items if item.team_id}
    equipment_ids = {item.equipment_id for item in items if item.equipment_id}
    shift_ids = {item.shift_config_id for item in items}

    workshops = db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all() if workshop_ids else []
    teams = db.query(Team).filter(Team.id.in_(team_ids)).all() if team_ids else []
    equipments = db.query(Equipment).filter(Equipment.id.in_(equipment_ids)).all() if equipment_ids else []
    shifts = db.query(ShiftConfig).filter(ShiftConfig.id.in_(shift_ids)).all() if shift_ids else []

    workshop_map = {item.id: item for item in workshops}
    team_map = {item.id: item for item in teams}
    equipment_map = {item.id: item for item in equipments}
    shift_map = {item.id: item for item in shifts}

    return [
        _serialize_shift_data(
            item,
            workshop_map=workshop_map,
            team_map=team_map,
            equipment_map=equipment_map,
            shift_map=shift_map,
        )
        for item in items
    ]


def list_production_exceptions(
    db: Session,
    *,
    business_date: date | None = None,
    exception_type: str | None = None,
    status: str | None = None,
    workshop_id: int | None = None,
    team_id: int | None = None,
    production_data_id: int | None = None,
) -> list[dict]:
    query = db.query(ProductionException)
    if business_date:
        query = query.filter(ProductionException.business_date == business_date)
    if exception_type:
        query = query.filter(ProductionException.exception_type == exception_type)
    if status:
        query = query.filter(ProductionException.status == status)
    if workshop_id:
        query = query.filter(ProductionException.workshop_id == workshop_id)
    if team_id is not None:
        query = query.filter(ProductionException.team_id == team_id)
    if production_data_id:
        query = query.filter(ProductionException.production_data_id == production_data_id)

    items = query.order_by(ProductionException.id.desc()).limit(1000).all()
    workshop_ids = {item.workshop_id for item in items}
    team_ids = {item.team_id for item in items if item.team_id}
    equipment_ids = {item.equipment_id for item in items if item.equipment_id}
    shift_ids = {item.shift_config_id for item in items if item.shift_config_id}

    workshops = db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all() if workshop_ids else []
    teams = db.query(Team).filter(Team.id.in_(team_ids)).all() if team_ids else []
    equipments = db.query(Equipment).filter(Equipment.id.in_(equipment_ids)).all() if equipment_ids else []
    shifts = db.query(ShiftConfig).filter(ShiftConfig.id.in_(shift_ids)).all() if shift_ids else []

    workshop_map = {item.id: item for item in workshops}
    team_map = {item.id: item for item in teams}
    equipment_map = {item.id: item for item in equipments}
    shift_map = {item.id: item for item in shifts}

    return [
        {
            'id': item.id,
            'production_data_id': item.production_data_id,
            'business_date': item.business_date,
            'workshop_id': item.workshop_id,
            'workshop_name': workshop_map.get(item.workshop_id).name if workshop_map.get(item.workshop_id) else None,
            'team_id': item.team_id,
            'team_name': team_map.get(item.team_id).name if item.team_id and team_map.get(item.team_id) else None,
            'equipment_id': item.equipment_id,
            'equipment_name': equipment_map.get(item.equipment_id).name
            if item.equipment_id and equipment_map.get(item.equipment_id)
            else None,
            'shift_config_id': item.shift_config_id,
            'shift_code': shift_map.get(item.shift_config_id).code
            if item.shift_config_id and shift_map.get(item.shift_config_id)
            else None,
            'exception_type': item.exception_type,
            'exception_desc': item.exception_desc,
            'severity': item.severity,
            'status': item.status,
            'resolved_by': item.resolved_by,
            'resolved_at': item.resolved_at,
            'created_at': item.created_at,
        }
        for item in items
    ]


def _status_transition_guard(current_status: str, action: str) -> None:
    if current_status == 'voided':
        raise HTTPException(status_code=400, detail='voided data cannot be changed')
    if action == 'review' and current_status in {'reviewed', 'confirmed'}:
        raise HTTPException(status_code=400, detail='current status cannot be reviewed again')
    if action == 'confirm' and current_status == 'confirmed':
        raise HTTPException(status_code=400, detail='current status already confirmed')
    if action == 'reject' and current_status == 'rejected':
        raise HTTPException(status_code=400, detail='current status already rejected')


def update_shift_data_status(
    db: Session,
    *,
    shift_data_id: int,
    action: str,
    reason: str | None,
    operator: User,
) -> ShiftProductionData:
    action = action.strip().lower()
    if action not in ACTION_STATUS_MAP:
        raise HTTPException(status_code=400, detail='unsupported action')

    item = db.get(ShiftProductionData, shift_data_id)
    if not item:
        raise HTTPException(status_code=404, detail='shift production data not found')

    if action == 'void':
        assert_manage_override_access(operator)
    else:
        assert_review_access(
            operator,
            workshop_id=item.workshop_id,
            team_id=item.team_id,
            shift_id=item.shift_config_id,
        )

    _status_transition_guard(item.data_status, action)
    now = datetime.now(UTC)
    target_status = ACTION_STATUS_MAP[action]

    if action in {'reject', 'void'} and not (reason or '').strip():
        raise HTTPException(status_code=400, detail='reason is required for reject/void action')

    old_status = item.data_status
    item.data_status = target_status

    if action == 'review':
        item.reviewed_by = operator.id
        item.reviewed_at = now
    elif action == 'confirm':
        item.confirmed_by = operator.id
        item.confirmed_at = now
        if item.reviewed_by is None:
            item.reviewed_by = operator.id
            item.reviewed_at = now
        bulk_update_production_exception_status(
            db,
            production_data_id=item.id,
            status='confirmed',
            user_id=operator.id,
        )
    elif action == 'reject':
        item.rejected_by = operator.id
        item.rejected_at = now
        item.rejected_reason = (reason or '').strip()
        bulk_update_production_exception_status(
            db,
            production_data_id=item.id,
            status='ignored',
            user_id=operator.id,
        )
    elif action == 'void':
        item.voided_by = operator.id
        item.voided_at = now
        item.voided_reason = (reason or '').strip()
        bulk_update_production_exception_status(
            db,
            production_data_id=item.id,
            status='ignored',
            user_id=operator.id,
        )

    sync_mobile_status_from_review(
        db,
        shift_data_id=item.id,
        action=action,
        reason=reason,
        actor_user_id=operator.id,
    )

    db.flush()
    record_audit(
        db,
        user=operator,
        action=f'shift_data_{action}',
        module='production',
        entity_type='shift_production_data',
        entity_id=item.id,
        detail={
            'old_status': old_status,
            'new_status': target_status,
            'reason': reason,
            'business_date': item.business_date.isoformat(),
        },
        reason=reason,
        auto_commit=False,
    )
    db.commit()
    db.refresh(item)
    if action == 'confirm':
        exception_count = _count_open_attendance_exceptions_for_shift(db, item=item)
        event_bus.publish(
            'attendance_confirmed',
            _build_attendance_confirmed_event(db, item=item, exception_count=exception_count, actor=operator),
        )
    return item


def get_shift_data_detail(db: Session, *, shift_data_id: int) -> tuple[dict, list[dict], list[dict]]:
    item = db.get(ShiftProductionData, shift_data_id)
    if not item:
        raise ValueError('shift production data not found')

    payloads = list_shift_data(
        db,
        start_date=item.business_date,
        end_date=item.business_date,
        workshop_id=item.workshop_id,
        team_id=item.team_id,
    )
    current = next((entry for entry in payloads if entry['id'] == item.id), None)
    if current is None:
        raise ValueError('shift production data not found')

    exceptions = list_production_exceptions(db, production_data_id=item.id)
    logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.table_name == 'shift_production_data',
            AuditLog.record_id == item.id,
        )
        .order_by(AuditLog.id.desc())
        .limit(30)
        .all()
    )
    trails = [
        {
            'id': log.id,
            'action': log.action,
            'user_name': log.user_name,
            'reason': log.reason,
            'created_at': log.created_at,
            'new_value': log.new_value,
        }
        for log in logs
    ]
    return current, exceptions, trails


def build_workshop_output_summary(
    db: Session,
    *,
    target_date: date,
    status_scope: str = 'include_reviewed',
) -> list[dict]:
    query = (
        db.query(
            ShiftProductionData.workshop_id,
            func.sum(ShiftProductionData.output_weight).label('total_output'),
            func.count(ShiftProductionData.id).label('shift_count'),
        )
        .filter(ShiftProductionData.business_date == target_date)
    )
    if status_scope == 'confirmed_only':
        query = query.filter(ShiftProductionData.data_status == 'confirmed')
    elif status_scope == 'include_pending':
        query = query.filter(ShiftProductionData.data_status.in_(['pending', 'reviewed', 'confirmed']))
    else:
        query = query.filter(ShiftProductionData.data_status.in_(['reviewed', 'confirmed']))

    rows = query.group_by(ShiftProductionData.workshop_id).all()
    workshop_ids = [item.workshop_id for item in rows]
    workshop_map = (
        {item.id: item for item in db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all()} if workshop_ids else {}
    )
    result: list[dict] = []
    for row in rows:
        workshop = workshop_map.get(row.workshop_id)
        result.append(
            {
                'workshop_id': row.workshop_id,
                'workshop_name': workshop.name if workshop else f'Workshop-{row.workshop_id}',
                'total_output': float(row.total_output or 0),
                'shift_count': int(row.shift_count or 0),
            }
        )
    result.sort(key=lambda item: item['total_output'], reverse=True)
    return result


def build_workshop_attendance_summary(db: Session, *, target_date: date) -> list[dict]:
    rows = (
        db.query(
            AttendanceResult.workshop_id,
            func.count(AttendanceResult.id).label('total'),
            func.sum(case((AttendanceResult.attendance_status == 'normal', 1), else_=0)).label('normal'),
            func.sum(case((AttendanceResult.attendance_status != 'normal', 1), else_=0)).label('abnormal'),
        )
        .filter(AttendanceResult.business_date == target_date)
        .group_by(AttendanceResult.workshop_id)
        .all()
    )
    workshop_ids = [item.workshop_id for item in rows if item.workshop_id]
    workshop_map = (
        {item.id: item for item in db.query(Workshop).filter(Workshop.id.in_(workshop_ids)).all()} if workshop_ids else {}
    )
    result: list[dict] = []
    for row in rows:
        result.append(
            {
                'workshop_id': row.workshop_id,
                'workshop_name': workshop_map.get(row.workshop_id).name
                if row.workshop_id and workshop_map.get(row.workshop_id)
                else 'Unknown',
                'total': int(row.total or 0),
                'normal': int(row.normal or 0),
                'abnormal': int(row.abnormal or 0),
            }
        )
    result.sort(key=lambda item: item['total'], reverse=True)
    return result


def mark_shift_data_published(
    db: Session,
    *,
    target_date: date,
    scope: str,
    operator: User,
) -> int:
    query = db.query(ShiftProductionData).filter(ShiftProductionData.business_date == target_date)
    if scope == 'confirmed_only':
        query = query.filter(ShiftProductionData.data_status == 'confirmed')
    else:
        query = query.filter(ShiftProductionData.data_status.in_(['reviewed', 'confirmed']))

    rows = query.all()
    now = datetime.utcnow()
    for item in rows:
        item.published_at = now
        item.published_by = operator.id
    db.flush()
    return len(rows)


def ensure_shift_data_exists(db: Session, *, shift_data_id: int) -> ShiftProductionData:
    item = db.get(ShiftProductionData, shift_data_id)
    if not item:
        raise HTTPException(status_code=404, detail='shift production data not found')
    return item
