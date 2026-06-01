from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.mes import (
    MesMaterialRecord,
    MesReferenceItem,
    MesStockRecord,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
    MesYieldRecord,
)

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

_SOURCE_DEFS = (
    {
        'key': 'workshop_process_records',
        'label': '车间过站',
        'model': MesWorkshopProcessRecord,
        'business_date_field': MesWorkshopProcessRecord.business_date,
        'seen_field': MesWorkshopProcessRecord.last_seen_from_mes_at,
    },
    {
        'key': 'stock_records',
        'label': '成品库存',
        'model': MesStockRecord,
        'business_date_field': MesStockRecord.business_date,
        'seen_field': MesStockRecord.last_seen_from_mes_at,
    },
    {
        'key': 'material_records',
        'label': '在制材料',
        'model': MesMaterialRecord,
        'business_date_field': MesMaterialRecord.business_date,
        'seen_field': MesMaterialRecord.last_seen_from_mes_at,
    },
    {
        'key': 'yield_records',
        'label': '成品率',
        'model': MesYieldRecord,
        'business_date_field': MesYieldRecord.business_date,
        'seen_field': MesYieldRecord.last_seen_from_mes_at,
    },
    {
        'key': 'reference_items',
        'label': '基础字典',
        'model': MesReferenceItem,
        'business_date_field': None,
        'seen_field': MesReferenceItem.last_seen_from_mes_at,
    },
    {
        'key': 'wip_total_snapshots',
        'label': '在制汇总',
        'model': MesWipTotalSnapshot,
        'business_date_field': None,
        'seen_field': MesWipTotalSnapshot.snapshot_at,
    },
)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_datetime(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _bounded_limit(value: int | None) -> int:
    try:
        limit = int(value if value is not None else DEFAULT_LIMIT)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


def _bounded_offset(value: int | None) -> int:
    try:
        offset = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, offset)


def _source_summary(db: Session, source_def: dict[str, Any]) -> dict[str, Any]:
    model = source_def['model']
    try:
        row_count = int(db.query(func.count(model.id)).scalar() or 0)
        business_date_field = source_def['business_date_field']
        latest_business_date = db.query(func.max(business_date_field)).scalar() if business_date_field is not None else None
        latest_seen_at = db.query(func.max(source_def['seen_field'])).scalar()
    except (OperationalError, ProgrammingError):
        return {
            'key': source_def['key'],
            'label': source_def['label'],
            'row_count': 0,
            'status': 'unavailable',
            'latest_business_date': None,
            'latest_seen_at': None,
        }
    return {
        'key': source_def['key'],
        'label': source_def['label'],
        'row_count': row_count,
        'status': 'ready' if row_count > 0 else 'empty',
        'latest_business_date': latest_business_date,
        'latest_seen_at': latest_seen_at,
    }


def build_summary(db: Session) -> dict[str, Any]:
    return {'sources': [_source_summary(db, source_def) for source_def in _SOURCE_DEFS]}


def _apply_filters(query: Any, model: type, *, business_date: date | None, search: str | None, fields: tuple[str, ...]) -> Any:
    if business_date is not None and hasattr(model, 'business_date'):
        query = query.filter(model.business_date == business_date)
    text = str(search or '').strip()
    if text:
        clauses = [getattr(model, field).ilike(f'%{text}%') for field in fields if hasattr(model, field)]
        if clauses:
            query = query.filter(or_(*clauses))
    return query


def _list_rows(
    db: Session,
    model: type,
    *,
    fields: tuple[str, ...],
    search_fields: tuple[str, ...],
    order_field: Any,
    business_date: date | None = None,
    search: str | None = None,
    limit: int | None = DEFAULT_LIMIT,
    offset: int | None = 0,
) -> list[dict[str, Any]]:
    try:
        query = db.query(model)
        query = _apply_filters(query, model, business_date=business_date, search=search, fields=search_fields)
        rows = (
            query.order_by(order_field.desc(), model.id.desc())
            .offset(_bounded_offset(offset))
            .limit(_bounded_limit(limit))
            .all()
        )
    except (OperationalError, ProgrammingError):
        return []
    return [_serialize(row, fields) for row in rows]


def _serialize(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in fields:
        value = getattr(row, field, None)
        if field.endswith('_tons') or field == 'yield_rate':
            value = _as_float(value)
        else:
            value = _as_datetime(value)
        payload[field] = value
    return payload


def list_workshop_process_records(
    db: Session,
    *,
    business_date: date | None = None,
    search: str | None = None,
    limit: int | None = DEFAULT_LIMIT,
    offset: int | None = 0,
) -> list[dict[str, Any]]:
    return _list_rows(
        db,
        MesWorkshopProcessRecord,
        fields=(
            'source_id',
            'batch_no',
            'customer_alias',
            'workshop_name',
            'process_name',
            'worker_name',
            'device_name',
            'input_weight_tons',
            'output_weight_tons',
            'yield_rate',
            'end_time',
            'business_date',
            'last_seen_from_mes_at',
        ),
        search_fields=('source_id', 'batch_no', 'customer_alias', 'workshop_name', 'process_name', 'worker_name', 'device_name'),
        order_field=MesWorkshopProcessRecord.end_time,
        business_date=business_date,
        search=search,
        limit=limit,
        offset=offset,
    )


def list_stock_records(
    db: Session,
    *,
    business_date: date | None = None,
    search: str | None = None,
    limit: int | None = DEFAULT_LIMIT,
    offset: int | None = 0,
) -> list[dict[str, Any]]:
    return _list_rows(
        db,
        MesStockRecord,
        fields=(
            'source_id',
            'batch_no',
            'contract_no',
            'customer_alias',
            'net_weight_tons',
            'gross_weight_tons',
            'in_stock_date',
            'business_date',
            'status_name',
            'last_seen_from_mes_at',
        ),
        search_fields=('source_id', 'batch_no', 'contract_no', 'customer_alias', 'status_name'),
        order_field=MesStockRecord.in_stock_date,
        business_date=business_date,
        search=search,
        limit=limit,
        offset=offset,
    )


def list_material_records(
    db: Session,
    *,
    business_date: date | None = None,
    search: str | None = None,
    limit: int | None = DEFAULT_LIMIT,
    offset: int | None = 0,
) -> list[dict[str, Any]]:
    return _list_rows(
        db,
        MesMaterialRecord,
        fields=(
            'source_id',
            'material_code',
            'workshop_name',
            'line_name',
            'position_name',
            'alloy_grade',
            'spec_display',
            'weight_tons',
            'production_date',
            'business_date',
            'status_name',
            'last_seen_from_mes_at',
        ),
        search_fields=('source_id', 'material_code', 'workshop_name', 'line_name', 'position_name', 'alloy_grade', 'spec_display', 'status_name'),
        order_field=MesMaterialRecord.production_date,
        business_date=business_date,
        search=search,
        limit=limit,
        offset=offset,
    )


def list_yield_records(
    db: Session,
    *,
    business_date: date | None = None,
    search: str | None = None,
    limit: int | None = DEFAULT_LIMIT,
    offset: int | None = 0,
) -> list[dict[str, Any]]:
    return _list_rows(
        db,
        MesYieldRecord,
        fields=(
            'source_id',
            'batch_no',
            'contract_no',
            'customer_alias',
            'contract_total_weight_tons',
            'feeding_weight_tons',
            'in_stock_net_weight_tons',
            'yield_rate',
            'report_time',
            'business_date',
            'last_seen_from_mes_at',
        ),
        search_fields=('source_id', 'batch_no', 'contract_no', 'customer_alias'),
        order_field=MesYieldRecord.report_time,
        business_date=business_date,
        search=search,
        limit=limit,
        offset=offset,
    )


def list_wip_total_snapshots(
    db: Session,
    *,
    search: str | None = None,
    limit: int | None = DEFAULT_LIMIT,
    offset: int | None = 0,
) -> list[dict[str, Any]]:
    return _list_rows(
        db,
        MesWipTotalSnapshot,
        fields=(
            'source_id',
            'workshop_name',
            'process_name',
            'doing_count',
            'doing_weight_tons',
            'snapshot_at',
        ),
        search_fields=('source_id', 'workshop_name', 'process_name'),
        order_field=MesWipTotalSnapshot.snapshot_at,
        business_date=None,
        search=search,
        limit=limit,
        offset=offset,
    )


def list_reference_items(
    db: Session,
    *,
    source_type: str | None = None,
    search: str | None = None,
    limit: int | None = DEFAULT_LIMIT,
    offset: int | None = 0,
) -> list[dict[str, Any]]:
    try:
        query = db.query(MesReferenceItem)
        normalized_type = str(source_type or '').strip()
        if normalized_type:
            query = query.filter(MesReferenceItem.source_type == normalized_type)
        query = _apply_filters(
            query,
            MesReferenceItem,
            business_date=None,
            search=search,
            fields=('source_id', 'source_type', 'code', 'name', 'parent_id', 'workshop_name', 'status_name'),
        )
        rows = (
            query.order_by(MesReferenceItem.last_seen_from_mes_at.desc(), MesReferenceItem.id.desc())
            .offset(_bounded_offset(offset))
            .limit(_bounded_limit(limit))
            .all()
        )
    except (OperationalError, ProgrammingError):
        return []
    return [
        _serialize(
            row,
            (
                'source_type',
                'source_id',
                'code',
                'name',
                'parent_id',
                'workshop_name',
                'status_name',
                'last_seen_from_mes_at',
            ),
        )
        for row in rows
    ]
