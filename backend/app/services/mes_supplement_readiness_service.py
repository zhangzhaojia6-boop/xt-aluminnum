from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.master import Equipment, MasterCodeAlias
from app.models.mes import MesWorkshopProcessRecord
from app.services import mes_machine_match_service
from app.services.mobile_mes_supplement_service import (
    _build_process_sequence_map,
    _material_category,
    _snapshot_by_batch,
    _snapshot_for_process,
    _window_for_business_date,
    resolve_supplement_business_date,
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


def _rate(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part / total, 4)


def _status(*, total: int, output_rate: float, machine_rate: float) -> str:
    if total <= 0:
        return 'no_data'
    if output_rate >= 0.8 and machine_rate >= 0.7:
        return 'ready'
    if output_rate >= 0.5 and machine_rate >= 0.4:
        return 'needs_mapping'
    return 'blocked'


def _warnings(*, total: int, output_rate: float, machine_rate: float, sequence_rate: float) -> list[str]:
    payload: list[str] = []
    if total <= 0:
        return ['mes_process_records_empty']
    if output_rate < 0.8:
        payload.append('output_weight_coverage_below_80_percent')
    if machine_rate < 0.7:
        payload.append('machine_match_coverage_below_70_percent')
    if sequence_rate < 0.8:
        payload.append('cold_roll_sequence_coverage_below_80_percent')
    return payload


def _window_filter(business_date: date):
    start, end = _window_for_business_date(business_date)
    return or_(
        and_(MesWorkshopProcessRecord.end_time >= start, MesWorkshopProcessRecord.end_time < end),
        and_(MesWorkshopProcessRecord.end_time.is_(None), MesWorkshopProcessRecord.business_date == business_date),
    )


def _sum_output_kg(db: Session, where_clause, *, workshop_names: set[str] | None) -> float:
    query = db.query(func.sum(MesWorkshopProcessRecord.output_weight_kg)).filter(where_clause)
    if workshop_names:
        query = query.filter(MesWorkshopProcessRecord.workshop_name.in_(workshop_names))
    return float(query.scalar() or 0)


def _count_records(db: Session, where_clause, *, workshop_names: set[str] | None) -> int:
    query = db.query(func.count(MesWorkshopProcessRecord.id)).filter(where_clause)
    if workshop_names:
        query = query.filter(MesWorkshopProcessRecord.workshop_name.in_(workshop_names))
    return int(query.scalar() or 0)


def _load_window_rows(
    db: Session,
    *,
    business_date: date,
    workshop_names: set[str] | None,
    limit: int,
) -> list[MesWorkshopProcessRecord]:
    query = db.query(MesWorkshopProcessRecord).filter(_window_filter(business_date))
    if workshop_names:
        query = query.filter(MesWorkshopProcessRecord.workshop_name.in_(workshop_names))
    return (
        query.order_by(MesWorkshopProcessRecord.end_time.asc(), MesWorkshopProcessRecord.id.asc())
        .limit(max(1, min(limit, 500)))
        .all()
    )


def build_supplement_readiness(
    db: Session,
    *,
    business_date: date | None = None,
    workshop_names: set[str] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    resolved_date = business_date or resolve_supplement_business_date()
    rows = _load_window_rows(db, business_date=resolved_date, workshop_names=workshop_names, limit=limit)
    machines = db.query(Equipment).filter(Equipment.is_active.is_(True)).all()
    aliases = (
        db.query(MasterCodeAlias)
        .filter(MasterCodeAlias.entity_type == 'equipment', MasterCodeAlias.is_active.is_(True))
        .all()
    )
    snapshots = _snapshot_by_batch(db, [row.batch_no for row in rows])
    process_sequences = _build_process_sequence_map(rows, snapshots)

    total = len(rows)
    has_device_name = 0
    has_output_weight = 0
    matched_machine = 0
    high_confidence = 0
    medium_confidence = 0
    with_snapshot = 0
    cold_roll_records = 0
    cold_roll_with_sequence = 0
    categories: dict[str, int] = {}
    binding_sources: dict[str, int] = {}
    unmatched_devices: list[dict[str, Any]] = []

    for row in rows:
        if row.device_name:
            has_device_name += 1
        if _plain_number(row.output_weight_kg) is not None:
            has_output_weight += 1

        snapshot = _snapshot_for_process(row, snapshots)
        if snapshot is not None:
            with_snapshot += 1

        category = _material_category(row)
        categories[category] = categories.get(category, 0) + 1
        if category == 'cold_roll_pass':
            cold_roll_records += 1
            if row.id in process_sequences:
                cold_roll_with_sequence += 1

        binding = mes_machine_match_service.resolve_mes_machine_binding(
            machines=machines,
            aliases=aliases,
            device_name=row.device_name,
            process_hint=row.process_name,
        )
        source = str(binding.get('source') or 'unresolved')
        binding_sources[source] = binding_sources.get(source, 0) + 1
        if binding.get('machine_id') is not None:
            matched_machine += 1
            if binding.get('confidence') == 'high':
                high_confidence += 1
            elif binding.get('confidence') == 'medium':
                medium_confidence += 1
        elif len(unmatched_devices) < 10:
            unmatched_devices.append(
                {
                    'source_id': row.source_id,
                    'batch_no': row.batch_no,
                    'workshop_name': row.workshop_name,
                    'process_name': row.process_name,
                    'device_name': row.device_name,
                    'binding_source': source,
                }
            )

    output_rate = _rate(has_output_weight, total)
    machine_rate = _rate(matched_machine, total)
    sequence_rate = _rate(cold_roll_with_sequence, cold_roll_records)
    stored_filter = MesWorkshopProcessRecord.business_date == resolved_date
    window_filter = _window_filter(resolved_date)
    supplement_count = _count_records(db, window_filter, workshop_names=workshop_names)
    stored_count = _count_records(db, stored_filter, workshop_names=workshop_names)
    supplement_output = _sum_output_kg(db, window_filter, workshop_names=workshop_names)
    stored_output = _sum_output_kg(db, stored_filter, workshop_names=workshop_names)

    return {
        'business_date': resolved_date,
        'sample_limit': max(1, min(limit, 500)),
        'status': _status(total=total, output_rate=output_rate, machine_rate=machine_rate),
        'coverage': {
            'sample_count': total,
            'device_name_rate': _rate(has_device_name, total),
            'output_weight_rate': output_rate,
            'machine_match_rate': machine_rate,
            'snapshot_match_rate': _rate(with_snapshot, total),
            'cold_roll_sequence_rate': sequence_rate,
        },
        'machine_binding': {
            'matched_count': matched_machine,
            'unmatched_count': max(total - matched_machine, 0),
            'high_confidence_count': high_confidence,
            'medium_confidence_count': medium_confidence,
            'source_counts': binding_sources,
        },
        'material_categories': categories,
        'window_comparison': {
            'supplement_window_start': '09:30',
            'supplement_window_count': supplement_count,
            'stored_business_date_count': stored_count,
            'delta_count': supplement_count - stored_count,
            'supplement_window_output_kg': round(supplement_output, 4),
            'stored_business_date_output_kg': round(stored_output, 4),
            'delta_output_kg': round(supplement_output - stored_output, 4),
        },
        'unmatched_devices': unmatched_devices,
        'warnings': _warnings(
            total=total,
            output_rate=output_rate,
            machine_rate=machine_rate,
            sequence_rate=sequence_rate,
        ),
    }
