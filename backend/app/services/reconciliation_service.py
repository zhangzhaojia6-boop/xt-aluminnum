from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceResult
from app.models.mes import MesImportRecord
from app.models.master import Workshop
from app.models.shift import ShiftConfig
from app.models.energy import EnergyImportRecord
from app.models.production import ShiftProductionData
from app.models.reconciliation import DataReconciliationItem
from app.models.system import User
from app.services.audit_service import record_audit

RECON_TYPES = ('attendance_vs_production', 'production_vs_mes', 'energy_vs_production', 'report_vs_source')
STATUS_PROCESSED = {'confirmed', 'ignored', 'corrected'}


def _to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def count_open_items(db: Session, *, business_date: date) -> int:
    return int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(DataReconciliationItem.business_date == business_date, DataReconciliationItem.status == 'open')
        .scalar()
        or 0
    )


def count_processed_items(db: Session, *, business_date: date) -> int:
    return int(
        db.query(func.count(DataReconciliationItem.id))
        .filter(
            DataReconciliationItem.business_date == business_date,
            DataReconciliationItem.status.in_(list(STATUS_PROCESSED)),
        )
        .scalar()
        or 0
    )


def list_items(
    db: Session,
    *,
    business_date: date | None = None,
    reconciliation_type: str | None = None,
    status: str | None = None,
    field_name: str | None = None,
    item_id: int | None = None,
) -> list[DataReconciliationItem]:
    query = db.query(DataReconciliationItem)
    if item_id:
        query = query.filter(DataReconciliationItem.id == item_id)
    if business_date:
        query = query.filter(DataReconciliationItem.business_date == business_date)
    if reconciliation_type:
        query = query.filter(DataReconciliationItem.reconciliation_type == reconciliation_type)
    if status:
        query = query.filter(DataReconciliationItem.status == status)
    if field_name:
        query = query.filter(DataReconciliationItem.field_name == field_name)
    return query.order_by(DataReconciliationItem.business_date.desc(), DataReconciliationItem.id.desc()).all()


def _create_item(
    db: Session,
    *,
    business_date: date,
    reconciliation_type: str,
    source_a: str,
    source_b: str,
    dimension_key: str,
    field_name: str,
    source_a_value: float,
    source_b_value: float,
) -> DataReconciliationItem:
    diff = _to_float(source_a_value) - _to_float(source_b_value)
    item = DataReconciliationItem(
        business_date=business_date,
        reconciliation_type=reconciliation_type,
        source_a=source_a,
        source_b=source_b,
        dimension_key=dimension_key,
        field_name=field_name,
        source_a_value=str(source_a_value),
        source_b_value=str(source_b_value),
        diff_value=diff,
        status='open',
    )
    db.add(item)
    return item


def generate_reconciliation(
    db: Session,
    *,
    business_date: date,
    reconciliation_type: str | None,
    operator: User,
) -> list[DataReconciliationItem]:
    types = [reconciliation_type] if reconciliation_type else ['attendance_vs_production', 'production_vs_mes', 'energy_vs_production']
    for item in types:
        if item not in RECON_TYPES:
            raise ValueError(f'unsupported reconciliation_type: {item}')

    existing = (
        db.query(DataReconciliationItem)
        .filter(
            DataReconciliationItem.business_date == business_date,
            DataReconciliationItem.reconciliation_type.in_(types),
        )
        .all()
    )
    for item in existing:
        db.delete(item)

    created: list[DataReconciliationItem] = []

    workshop_code_map = {item.id: item.code for item in db.query(Workshop).all()}
    shift_code_map = {item.id: item.code for item in db.query(ShiftConfig).all()}

    if 'attendance_vs_production' in types:
        shift_id_expr = func.coalesce(AttendanceResult.shift_config_id, AttendanceResult.auto_shift_config_id)
        attendance_rows = (
            db.query(
                AttendanceResult.workshop_id,
                shift_id_expr,
                func.count(AttendanceResult.id).label('headcount'),
            )
            .filter(
                AttendanceResult.business_date == business_date,
                AttendanceResult.attendance_status != 'absent',
            )
            .group_by(AttendanceResult.workshop_id, shift_id_expr)
            .all()
        )
        attendance_map: dict[tuple[str | None, str | None], int] = {}
        for workshop_id, shift_id, headcount in attendance_rows:
            workshop_code = workshop_code_map.get(workshop_id)
            shift_code = shift_code_map.get(shift_id)
            attendance_map[(workshop_code, shift_code)] = int(headcount or 0)

        production_rows = (
            db.query(
                ShiftProductionData.workshop_id,
                ShiftProductionData.shift_config_id,
                func.sum(ShiftProductionData.actual_headcount).label('headcount'),
            )
            .filter(
                ShiftProductionData.business_date == business_date,
                ShiftProductionData.data_status != 'voided',
            )
            .group_by(ShiftProductionData.workshop_id, ShiftProductionData.shift_config_id)
            .all()
        )
        production_map: dict[tuple[str | None, str | None], int] = {}
        for workshop_id, shift_id, headcount in production_rows:
            workshop_code = workshop_code_map.get(workshop_id)
            shift_code = shift_code_map.get(shift_id)
            production_map[(workshop_code, shift_code)] = int(headcount or 0)

        keys = set(attendance_map.keys()) | set(production_map.keys())
        for workshop_code, shift_code in keys:
            att = attendance_map.get((workshop_code, shift_code), 0)
            prod = production_map.get((workshop_code, shift_code), 0)
            if att != prod:
                dimension_key = f'workshop:{workshop_code}|shift:{shift_code}'
                created.append(
                    _create_item(
                        db,
                        business_date=business_date,
                        reconciliation_type='attendance_vs_production',
                        source_a='attendance_results',
                        source_b='shift_production_data',
                        dimension_key=dimension_key,
                        field_name='headcount',
                        source_a_value=float(att),
                        source_b_value=float(prod),
                    )
                )

    if 'production_vs_mes' in types:
        production_rows = (
            db.query(
                ShiftProductionData.workshop_id,
                ShiftProductionData.shift_config_id,
                func.sum(ShiftProductionData.output_weight).label('output_weight'),
            )
            .filter(
                ShiftProductionData.business_date == business_date,
                ShiftProductionData.data_status != 'voided',
            )
            .group_by(ShiftProductionData.workshop_id, ShiftProductionData.shift_config_id)
            .all()
        )
        production_map: dict[tuple[str | None, str | None], float] = {}
        for workshop_id, shift_id, output_weight in production_rows:
            workshop_code = workshop_code_map.get(workshop_id)
            shift_code = shift_code_map.get(shift_id)
            production_map[(workshop_code, shift_code)] = _to_float(output_weight)

        mes_rows = (
            db.query(
                MesImportRecord.workshop_code,
                MesImportRecord.shift_code,
                func.sum(MesImportRecord.metric_value).label('metric_value'),
            )
            .filter(
                MesImportRecord.business_date == business_date,
                MesImportRecord.metric_code == 'output_weight',
            )
            .group_by(MesImportRecord.workshop_code, MesImportRecord.shift_code)
            .all()
        )
        mes_map: dict[tuple[str | None, str | None], float] = {}
        for workshop_code, shift_code, metric_value in mes_rows:
            mes_map[(workshop_code, shift_code)] = _to_float(metric_value)

        keys = set(production_map.keys()) | set(mes_map.keys())
        for workshop_code, shift_code in keys:
            prod = production_map.get((workshop_code, shift_code), 0.0)
            mes = mes_map.get((workshop_code, shift_code), 0.0)
            if prod != mes:
                dimension_key = f'workshop:{workshop_code}|shift:{shift_code}'
                created.append(
                    _create_item(
                        db,
                        business_date=business_date,
                        reconciliation_type='production_vs_mes',
                        source_a='shift_production_data',
                        source_b='mes_export',
                        dimension_key=dimension_key,
                        field_name='output_weight',
                        source_a_value=prod,
                        source_b_value=mes,
                    )
                )

    if 'energy_vs_production' in types:
        energy_rows = (
            db.query(
                EnergyImportRecord.workshop_code,
                EnergyImportRecord.shift_code,
                func.sum(EnergyImportRecord.energy_value).label('energy_total'),
            )
            .filter(EnergyImportRecord.business_date == business_date)
            .group_by(EnergyImportRecord.workshop_code, EnergyImportRecord.shift_code)
            .all()
        )
        energy_map: dict[tuple[str | None, str | None], float] = {}
        for workshop_code, shift_code, energy_total in energy_rows:
            energy_map[(workshop_code, shift_code)] = _to_float(energy_total)

        production_rows = (
            db.query(
                ShiftProductionData.workshop_id,
                ShiftProductionData.shift_config_id,
                func.sum(ShiftProductionData.output_weight).label('output_weight'),
            )
            .filter(
                ShiftProductionData.business_date == business_date,
                ShiftProductionData.data_status != 'voided',
            )
            .group_by(ShiftProductionData.workshop_id, ShiftProductionData.shift_config_id)
            .all()
        )
        production_map: dict[tuple[str | None, str | None], float] = {}
        for workshop_id, shift_id, output_weight in production_rows:
            workshop_code = workshop_code_map.get(workshop_id)
            shift_code = shift_code_map.get(shift_id)
            production_map[(workshop_code, shift_code)] = _to_float(output_weight)

        keys = set(energy_map.keys()) | set(production_map.keys())
        for workshop_code, shift_code in keys:
            energy_total = energy_map.get((workshop_code, shift_code), 0.0)
            output_weight = production_map.get((workshop_code, shift_code), 0.0)
            if energy_total == 0.0 or output_weight == 0.0:
                dimension_key = f'workshop:{workshop_code}|shift:{shift_code}'
                created.append(
                    _create_item(
                        db,
                        business_date=business_date,
                        reconciliation_type='energy_vs_production',
                        source_a='energy',
                        source_b='shift_production_data',
                        dimension_key=dimension_key,
                        field_name='energy_total',
                        source_a_value=energy_total,
                        source_b_value=output_weight,
                    )
                )

    db.commit()
    for item in created:
        db.refresh(item)

    record_audit(
        db,
        user=operator,
        action='generate_reconciliation',
        module='reconciliation',
        entity_type='data_reconciliation_items',
        entity_id=created[0].id if created else None,
        detail={'business_date': business_date.isoformat(), 'types': types, 'count': len(created)},
    )

    return created


def update_item_status(
    db: Session,
    *,
    item_id: int,
    action: str,
    operator: User,
    note: str | None = None,
) -> DataReconciliationItem:
    item = db.get(DataReconciliationItem, item_id)
    if item is None:
        raise ValueError('reconciliation item not found')

    if action == 'confirm':
        new_status = 'confirmed'
    elif action == 'ignore':
        new_status = 'ignored'
    elif action == 'correct':
        if not note:
            raise ValueError('resolve_note is required for correct')
        new_status = 'corrected'
    else:
        raise ValueError('unsupported action')

    item.status = new_status
    item.resolved_by = operator.id
    item.resolved_at = datetime.utcnow()
    if note:
        item.resolve_note = note
    db.flush()

    record_audit(
        db,
        user=operator,
        action=f'reconciliation_{action}',
        module='reconciliation',
        entity_type='data_reconciliation_items',
        entity_id=item.id,
        detail={'status': new_status, 'note': note},
        reason=note,
        auto_commit=False,
    )
    db.commit()
    db.refresh(item)
    return item
