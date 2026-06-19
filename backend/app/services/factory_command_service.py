from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from sqlalchemy import and_, false, or_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.business_time import resolve_production_business_date
from app.core.active_workshops import normalize_workshop_name, workshop_name_query_tokens
from app.core.scope import ScopeSummary
from app.core.report_statuses import READY_REPORT_STATUSES
from app.models.master import Equipment, MasterCodeAlias, Workshop
from app.models.mes import (
    CoilFlowEvent,
    MesCoilSnapshot,
    MesDailyWipSnapshot,
    MesMachineLineSnapshot,
    MesStockRecord,
    MesWipTotalSnapshot,
    MesWorkshopProcessRecord,
    MesYieldRecord,
)
from app.models.production import MobileShiftReport, ShiftProductionData
from app.services.equipment_service import resolve_reporting_machine_from_candidates
from app.services.mes_sync_service import latest_sync_status

DEFAULT_COIL_LIST_LIMIT = 100
MAX_COIL_LIST_LIMIT = 500
LOCAL_SHIFT_STATUSES = {'confirmed', 'submitted'}
LOCAL_PENDING_SHIFT_SOURCES = {'mobile_coil_agg'}
LOCAL_MOBILE_REPORT_STATUSES = READY_REPORT_STATUSES
LOCAL_WEIGHT_KG_SOURCES = {'mobile_coil_agg'}


def _all(db: Session, model: type) -> list[Any]:
    return list(db.query(model).all())


def _safe_all(db: Session, model: type) -> list[Any]:
    try:
        return _all(db, model)
    except (OperationalError, ProgrammingError):
        return []


def _query_first(query):
    if hasattr(query, 'first'):
        return query.first()
    rows = query.all() if hasattr(query, 'all') else list(query)
    return rows[0] if rows else None


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _canonical_workshop_name(value: Any, fallback: str = '未识别车间') -> str:
    normalized = normalize_workshop_name(value)
    return normalized or fallback


def _canonical_workshop_name_or_none(value: Any) -> str | None:
    normalized = normalize_workshop_name(value)
    return normalized or None


def _workshop_tokens(value: Any) -> set[str]:
    return {str(token).strip() for token in workshop_name_query_tokens(value) if str(token).strip()}


def _int_number(value: Any) -> int:
    return int(_number(value))


def _machine_mes_binding(raw: Mapping[str, Any] | None) -> dict[str, int]:
    payload = raw or {}
    return {
        'fill_entry_count': _int_number(payload.get('fill_entry_count')),
        'mes_matched_fill_count': _int_number(payload.get('mes_matched_fill_count')),
        'mes_bound_fill_count': _int_number(payload.get('mes_bound_fill_count')),
        'direct_machine_code_count': _int_number(payload.get('direct_machine_code_count')),
        'route_inferred_machine_count': _int_number(payload.get('route_inferred_machine_count')),
        'mes_projection_count': _int_number(payload.get('mes_projection_count')),
    }


def _local_weight_tons(row: Any, field_name: str) -> float:
    value = _number(getattr(row, field_name, None))
    if getattr(row, 'data_source', None) in LOCAL_WEIGHT_KG_SOURCES:
        return value / 1000
    return value


def _is_stalled(row: Any) -> bool:
    return (
        _number(getattr(row, 'delay_hours', None)) > 0
        or not getattr(row, 'current_process', None)
        or not getattr(row, 'next_process', None)
    )


def _destination(row: Any) -> dict[str, str]:
    if getattr(row, 'delivery_date', None):
        return {'kind': 'delivery', 'label': '交付'}
    if getattr(row, 'allocation_date', None):
        return {'kind': 'allocation', 'label': '已分配'}
    if getattr(row, 'in_stock_date', None) or getattr(row, 'status_name', None) == '已入库':
        return {'kind': 'finished_stock', 'label': '成品库存'}
    if getattr(row, 'current_process', None) or getattr(row, 'next_process', None):
        return {'kind': 'in_progress', 'label': '在制'}
    return {'kind': 'unknown', 'label': '未知'}


def _weight(row: Any) -> float:
    for field_name in ('net_weight', 'gross_weight', 'material_weight', 'feeding_weight'):
        value = getattr(row, field_name, None)
        if value is not None:
            return _number(value)
    return 0.0


def _weight_tons_from_process(record: Any, tons_field: str, kg_field: str) -> float | None:
    tons_value = getattr(record, tons_field, None)
    if tons_value is not None:
        return round(_number(tons_value), 4)
    kg_value = getattr(record, kg_field, None)
    if kg_value is not None:
        return round(_number(kg_value) / 1000, 4)
    return None


def _possible_tons(value: Any) -> float | None:
    if value is None:
        return None
    numeric = _number(value)
    if abs(numeric) >= 1000:
        return round(numeric / 1000, 4)
    return round(numeric, 4)


def _process_sort_key(record: Any) -> tuple[float, int]:
    value = (
        getattr(record, 'end_time', None)
        or getattr(record, 'last_seen_from_mes_at', None)
        or getattr(record, 'updated_at', None)
        or getattr(record, 'created_at', None)
    )
    timestamp = value.timestamp() if hasattr(value, 'timestamp') else 0.0
    return (timestamp, int(getattr(record, 'id', 0) or 0))


def _latest_process_records_by_batch(db: Session, batch_nos: set[str]) -> dict[str, Any]:
    normalized = {str(value).strip() for value in batch_nos if str(value or '').strip()}
    if not normalized:
        return {}

    query = db.query(MesWorkshopProcessRecord)
    try:
        if _is_sqlalchemy_query(query):
            records = list(query.filter(MesWorkshopProcessRecord.batch_no.in_(normalized)).all())
        else:
            records = [
                row
                for row in _all(db, MesWorkshopProcessRecord)
                if str(getattr(row, 'batch_no', '') or '').strip() in normalized
            ]
    except (OperationalError, ProgrammingError):
        return {}

    latest: dict[str, Any] = {}
    for record in records:
        batch_no = str(getattr(record, 'batch_no', '') or '').strip()
        if not batch_no:
            continue
        current = latest.get(batch_no)
        if current is None or _process_sort_key(record) > _process_sort_key(current):
            latest[batch_no] = record
    return latest


def _process_records_for_batch(db: Session, batch_no: str) -> list[Any]:
    normalized = str(batch_no or '').strip()
    if not normalized:
        return []
    try:
        query = db.query(MesWorkshopProcessRecord)
        if _is_sqlalchemy_query(query):
            return list(query.filter(MesWorkshopProcessRecord.batch_no == normalized).all())
        return [
            row
            for row in _all(db, MesWorkshopProcessRecord)
            if str(getattr(row, 'batch_no', '') or '').strip() == normalized
        ]
    except (OperationalError, ProgrammingError):
        return []


def _process_weight_payload(record: Any | None) -> dict[str, Any]:
    if record is None:
        return {
            'mes_input_weight_tons': None,
            'mes_output_weight_tons': None,
            'auto_scrap_weight_tons': None,
            'auto_scrap_rate': None,
            'scrap_status': 'no_mes_process_record',
        }

    input_tons = _weight_tons_from_process(record, 'input_weight_tons', 'input_weight_kg')
    output_tons = _weight_tons_from_process(record, 'output_weight_tons', 'output_weight_kg')
    scrap_rate = None
    if input_tons is None or output_tons is None:
        scrap_tons = None
        status = 'missing_weight'
    elif output_tons > input_tons:
        scrap_tons = None
        status = 'abnormal_output_gt_input'
    else:
        scrap_tons = round(input_tons - output_tons, 4)
        scrap_rate = round(scrap_tons / input_tons, 4) if input_tons > 0 else None
        status = 'normal'

    return {
        'mes_input_weight_tons': input_tons,
        'mes_output_weight_tons': output_tons,
        'auto_scrap_weight_tons': scrap_tons,
        'auto_scrap_rate': scrap_rate,
        'scrap_status': status,
    }


def _event_time_text(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, 'isoformat') else (str(value) if value else None)


def _flow_event(
    *,
    kind: str,
    label: str,
    source_table: str,
    source_path: str | None,
    event_time: Any,
    workshop: Any = None,
    process: Any = None,
    machine: Any = None,
    input_weight_tons: Any = None,
    output_weight_tons: Any = None,
    net_weight_tons: Any = None,
    status: str = '已证实',
) -> dict[str, Any]:
    return {
        'kind': kind,
        'label': label,
        'event_time': _event_time_text(event_time),
        'workshop': _canonical_workshop_name_or_none(workshop),
        'process': process,
        'machine': machine,
        'input_weight_tons': input_weight_tons,
        'output_weight_tons': output_weight_tons,
        'net_weight_tons': net_weight_tons,
        'source_table': source_table,
        'source_path': source_path,
        'status': status,
    }


def _flow_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get('event_time') or ''), str(item.get('kind') or ''))


def _stock_event_meta(record: Any) -> dict[str, str]:
    source_path = str(getattr(record, 'source_path', '') or '')
    normalized = source_path.lower()
    if 'allocation' in normalized:
        return {
            'kind': 'allocation',
            'label': '成品调拨',
            'source_table': 'WMS_Allocation / WMS_OutStockDetail',
            'status': '候选',
        }
    if 'delivery' in normalized or 'outstock' in normalized:
        return {
            'kind': 'delivery',
            'label': '成品出库/交付',
            'source_table': 'WMS_OutStockDetail',
            'status': '待验证',
        }
    if 'stock_header_records' in normalized or 'wms_instock' in normalized or 'instock' in normalized:
        return {
            'kind': 'stock',
            'label': '成品入库',
            'source_table': 'WMS_InStock / WMS_InStockDetail',
            'status': '已证实',
        }
    return {
        'kind': 'stock',
        'label': '成品入库',
        'source_table': 'WMS_InStock / WMS_InStockDetail',
        'status': '待验证',
    }


def _matching_stock_records(db: Session, row: Any, batch_no: str) -> list[MesStockRecord]:
    tracking_card_no = str(getattr(row, 'tracking_card_no', '') or '').strip()
    coil_id = str(getattr(row, 'coil_id', '') or '').strip()
    keys = {item for item in (batch_no, tracking_card_no, coil_id) if item}
    if not keys:
        return []
    return [
        record
        for record in _safe_all(db, MesStockRecord)
        if str(getattr(record, 'batch_no', '') or '').strip() in keys
        or str(getattr(record, 'source_id', '') or '').strip() in keys
    ]


def _lifecycle_events(db: Session, row: Any, *, process_records: list[Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    batch_no = str(getattr(row, 'batch_no', '') or '').strip()
    events: list[dict[str, Any]] = []
    feeding_time = getattr(row, 'event_time', None) or getattr(row, 'updated_from_mes_at', None) or getattr(row, 'last_seen_from_mes_at', None)
    if getattr(row, 'feeding_weight', None) is not None:
        events.append(
            _flow_event(
                kind='feeding',
                label='投料',
                source_table='MES_Product',
                source_path='/Feeding/Index',
                event_time=feeding_time,
                input_weight_tons=_possible_tons(getattr(row, 'feeding_weight', None)),
            )
        )
    for record in sorted(process_records, key=_process_sort_key):
        events.append(
            _flow_event(
                kind='process',
                label=str(getattr(record, 'process_name', None) or '工序过站'),
                source_table='MES_ProductProcessRecord',
                source_path=getattr(record, 'source_path', None) or 'sqlserver:workshop_process_records',
                event_time=getattr(record, 'end_time', None),
                workshop=getattr(record, 'workshop_name', None),
                process=getattr(record, 'process_name', None),
                machine=getattr(record, 'device_name', None),
                input_weight_tons=_weight_tons_from_process(record, 'input_weight_tons', 'input_weight_kg'),
                output_weight_tons=_weight_tons_from_process(record, 'output_weight_tons', 'output_weight_kg'),
            )
        )
    for record in sorted(
        _matching_stock_records(db, row, batch_no),
        key=lambda item: _event_time_text(getattr(item, 'in_stock_date', None) or getattr(item, 'updated_at', None)) or '',
    ):
        source_path = str(getattr(record, 'source_path', '') or '')
        meta = _stock_event_meta(record)
        events.append(
            _flow_event(
                kind=meta['kind'],
                label=meta['label'],
                source_table=meta['source_table'],
                source_path=source_path,
                event_time=getattr(record, 'in_stock_date', None),
                net_weight_tons=getattr(record, 'net_weight_tons', None),
                status=meta['status'],
            )
        )
    for event in sorted([item for item in _safe_all(db, CoilFlowEvent) if item.coil_key == getattr(row, 'coil_id', None)], key=_event_sort_key):
        events.append(
            _flow_event(
                kind='snapshot_flow',
                label='MES流转快照',
                source_table='MES_Product',
                source_path='coil_flow_events',
                event_time=getattr(event, 'event_time', None),
                workshop=getattr(event, 'current_workshop', None),
                process=getattr(event, 'current_process', None),
                status='候选',
            )
        )
    events = sorted(events, key=_flow_sort_key)
    terminal_events = [item for item in events if item['kind'] in {'stock', 'delivery', 'allocation'}]
    confirmed_terminal_events = [item for item in terminal_events if item.get('status') == '已证实']
    coverage = {
        'status': 'ready' if process_records and confirmed_terminal_events else 'partial',
        'process_event_count': len(process_records),
        'stock_event_count': len(terminal_events),
        'confirmed_stock_event_count': len(confirmed_terminal_events),
        'missing_segments': [
            label
            for label, missing in (
                ('工序历史', not process_records),
                ('已证实入库/交付', not confirmed_terminal_events),
            )
            if missing
        ],
        'source': 'local_mes_projection',
    }
    return events, coverage


def _coil_trace_payload(row: Any, *, line_code: str | None = None) -> dict[str, Any]:
    return {
        'coil_key': getattr(row, 'coil_id', None),
        'tracking_card_no': getattr(row, 'tracking_card_no', None),
        'batch_no': getattr(row, 'batch_no', None),
        'contract_no': getattr(row, 'contract_no', None),
        'material_code': getattr(row, 'material_code', None),
        'customer_alias': getattr(row, 'customer_alias', None),
        'alloy_grade': getattr(row, 'alloy_grade', None),
        'material_state': getattr(row, 'material_state', None),
        'spec_thickness': getattr(row, 'spec_thickness', None),
        'spec_width': getattr(row, 'spec_width', None),
        'spec_length': getattr(row, 'spec_length', None),
        'spec_display': getattr(row, 'spec_display', None),
        'feeding_weight': getattr(row, 'feeding_weight', None),
        'material_weight': getattr(row, 'material_weight', None),
        'gross_weight': getattr(row, 'gross_weight', None),
        'net_weight': getattr(row, 'net_weight', None),
        'line_code': line_code,
        'machine_code': getattr(row, 'machine_code', None),
        'current_workshop': _canonical_workshop_name_or_none(getattr(row, 'current_workshop', None)),
        'current_process': getattr(row, 'current_process', None),
        'next_workshop': _canonical_workshop_name_or_none(getattr(row, 'next_workshop', None)),
        'next_process': getattr(row, 'next_process', None),
        'status_name': getattr(row, 'status_name', None),
        'card_status_name': getattr(row, 'card_status_name', None),
        'production_status': getattr(row, 'production_status', None),
        'delay_hours': getattr(row, 'delay_hours', None),
        'process_route_text': getattr(row, 'process_route_text', None),
        'print_process_route_text': getattr(row, 'print_process_route_text', None),
        'in_stock_date': getattr(row, 'in_stock_date', None),
        'delivery_date': getattr(row, 'delivery_date', None),
        'allocation_date': getattr(row, 'allocation_date', None),
        'updated_from_mes_at': getattr(row, 'updated_from_mes_at', None),
        'last_seen_from_mes_at': getattr(row, 'last_seen_from_mes_at', None),
    }


def _scope_workshop_tokens(db: Session, scope: ScopeSummary | None) -> set[str] | None:
    if scope is None or scope.is_admin or scope.data_scope_type == 'all':
        return None
    if scope.workshop_id is None:
        return set()
    workshop = _query_first(db.query(Workshop).filter(Workshop.id == scope.workshop_id))
    tokens = {str(scope.workshop_id)}
    canonical_code: str | None = None
    if workshop is not None:
        canonical_code = (str(getattr(workshop, 'code', '') or '') or None)
        tokens.update(
            token
            for token in (
                getattr(workshop, 'name', None),
                _canonical_workshop_name(getattr(workshop, 'name', None), fallback=''),
                getattr(workshop, 'code', None),
            )
            if token
        )
    if canonical_code:
        alias_rows = (
            db.query(MasterCodeAlias.alias_code)
            .filter(
                MasterCodeAlias.entity_type == 'workshop',
                MasterCodeAlias.canonical_code == canonical_code,
                MasterCodeAlias.is_active.is_(True),
            )
            .all()
        )
        tokens.update(str(row[0]) for row in alias_rows if row and row[0])
    return {str(token).strip() for token in tokens if str(token).strip()}


def _matches_workshop(value: Any, tokens: set[str] | None) -> bool:
    if tokens is None:
        return True
    if not tokens:
        return False
    text = str(value or '').strip()
    if text in tokens:
        return True
    return _canonical_workshop_name(text, fallback='') in tokens


def _bounded_limit(value: int | None) -> int:
    try:
        limit = int(value if value is not None else DEFAULT_COIL_LIST_LIMIT)
    except (TypeError, ValueError):
        return DEFAULT_COIL_LIST_LIMIT
    return max(1, min(limit, MAX_COIL_LIST_LIMIT))


def _bounded_offset(value: int | None) -> int:
    try:
        offset = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(offset, 0)


def _matches_filter_text(row: Any, query: str | None) -> bool:
    text = str(query or '').strip().lower()
    if not text:
        return True
    fields = (
        'coil_id',
        'tracking_card_no',
        'batch_no',
        'contract_no',
        'material_code',
        'customer_alias',
        'alloy_grade',
        'material_state',
        'spec_display',
        'machine_code',
        'current_workshop',
        'current_process',
        'next_process',
        'status_name',
        'card_status_name',
        'production_status',
    )
    return any(text in str(getattr(row, field, '') or '').lower() for field in fields)


def _matches_destination_filter(row: Any, destination: str | None) -> bool:
    value = str(destination or '').strip()
    if not value:
        return True
    return _destination(row)['kind'] == value


def _is_sqlalchemy_query(query: Any) -> bool:
    return hasattr(query, 'column_descriptions') and hasattr(query, 'offset') and hasattr(query, 'limit')


def _projection_available(db: Session) -> bool:
    try:
        query = db.query(MesCoilSnapshot)
        if _is_sqlalchemy_query(query):
            return query.limit(1).first() is not None
        return _query_first(query) is not None
    except (OperationalError, ProgrammingError):
        return False


def _should_use_local_shift_data(db: Session, freshness: Mapping[str, Any]) -> bool:
    _ = freshness
    return not _projection_available(db)


def _local_freshness(freshness: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(freshness)
    payload['source'] = 'local_shift_data'
    return payload


def _mixed_freshness(freshness: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(freshness)
    payload['source'] = 'mixed'
    return payload


def _scope_workshop_ids(scope: ScopeSummary | None) -> set[int] | None:
    if scope is None or scope.is_admin or scope.data_scope_type == 'all':
        return None
    if scope.workshop_id is None:
        return set()
    return {int(scope.workshop_id)}


def _matches_workshop_id(value: Any, workshop_ids: set[int] | None) -> bool:
    if workshop_ids is None:
        return True
    if not workshop_ids:
        return False
    try:
        return int(value) in workshop_ids
    except (TypeError, ValueError):
        return False


def _local_shift_rows(db: Session, *, target_date: date, scope: ScopeSummary | None = None) -> list[Any]:
    workshop_ids = _scope_workshop_ids(scope)
    try:
        query = db.query(ShiftProductionData)
        if _is_sqlalchemy_query(query):
            query = query.filter(
                ShiftProductionData.business_date == target_date,
                or_(
                    ShiftProductionData.data_status.in_(LOCAL_SHIFT_STATUSES),
                    and_(
                        ShiftProductionData.data_status == 'pending',
                        ShiftProductionData.data_source.in_(LOCAL_PENDING_SHIFT_SOURCES),
                    ),
                ),
            )
            if workshop_ids is not None:
                query = query.filter(ShiftProductionData.workshop_id.in_(workshop_ids))
            return list(query.all())
        rows = _all(db, ShiftProductionData)
    except (OperationalError, ProgrammingError):
        return []
    return [
        row
        for row in rows
        if getattr(row, 'business_date', None) == target_date
        and (
            getattr(row, 'data_status', None) in LOCAL_SHIFT_STATUSES
            or (
                getattr(row, 'data_status', None) == 'pending'
                and getattr(row, 'data_source', None) in LOCAL_PENDING_SHIFT_SOURCES
            )
        )
        and _matches_workshop_id(getattr(row, 'workshop_id', None), workshop_ids)
    ]


def _local_mobile_report_rows(db: Session, *, target_date: date, scope: ScopeSummary | None = None) -> list[Any]:
    workshop_ids = _scope_workshop_ids(scope)
    try:
        query = db.query(MobileShiftReport)
        if _is_sqlalchemy_query(query):
            query = query.filter(
                MobileShiftReport.business_date == target_date,
                MobileShiftReport.report_status.in_(LOCAL_MOBILE_REPORT_STATUSES),
            )
            if workshop_ids is not None:
                query = query.filter(MobileShiftReport.workshop_id.in_(workshop_ids))
            return list(query.all())
        rows = _all(db, MobileShiftReport)
    except (OperationalError, ProgrammingError):
        return []
    return [
        row
        for row in rows
        if getattr(row, 'business_date', None) == target_date
        and getattr(row, 'report_status', None) in LOCAL_MOBILE_REPORT_STATUSES
        and _matches_workshop_id(getattr(row, 'workshop_id', None), workshop_ids)
    ]


def _local_rows(db: Session, *, target_date: date, scope: ScopeSummary | None = None) -> list[Any]:
    shift_rows = _local_shift_rows(db, target_date=target_date, scope=scope)
    shift_ids = {
        int(getattr(row, 'id'))
        for row in shift_rows
        if getattr(row, 'id', None) is not None
    }
    mobile_rows = [
        row
        for row in _local_mobile_report_rows(db, target_date=target_date, scope=scope)
        if getattr(row, 'linked_production_data_id', None) not in shift_ids
    ]
    return [*shift_rows, *mobile_rows]


def _latest_local_business_date(db: Session, *, fallback: date, scope: ScopeSummary | None = None) -> date:
    workshop_ids = _scope_workshop_ids(scope)
    dates: list[date] = []
    try:
        shift_rows = _all(db, ShiftProductionData)
    except (OperationalError, ProgrammingError):
        shift_rows = []
    for row in shift_rows:
        business_date = getattr(row, 'business_date', None)
        if business_date is None or business_date > fallback:
            continue
        if not _matches_workshop_id(getattr(row, 'workshop_id', None), workshop_ids):
            continue
        if getattr(row, 'data_status', None) in LOCAL_SHIFT_STATUSES or (
            getattr(row, 'data_status', None) == 'pending'
            and getattr(row, 'data_source', None) in LOCAL_PENDING_SHIFT_SOURCES
        ):
            dates.append(business_date)
    try:
        mobile_rows = _all(db, MobileShiftReport)
    except (OperationalError, ProgrammingError):
        mobile_rows = []
    for row in mobile_rows:
        business_date = getattr(row, 'business_date', None)
        if business_date is None or business_date > fallback:
            continue
        if not _matches_workshop_id(getattr(row, 'workshop_id', None), workshop_ids):
            continue
        if getattr(row, 'report_status', None) in LOCAL_MOBILE_REPORT_STATUSES:
            dates.append(business_date)
    return max(dates) if dates else fallback


def _workshop_name_map(db: Session) -> dict[int, str]:
    return {
        int(row.id): _canonical_workshop_name(getattr(row, 'name', None), fallback=str(row.name))
        for row in _safe_all(db, Workshop)
        if getattr(row, 'id', None) is not None
    }


def _equipment_map(db: Session) -> dict[int, Any]:
    return {
        int(row.id): row
        for row in _safe_all(db, Equipment)
        if getattr(row, 'id', None) is not None
    }


def _row_sort_time(row: Any) -> tuple[float, int]:
    value = (
        getattr(row, 'submitted_at', None)
        or getattr(row, 'confirmed_at', None)
        or getattr(row, 'updated_at', None)
        or getattr(row, 'created_at', None)
    )
    timestamp = value.timestamp() if hasattr(value, 'timestamp') else 0.0
    return (timestamp, int(getattr(row, 'id', 0) or 0))


def _local_issue_count(row: Any) -> int:
    if hasattr(row, 'issue_count'):
        return int(getattr(row, 'issue_count', 0) or 0)
    return 1 if getattr(row, 'has_exception', False) else 0


def _scope_coil_expression(tokens: set[str] | None):
    if tokens is None:
        return None
    if not tokens:
        return false()
    return or_(MesCoilSnapshot.current_workshop.in_(tokens), MesCoilSnapshot.workshop_code.in_(tokens))


def _workshop_expression(workshop: str | None):
    text = str(workshop or '').strip()
    if not text:
        return None
    tokens = _workshop_tokens(text)
    return or_(MesCoilSnapshot.current_workshop.in_(tokens), MesCoilSnapshot.workshop_code.in_(tokens))


def _filter_text_expression(query: str | None):
    text = str(query or '').strip()
    if not text:
        return None
    pattern = f'%{text}%'
    return or_(
        MesCoilSnapshot.coil_id.ilike(pattern),
        MesCoilSnapshot.tracking_card_no.ilike(pattern),
        MesCoilSnapshot.batch_no.ilike(pattern),
        MesCoilSnapshot.contract_no.ilike(pattern),
        MesCoilSnapshot.material_code.ilike(pattern),
        MesCoilSnapshot.customer_alias.ilike(pattern),
        MesCoilSnapshot.alloy_grade.ilike(pattern),
        MesCoilSnapshot.material_state.ilike(pattern),
        MesCoilSnapshot.spec_display.ilike(pattern),
        MesCoilSnapshot.machine_code.ilike(pattern),
        MesCoilSnapshot.current_workshop.ilike(pattern),
        MesCoilSnapshot.current_process.ilike(pattern),
        MesCoilSnapshot.next_process.ilike(pattern),
        MesCoilSnapshot.status_name.ilike(pattern),
        MesCoilSnapshot.card_status_name.ilike(pattern),
        MesCoilSnapshot.production_status.ilike(pattern),
    )


def _present_expression(column):
    return and_(column.isnot(None), column != '')


def _absent_expression(column):
    return or_(column.is_(None), column == '')


def _destination_expression(destination: str | None):
    value = str(destination or '').strip()
    if not value:
        return None
    no_delivery = MesCoilSnapshot.delivery_date.is_(None)
    no_allocation = MesCoilSnapshot.allocation_date.is_(None)
    not_finished_stock = and_(
        MesCoilSnapshot.in_stock_date.is_(None),
        or_(MesCoilSnapshot.status_name.is_(None), MesCoilSnapshot.status_name != '已入库'),
    )
    if value == 'delivery':
        return MesCoilSnapshot.delivery_date.isnot(None)
    if value == 'allocation':
        return and_(no_delivery, MesCoilSnapshot.allocation_date.isnot(None))
    if value == 'finished_stock':
        return and_(
            no_delivery,
            no_allocation,
            or_(MesCoilSnapshot.in_stock_date.isnot(None), MesCoilSnapshot.status_name == '已入库'),
        )
    if value == 'in_progress':
        return and_(
            no_delivery,
            no_allocation,
            not_finished_stock,
            or_(_present_expression(MesCoilSnapshot.current_process), _present_expression(MesCoilSnapshot.next_process)),
        )
    if value == 'unknown':
        return and_(
            no_delivery,
            no_allocation,
            not_finished_stock,
            _absent_expression(MesCoilSnapshot.current_process),
            _absent_expression(MesCoilSnapshot.next_process),
        )
    return false()


def _paged_coils(
    db: Session,
    *,
    scope: ScopeSummary | None = None,
    limit: int,
    offset: int,
    workshop: str | None = None,
    destination: str | None = None,
    query: str | None = None,
) -> list[Any]:
    coil_query = db.query(MesCoilSnapshot)
    if not _is_sqlalchemy_query(coil_query):
        rows = _filter_coils(_scoped_coils(db, scope=scope), workshop=workshop, destination=destination, query=query)
        return rows[offset : offset + limit]

    expressions = (
        _scope_coil_expression(_scope_workshop_tokens(db, scope)),
        _workshop_expression(workshop),
        _destination_expression(destination),
        _filter_text_expression(query),
    )
    for expression in expressions:
        if expression is not None:
            coil_query = coil_query.filter(expression)
    return list(coil_query.order_by(MesCoilSnapshot.id.asc()).offset(offset).limit(limit).all())


def _filter_coils(
    rows: Iterable[Any],
    *,
    workshop: str | None = None,
    destination: str | None = None,
    query: str | None = None,
) -> list[Any]:
    workshop_text = str(workshop or '').strip()
    workshop_tokens = _workshop_tokens(workshop_text) if workshop_text else set()
    return [
        row
        for row in rows
        if (
            not workshop_text
            or str(getattr(row, 'current_workshop', '') or '').strip() in workshop_tokens
            or _canonical_workshop_name(getattr(row, 'current_workshop', None), fallback='') in workshop_tokens
            or str(getattr(row, 'workshop_code', '') or '').strip() in workshop_tokens
        )
        and _matches_destination_filter(row, destination)
        and _matches_filter_text(row, query)
    ]


def _scoped_coils(db: Session, *, scope: ScopeSummary | None = None) -> list[Any]:
    tokens = _scope_workshop_tokens(db, scope)
    return [
        row
        for row in _all(db, MesCoilSnapshot)
        if _matches_workshop(getattr(row, 'current_workshop', None), tokens)
        or _matches_workshop(getattr(row, 'workshop_code', None), tokens)
    ]


def _scoped_machine_lines(db: Session, *, scope: ScopeSummary | None = None) -> list[Any]:
    tokens = _scope_workshop_tokens(db, scope)
    return [row for row in _all(db, MesMachineLineSnapshot) if _matches_workshop(getattr(row, 'workshop_name', None), tokens)]


def _latest_events_by_coil(db: Session, coil_keys: set[str]) -> dict[str, Any]:
    if not coil_keys:
        return {}
    latest: dict[str, Any] = {}
    query = db.query(CoilFlowEvent)
    events = query.filter(CoilFlowEvent.coil_key.in_(coil_keys)).all() if _is_sqlalchemy_query(query) else _all(db, CoilFlowEvent)
    for event in events:
        if event.coil_key not in coil_keys:
            continue
        current = latest.get(event.coil_key)
        if current is None or _event_sort_key(event) > _event_sort_key(current):
            latest[event.coil_key] = event
    return latest


def _slot_no(name: str | None) -> int | None:
    text = str(name or '').strip()
    if '#' not in text:
        return None
    try:
        return int(float(text.split('#', 1)[0]))
    except ValueError:
        return None


def _alias_key(value: Any) -> str:
    return ''.join(str(value or '').strip().lower().split())


def _iter_payload_aliases(payload: Any) -> Iterable[str]:
    if not isinstance(payload, Mapping):
        return []
    aliases: list[str] = []
    for key, value in payload.items():
        lowered = str(key).lower()
        if not any(part in lowered for part in ('alias', 'device', 'machine', 'line', 'code', 'name')):
            continue
        if isinstance(value, (list, tuple, set)):
            aliases.extend(str(item) for item in value if item)
        elif value:
            aliases.append(str(value))
    return aliases


def _line_alias_map(line_rows: Iterable[Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for line in line_rows:
        line_code = str(getattr(line, 'line_code', '') or '').strip()
        if not line_code:
            continue
        candidates = [
            line_code,
            getattr(line, 'line_name', None),
            *list(_iter_payload_aliases(getattr(line, 'source_payload', None))),
        ]
        for candidate in candidates:
            key = _alias_key(candidate)
            if key:
                aliases.setdefault(key, line_code)
    return aliases


def _coil_machine_aliases(row: Any) -> list[str]:
    return [
        str(value)
        for value in (
            getattr(row, 'machine_code', None),
            *_iter_payload_aliases(getattr(row, 'source_payload', None)),
        )
        if value
    ]


def _unmatched_line_code_for_coil(row: Any) -> str:
    workshop = _canonical_workshop_name(getattr(row, 'current_workshop', None), fallback='') or '未知车间'
    return f'未匹配机列:{workshop}'


def _line_code_for_coil(row: Any, line_aliases: Mapping[str, str]) -> str | None:
    machine_code = str(getattr(row, 'machine_code', None) or '').strip()
    if not machine_code:
        return None
    for alias in _coil_machine_aliases(row):
        line_code = line_aliases.get(_alias_key(alias))
        if line_code:
            return line_code
    slot_no = _slot_no(machine_code)
    workshop = _canonical_workshop_name(getattr(row, 'current_workshop', None), fallback='')
    if workshop and slot_no is not None:
        return f'{workshop}:{slot_no:02d}'
    return machine_code


def _event_sort_key(event: Any) -> tuple[float, int]:
    value = getattr(event, 'event_time', None) or getattr(event, 'created_at', None)
    timestamp = value.timestamp() if hasattr(value, 'timestamp') else 0.0
    return (timestamp, getattr(event, 'id', 0) or 0)


def _business_date(now: Any = None) -> date:
    current = now or datetime.now(timezone.utc)
    if isinstance(current, datetime):
        return resolve_production_business_date(current)
    if isinstance(current, date):
        return current
    return resolve_production_business_date(datetime.now(timezone.utc))


def _is_explicit_business_date(value: Any) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _same_business_date(value: Any, target: date) -> bool:
    if isinstance(value, datetime):
        return resolve_production_business_date(value) == target
    if isinstance(value, date):
        return value == target
    return False


def _mes_extended_freshness(freshness: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(freshness)
    payload['source'] = 'mes_extended'
    return payload


def _scoped_mes_extended_rows(
    db: Session,
    model: type,
    *,
    scope: ScopeSummary | None = None,
    workshop_field: str | None = 'workshop_name',
) -> list[Any]:
    tokens = _scope_workshop_tokens(db, scope)
    rows = _safe_all(db, model)
    if tokens is None:
        return rows
    if not tokens or not workshop_field:
        return []
    return [row for row in rows if _matches_workshop(getattr(row, workshop_field, None), tokens)]


def _latest_mes_extended_business_date(db: Session, *, fallback: date, scope: ScopeSummary | None = None) -> date:
    dates: list[date] = []
    for model, workshop_field in (
        (MesWorkshopProcessRecord, 'workshop_name'),
        (MesDailyWipSnapshot, 'workshop_name'),
        (MesStockRecord, None),
        (MesYieldRecord, None),
    ):
        for row in _scoped_mes_extended_rows(db, model, scope=scope, workshop_field=workshop_field):
            business_date = getattr(row, 'business_date', None)
            if isinstance(business_date, datetime):
                business_date = business_date.date()
            if isinstance(business_date, date) and business_date <= fallback:
                dates.append(business_date)
    return max(dates) if dates else fallback


def _mes_extended_rows_for_date(rows: Iterable[Any], target_date: date) -> list[Any]:
    return [row for row in rows if _same_business_date(getattr(row, 'business_date', None), target_date)]


def _daily_wip_rows_for_date(db: Session, *, target_date: date, scope: ScopeSummary | None = None) -> list[Any]:
    return _mes_extended_rows_for_date(
        _scoped_mes_extended_rows(db, MesDailyWipSnapshot, scope=scope, workshop_field='workshop_name'),
        target_date,
    )


def _latest_wip_snapshots(rows: Iterable[Any]) -> list[Any]:
    row_list = list(rows)
    if not row_list:
        return []
    latest = max(
        (
            getattr(row, 'snapshot_at', None)
            for row in row_list
            if getattr(row, 'snapshot_at', None) is not None
        ),
        default=None,
    )
    if latest is None:
        return row_list
    return [row for row in row_list if getattr(row, 'snapshot_at', None) == latest]


def _build_overview_from_mes_extended(
    db: Session,
    *,
    freshness: Mapping[str, Any],
    target_date: date,
    scope: ScopeSummary | None = None,
    abnormal_count: int = 0,
    previous_day: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    process_rows = _mes_extended_rows_for_date(
        _scoped_mes_extended_rows(db, MesWorkshopProcessRecord, scope=scope, workshop_field='workshop_name'),
        target_date,
    )
    stock_rows = _scoped_mes_extended_rows(db, MesStockRecord, scope=scope, workshop_field=None)
    today_stock_rows = _mes_extended_rows_for_date(stock_rows, target_date)
    yield_rows = _mes_extended_rows_for_date(
        _scoped_mes_extended_rows(db, MesYieldRecord, scope=scope, workshop_field=None),
        target_date,
    )
    daily_wip_rows = _daily_wip_rows_for_date(db, target_date=target_date, scope=scope)
    wip_rows = _latest_wip_snapshots(
        _scoped_mes_extended_rows(db, MesWipTotalSnapshot, scope=scope, workshop_field='workshop_name')
    )
    if not (process_rows or stock_rows or yield_rows or daily_wip_rows or wip_rows):
        return None

    total_input = sum(_number(getattr(row, 'input_weight_tons', None)) for row in process_rows)
    total_output = sum(_number(getattr(row, 'output_weight_tons', None)) for row in process_rows)
    today_output = sum(_number(getattr(row, 'net_weight_tons', None)) for row in today_stock_rows)
    stock_total = today_output
    daily_wip_total = sum(_number(getattr(row, 'material_weight_tons', None)) for row in daily_wip_rows)
    wip_total = daily_wip_total if daily_wip_rows else sum(_number(getattr(row, 'doing_weight_tons', None)) for row in wip_rows)
    if wip_total <= 0 and total_input > 0:
        wip_total = max(total_input - total_output, 0.0)

    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in process_rows:
        grouped[_canonical_workshop_name(getattr(row, 'workshop_name', None))].append(row)
    workshop_summary = []
    for workshop_name, rows in grouped.items():
        workshop_input = sum(_number(getattr(row, 'input_weight_tons', None)) for row in rows)
        workshop_output = sum(_number(getattr(row, 'output_weight_tons', None)) for row in rows)
        workshop_summary.append(
            {
                'workshop_name': workshop_name,
                'row_count': len(rows),
                'total_input_tons': round(workshop_input, 4),
                'total_output_tons': round(workshop_output, 4),
                'yield_rate': round(workshop_output / workshop_input * 100, 2) if workshop_input else None,
            }
        )
    if not workshop_summary and daily_wip_rows:
        wip_grouped: dict[str, list[Any]] = defaultdict(list)
        for row in daily_wip_rows:
            wip_grouped[_canonical_workshop_name(getattr(row, 'workshop_name', None))].append(row)
        for workshop_name, rows in wip_grouped.items():
            workshop_summary.append(
                {
                    'workshop_name': workshop_name,
                    'row_count': sum(int(_number(getattr(row, 'coil_count', None))) for row in rows),
                    'total_input_tons': round(sum(_number(getattr(row, 'feeding_weight_tons', None)) for row in rows), 4),
                    'total_output_tons': round(sum(_number(getattr(row, 'material_weight_tons', None)) for row in rows), 4),
                    'yield_rate': None,
                }
            )
    process_yield_rate = round(total_output / total_input * 100, 2) if total_input else None
    rates = [_number(getattr(row, 'yield_rate', None)) for row in yield_rows]
    rates = [value for value in rates if value > 0]
    yield_rate = round(sum(rates) / len(rates), 2) if rates else None

    missing_data = ['cost_inputs']
    response_freshness = _mes_extended_freshness(freshness)
    return {
        'business_date': target_date.isoformat(),
        'source': response_freshness['source'],
        'freshness': response_freshness,
        'wip_tons': round(wip_total, 4),
        'today_output_tons': round(today_output, 4),
        'stock_tons': round(stock_total, 4),
        'total_input_tons': round(total_input, 4),
        'total_output_tons': round(total_output, 4),
        'process_output_tons': round(total_output, 4),
        'yield_rate': yield_rate,
        'process_yield_rate': process_yield_rate,
        'output_basis': 'mes_stock_records' if today_output > 0 else 'none',
        'process_output_basis': 'mes_workshop_process_records' if process_rows else 'none',
        'workshop_summary': sorted(workshop_summary, key=lambda item: item['total_output_tons'], reverse=True),
        'abnormal_count': abnormal_count,
        'cost_estimate': _estimate(missing_data=missing_data),
        'missing_data': missing_data,
        'previous_day': previous_day,
    }


def _estimate(*, missing_data: list[str] | None = None, label: str = '经营估算') -> dict[str, Any]:
    return {
        'label': label,
        'estimated_cost': None,
        'estimated_gross_margin': None,
        'missing_data': missing_data or ['cost_inputs'],
    }


def build_freshness(db: Session, *, now=None) -> dict[str, Any]:
    status = latest_sync_status(db, now=now if isinstance(now, datetime) else None)
    lag_seconds = (
        status.get('sync_lag_seconds')
        if status.get('sync_lag_seconds') is not None
        else status.get('sync_freshness_seconds')
    )
    if lag_seconds is None:
        lag_seconds = status.get('lag_seconds')
    source_lag_seconds = status.get('source_lag_seconds')
    source_status = status.get('status')
    if source_status in {'unconfigured', 'migration_missing', 'failed'}:
        freshness_status = source_status
    elif lag_seconds is None:
        freshness_status = source_status or 'idle'
    elif lag_seconds > 300:
        freshness_status = 'stale'
    else:
        freshness_status = 'fresh'
    risk_tone = 'high' if lag_seconds is not None and lag_seconds > 900 else 'normal'
    payload = {
        'status': freshness_status,
        'lag_seconds': lag_seconds,
        'last_synced_at': status.get('last_synced_at'),
        'last_event_at': status.get('last_event_at'),
        'source': status.get('source') or 'mes_projection',
        'configured': status.get('configured', True),
        'migration_ready': status.get('migration_ready', True),
        'action_required': status.get('action_required', 'none'),
        'risk_tone': risk_tone,
    }
    if 'sync_lag_seconds' in status or 'sync_freshness_seconds' in status:
        payload['sync_lag_seconds'] = lag_seconds
        payload['sync_freshness_seconds'] = status.get('sync_freshness_seconds')
    if 'source_lag_seconds' in status:
        payload['source_lag_seconds'] = source_lag_seconds
    return payload


def _live_source_freshness(freshness: Mapping[str, Any], source: str | None) -> dict[str, Any]:
    payload = dict(freshness)
    payload['source'] = source or payload.get('source') or 'work_order_runtime'
    return payload


def _live_fill_entry_count(payload: Mapping[str, Any] | None) -> int:
    if not payload:
        return 0
    progress = payload.get('overall_progress') or {}
    pending_assignment = progress.get('pending_assignment') or {}
    return int(progress.get('total_entry_count') or 0) + int(pending_assignment.get('entry_count') or 0)


def _live_payload_source(payload: Mapping[str, Any]) -> str:
    source = str(payload.get('data_source') or 'work_order_runtime')
    if source == 'mes_projection':
        progress = payload.get('overall_progress') or {}
        pending_assignment = progress.get('pending_assignment') or {}
        fill_count = int(progress.get('total_entry_count') or 0) + int(pending_assignment.get('entry_count') or 0)
        if fill_count > 0:
            return 'mixed'
    return source


def _live_aggregation_for_factory_command(
    db: Session,
    *,
    current_user: Any | None,
    now=None,
) -> dict[str, Any] | None:
    if current_user is None:
        return None
    try:
        from app.services import realtime_service

        resolved_now = now if isinstance(now, datetime) else None
        active_date = realtime_service.resolve_live_business_date(
            db,
            today=_business_date(now),
            now=resolved_now,
        )
        business_date = date.fromisoformat(str(active_date['business_date']))
        payload = realtime_service.build_live_aggregation(
            db,
            business_date=business_date,
            workshop_id=None,
            current_user=current_user,
        )
    except (OperationalError, ProgrammingError, KeyError, ValueError):
        return None
    return payload if _live_fill_entry_count(payload) > 0 else None


def _live_shift_entry_count(shift: Mapping[str, Any]) -> int:
    return int(shift.get('submitted_count') or 0) + int(shift.get('draft_count') or 0)


def _live_workshop_attention_count(workshop: Mapping[str, Any]) -> int:
    count = 0
    for machine in workshop.get('machines') or []:
        for shift in machine.get('shifts') or []:
            if shift.get('is_applicable') is False or _live_shift_entry_count(shift) <= 0:
                continue
            if shift.get('status_tone') in {'danger', 'warning'}:
                count += 1
    return count


def _overview_from_live_aggregation(
    payload: Mapping[str, Any],
    *,
    freshness: Mapping[str, Any],
) -> dict[str, Any]:
    source = _live_payload_source(payload)
    response_freshness = _live_source_freshness(freshness, source)
    factory_total = payload.get('factory_total') or {}
    total_input = _number(factory_total.get('input'))
    total_output = _number(factory_total.get('output'))
    grouped_summary: dict[str, dict[str, Any]] = {}
    for workshop in payload.get('workshops') or []:
        workshop_total = workshop.get('workshop_total') or {}
        row_count = int(workshop_total.get('total_entry_count') or 0)
        output = _number(workshop_total.get('output'))
        if row_count <= 0 and output <= 0:
            continue
        input_weight = _number(workshop_total.get('input'))
        workshop_name = _canonical_workshop_name(
            workshop.get('workshop_name') or f"车间{workshop.get('workshop_id')}",
        )
        existing = grouped_summary.setdefault(
            workshop_name,
            {
                'workshop_id': workshop.get('workshop_id'),
                'workshop_name': workshop_name,
                'row_count': 0,
                'total_input_tons': 0.0,
                'total_output_tons': 0.0,
                'yield_rate': workshop_total.get('yield_rate'),
            },
        )
        existing['row_count'] += row_count
        existing['total_input_tons'] = round(existing['total_input_tons'] + input_weight, 4)
        existing['total_output_tons'] = round(existing['total_output_tons'] + output, 4)
    workshop_summary = list(grouped_summary.values())
    progress = payload.get('overall_progress') or {}
    return {
        'business_date': str(payload.get('business_date') or ''),
        'source': response_freshness['source'],
        'freshness': response_freshness,
        'wip_tons': round(max(total_input - total_output, 0.0), 4),
        'today_output_tons': round(total_output, 4),
        'stock_tons': round(total_output, 4),
        'total_input_tons': round(total_input, 4),
        'total_output_tons': round(total_output, 4),
        'process_output_tons': round(total_output, 4),
        'yield_rate': factory_total.get('yield_rate'),
        'process_yield_rate': factory_total.get('yield_rate'),
        'output_basis': 'live_aggregation',
        'process_output_basis': 'live_aggregation_factory_total',
        'workshop_summary': sorted(workshop_summary, key=lambda item: item['total_output_tons'], reverse=True),
        'abnormal_count': int(progress.get('attention_cell_count') or 0) + int(progress.get('missing_cell_count') or 0),
        'cost_estimate': _estimate(missing_data=['cost_inputs']),
        'missing_data': ['cost_inputs'],
    }


def _workshops_from_live_aggregation(
    payload: Mapping[str, Any],
    *,
    freshness: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source = _live_payload_source(payload)
    response_freshness = _live_source_freshness(freshness, source)
    by_name: dict[str, dict[str, Any]] = {}
    for workshop in payload.get('workshops') or []:
        total = workshop.get('workshop_total') or {}
        row_count = int(total.get('total_entry_count') or 0)
        output = _number(total.get('output'))
        if row_count <= 0 and output <= 0:
            continue
        workshop_name = _canonical_workshop_name(workshop.get('workshop_name') or f"车间{workshop.get('workshop_id')}")
        existing = by_name.get(workshop_name)
        if existing is None:
            by_name[workshop_name] = {
                'workshop_name': workshop_name,
                'active_coil_count': row_count,
                'active_tons': round(output, 4),
                'stalled_count': _live_workshop_attention_count(workshop),
                'freshness': response_freshness,
            }
            continue
        existing['active_coil_count'] += row_count
        existing['active_tons'] = round(existing['active_tons'] + output, 4)
        existing['stalled_count'] += _live_workshop_attention_count(workshop)
    items = list(by_name.values())
    return sorted(items, key=lambda item: item['active_tons'], reverse=True)


def _machine_lines_from_live_aggregation(
    db: Session,
    payload: Mapping[str, Any],
    *,
    freshness: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source = _live_payload_source(payload)
    response_freshness = _live_source_freshness(freshness, source)
    equipment_by_id = _equipment_map(db)
    items = []
    for workshop in payload.get('workshops') or []:
        workshop_name = _canonical_workshop_name_or_none(workshop.get('workshop_name'))
        for machine in workshop.get('machines') or []:
            machine_id = machine.get('machine_id')
            shifts = machine.get('shifts') or []
            entry_count = sum(_live_shift_entry_count(shift) for shift in shifts)
            output = _number((machine.get('day_total') or {}).get('output'))
            if entry_count <= 0 and output <= 0:
                continue
            binding_status = str(machine.get('machine_binding_status') or '').strip() or 'bound'
            equipment = equipment_by_id.get(int(machine_id)) if machine_id is not None and int(machine_id) > 0 else None
            is_unbound = binding_status == 'unbound' or (machine_id is not None and int(machine_id) < 0)
            line_code = (
                f"workshop:{workshop.get('workshop_id')}:machine:{machine_id}:unbound"
                if is_unbound
                else str(getattr(equipment, 'code', None) or f'equipment:{machine_id}')
            )
            attention_count = sum(
                1
                for shift in shifts
                if shift.get('is_applicable') is not False
                and _live_shift_entry_count(shift) > 0
                and shift.get('status_tone') in {'danger', 'warning'}
            )
            items.append(
                {
                    'line_code': line_code,
                    'line_name': machine.get('machine_name') or getattr(equipment, 'name', None),
                    'workshop_name': workshop_name,
                    'active_coil_count': entry_count,
                    'active_tons': round(output, 4),
                    'finished_tons': round(output, 4),
                    'stalled_count': attention_count,
                    'machine_binding_status': 'unbound' if is_unbound else 'bound',
                    'mes_binding': _machine_mes_binding(machine.get('mes_binding')),
                    'cost_estimate': _estimate(),
                    'margin_estimate': _estimate(label='毛差估算'),
                    'freshness': response_freshness,
                }
            )
    return sorted(items, key=lambda item: item['line_code'])


def _build_overview_from_shift_data(
    db: Session,
    *,
    freshness: Mapping[str, Any],
    target_date: date,
    scope: ScopeSummary | None = None,
) -> dict[str, Any]:
    rows = _local_rows(db, target_date=target_date, scope=scope)
    total_input = sum(_local_weight_tons(row, 'input_weight') for row in rows)
    total_output = sum(_local_weight_tons(row, 'output_weight') for row in rows)
    total_qualified = sum(
        _local_weight_tons(row, 'qualified_weight')
        if getattr(row, 'qualified_weight', None) is not None
        else _local_weight_tons(row, 'output_weight')
        for row in rows
    )
    wip_tons = max(total_input - total_output, 0.0)
    missing_data = ['cost_inputs']
    workshop_summary = []
    workshop_names = _workshop_name_map(db)
    grouped: dict[int, list[Any]] = defaultdict(list)
    for row in rows:
        workshop_id = getattr(row, 'workshop_id', None)
        if workshop_id is not None:
            grouped[int(workshop_id)].append(row)
    for workshop_id, workshop_rows in grouped.items():
        workshop_input = sum(_local_weight_tons(row, 'input_weight') for row in workshop_rows)
        workshop_output = sum(_local_weight_tons(row, 'output_weight') for row in workshop_rows)
        workshop_summary.append(
            {
                'workshop_id': workshop_id,
                'workshop_name': workshop_names.get(workshop_id, f'车间{workshop_id}'),
                'row_count': len(workshop_rows),
                'total_input_tons': round(workshop_input, 4),
                'total_output_tons': round(workshop_output, 4),
                'yield_rate': round(workshop_output / workshop_input * 100, 2) if workshop_input else None,
            }
        )
    return {
        'business_date': target_date.isoformat(),
        'source': 'local_shift_data',
        'freshness': _local_freshness(freshness),
        'wip_tons': round(wip_tons, 4),
        'today_output_tons': round(total_output, 4),
        'stock_tons': round(total_qualified, 4),
        'total_input_tons': round(total_input, 4),
        'total_output_tons': round(total_output, 4),
        'yield_rate': round(total_output / total_input * 100, 2) if total_input else None,
        'workshop_summary': sorted(workshop_summary, key=lambda item: item['total_output_tons'], reverse=True),
        'abnormal_count': sum(1 for row in rows if _local_issue_count(row) > 0),
        'cost_estimate': _estimate(missing_data=missing_data),
        'missing_data': missing_data,
    }


def _has_local_overview_rows(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get('workshop_summary'))


def _build_previous_day_summary(
    db: Session,
    *,
    today: date,
    scope: ScopeSummary | None = None,
) -> dict[str, Any] | None:
    yesterday = today - timedelta(days=1)
    rows = _local_rows(db, target_date=yesterday, scope=scope)
    if not rows:
        return None
    total_input = sum(_local_weight_tons(row, 'input_weight') for row in rows)
    total_output = sum(_local_weight_tons(row, 'output_weight') for row in rows)
    return {
        'business_date': yesterday.isoformat(),
        'total_input_tons': round(total_input, 4),
        'total_output_tons': round(total_output, 4),
        'yield_rate': round(total_output / total_input * 100, 2) if total_input else None,
    }


def build_overview(db: Session, *, now=None, scope: ScopeSummary | None = None, current_user: Any | None = None) -> dict[str, Any]:
    freshness = build_freshness(db, now=now)
    today = _business_date(now)
    explicit_target_date = _is_explicit_business_date(now)
    previous_day = _build_previous_day_summary(db, today=today, scope=scope)
    live_payload = _live_aggregation_for_factory_command(db, current_user=current_user, now=now)
    if live_payload is not None:
        result = _overview_from_live_aggregation(live_payload, freshness=freshness)
        if not result.get('business_date'):
            result['business_date'] = today.isoformat()
        result['previous_day'] = previous_day
        return result
    target_date = today if explicit_target_date else _latest_local_business_date(db, fallback=today, scope=scope)
    if _should_use_local_shift_data(db, freshness):
        result = _build_overview_from_shift_data(
            db,
            freshness=freshness,
            target_date=target_date,
            scope=scope,
        )
        if not _has_local_overview_rows(result):
            extended_target_date = target_date if explicit_target_date else _latest_mes_extended_business_date(db, fallback=today, scope=scope)
            extended_result = _build_overview_from_mes_extended(
                db,
                freshness=freshness,
                target_date=extended_target_date,
                scope=scope,
                previous_day=previous_day,
            )
            if extended_result is not None:
                return extended_result
        result['previous_day'] = previous_day
        return result

    rows = _scoped_coils(db, scope=scope)
    stock_rows = [row for row in rows if _destination(row)['kind'] == 'finished_stock']
    current_date = _business_date(now)
    today_output_rows = [
        row
        for row in stock_rows
        if _same_business_date(getattr(row, 'in_stock_date', None), current_date)
    ]
    wip_rows = [row for row in rows if _destination(row)['kind'] == 'in_progress']
    abnormal_count = sum(1 for row in rows if _is_stalled(row))
    missing_data = ['cost_inputs']
    today_output_tons = round(sum(_weight(row) for row in today_output_rows), 4)
    local_overview = _build_overview_from_shift_data(
        db,
        freshness=freshness,
        target_date=target_date,
        scope=scope,
    )
    has_local_rows = _has_local_overview_rows(local_overview)
    local_output_tons = local_overview['total_output_tons'] if has_local_rows else 0.0
    response_freshness = _mixed_freshness(freshness) if has_local_rows else freshness
    if not has_local_rows:
        extended_target_date = target_date if explicit_target_date else _latest_mes_extended_business_date(db, fallback=current_date, scope=scope)
        extended_overview = _build_overview_from_mes_extended(
            db,
            freshness=freshness,
            target_date=extended_target_date,
            scope=scope,
            abnormal_count=abnormal_count,
            previous_day=previous_day,
        )
        if extended_overview is not None:
            return extended_overview
    return {
        'business_date': target_date.isoformat(),
        'source': response_freshness.get('source') or 'mes_projection',
        'freshness': response_freshness,
        'wip_tons': round(sum(_weight(row) for row in wip_rows), 4),
        'today_output_tons': round(max(today_output_tons, local_output_tons), 4),
        'stock_tons': round(sum(_weight(row) for row in stock_rows), 4),
        'total_input_tons': local_overview['total_input_tons'] if has_local_rows else 0.0,
        'total_output_tons': local_overview['total_output_tons'] if has_local_rows else today_output_tons,
        'yield_rate': local_overview['yield_rate'] if has_local_rows else None,
        'workshop_summary': local_overview['workshop_summary'] if has_local_rows else [],
        'abnormal_count': abnormal_count + (local_overview['abnormal_count'] if has_local_rows else 0),
        'cost_estimate': _estimate(missing_data=missing_data),
        'missing_data': missing_data,
        'previous_day': previous_day,
    }


def _list_workshops_from_shift_data(
    db: Session,
    *,
    freshness: Mapping[str, Any],
    target_date: date,
    scope: ScopeSummary | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[int, list[Any]] = defaultdict(list)
    for row in _local_rows(db, target_date=target_date, scope=scope):
        workshop_id = getattr(row, 'workshop_id', None)
        if workshop_id is not None:
            grouped[int(workshop_id)].append(row)
    workshop_names = _workshop_name_map(db)
    items = []
    for workshop_id, rows in grouped.items():
        items.append(
            {
                'workshop_name': workshop_names.get(workshop_id, f'车间{workshop_id}'),
                'active_coil_count': len(rows),
                'active_tons': round(sum(_local_weight_tons(row, 'output_weight') for row in rows), 4),
                'stalled_count': sum(1 for row in rows if _local_issue_count(row) > 0),
                'freshness': _local_freshness(freshness),
            }
        )
    return sorted(items, key=lambda item: item['active_tons'], reverse=True)


def _list_workshops_from_mes_extended(
    db: Session,
    *,
    freshness: Mapping[str, Any],
    target_date: date,
    scope: ScopeSummary | None = None,
) -> list[dict[str, Any]]:
    rows = _mes_extended_rows_for_date(
        _scoped_mes_extended_rows(db, MesWorkshopProcessRecord, scope=scope, workshop_field='workshop_name'),
        target_date,
    )
    response_freshness = _mes_extended_freshness(freshness)
    if not rows:
        daily_wip_rows = _daily_wip_rows_for_date(db, target_date=target_date, scope=scope)
        grouped_wip: dict[str, list[Any]] = defaultdict(list)
        for row in daily_wip_rows:
            grouped_wip[_canonical_workshop_name(getattr(row, 'workshop_name', None))].append(row)
        return sorted(
            [
                {
                    'workshop_name': workshop_name,
                    'active_coil_count': sum(int(_number(getattr(row, 'coil_count', None))) for row in workshop_rows),
                    'active_tons': round(sum(_number(getattr(row, 'material_weight_tons', None)) for row in workshop_rows), 4),
                    'stalled_count': 0,
                    'freshness': response_freshness,
                }
                for workshop_name, workshop_rows in grouped_wip.items()
            ],
            key=lambda item: item['active_tons'],
            reverse=True,
        )
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[_canonical_workshop_name(getattr(row, 'workshop_name', None))].append(row)
    items = []
    for workshop_name, workshop_rows in grouped.items():
        items.append(
            {
                'workshop_name': workshop_name,
                'active_coil_count': len(workshop_rows),
                'active_tons': round(sum(_number(getattr(row, 'output_weight_tons', None)) for row in workshop_rows), 4),
                'stalled_count': 0,
                'freshness': response_freshness,
            }
        )
    return sorted(items, key=lambda item: item['active_tons'], reverse=True)


def list_workshops(
    db: Session,
    *,
    scope: ScopeSummary | None = None,
    now=None,
    current_user: Any | None = None,
) -> list[dict[str, Any]]:
    freshness = build_freshness(db, now=now)
    live_payload = _live_aggregation_for_factory_command(db, current_user=current_user, now=now)
    if live_payload is not None:
        return _workshops_from_live_aggregation(live_payload, freshness=freshness)
    target_date = _latest_local_business_date(db, fallback=_business_date(now), scope=scope)
    if _should_use_local_shift_data(db, freshness):
        local_items = _list_workshops_from_shift_data(
            db,
            freshness=freshness,
            target_date=target_date,
            scope=scope,
        )
        if local_items:
            return local_items
        extended_target_date = _latest_mes_extended_business_date(db, fallback=_business_date(now), scope=scope)
        extended_items = _list_workshops_from_mes_extended(
            db,
            freshness=freshness,
            target_date=extended_target_date,
            scope=scope,
        )
        return extended_items

    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in _scoped_coils(db, scope=scope):
        grouped[_canonical_workshop_name(getattr(row, 'current_workshop', None))].append(row)
    items = []
    for workshop_name, rows in grouped.items():
        items.append(
            {
                'workshop_name': workshop_name,
                'active_coil_count': len(rows),
                'active_tons': round(sum(_weight(row) for row in rows), 4),
                'stalled_count': sum(1 for row in rows if _is_stalled(row)),
                'freshness': freshness,
            }
        )
    local_items = _list_workshops_from_shift_data(
        db,
        freshness=freshness,
        target_date=target_date,
        scope=scope,
    )
    if not local_items:
        extended_target_date = _latest_mes_extended_business_date(db, fallback=_business_date(now), scope=scope)
        extended_items = _list_workshops_from_mes_extended(
            db,
            freshness=freshness,
            target_date=extended_target_date,
            scope=scope,
        )
        if extended_items:
            return extended_items
    by_name = {_canonical_workshop_name(item['workshop_name']): item for item in items}
    for local_item in local_items:
        local_item['workshop_name'] = _canonical_workshop_name(local_item['workshop_name'])
        existing = by_name.get(str(local_item['workshop_name']))
        if existing is None:
            items.append(local_item)
            by_name[str(local_item['workshop_name'])] = local_item
            continue
        existing['active_coil_count'] += local_item['active_coil_count']
        existing['active_tons'] = round(existing['active_tons'] + local_item['active_tons'], 4)
        existing['stalled_count'] += local_item['stalled_count']
        existing['freshness'] = _mixed_freshness(freshness)
    return sorted(items, key=lambda item: item['active_tons'], reverse=True)


def _list_machine_lines_from_shift_data(
    db: Session,
    *,
    freshness: Mapping[str, Any],
    target_date: date,
    scope: ScopeSummary | None = None,
) -> list[dict[str, Any]]:
    equipment_by_id = _equipment_map(db)
    reporting_candidates = list(equipment_by_id.values())
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in _local_shift_rows(db, target_date=target_date, scope=scope):
        equipment_id = getattr(row, 'equipment_id', None)
        if equipment_id is not None:
            raw_equipment_id = int(equipment_id)
            equipment = equipment_by_id.get(raw_equipment_id)
            reporting_equipment = resolve_reporting_machine_from_candidates(equipment, reporting_candidates)
            reporting_equipment_id = int(getattr(reporting_equipment, 'id', raw_equipment_id) or raw_equipment_id)
            grouped[f'equipment:{reporting_equipment_id}'].append(row)
            continue
        workshop_id = getattr(row, 'workshop_id', None)
        shift_id = getattr(row, 'shift_config_id', None)
        workshop_key = workshop_id if workshop_id is not None else 'unknown'
        shift_key = shift_id if shift_id is not None else 'unknown'
        grouped[f'workshop:{workshop_key}:shift:{shift_key}:unbound'].append(row)
    workshop_names = _workshop_name_map(db)
    items = []
    for group_key, rows in grouped.items():
        latest_row = max(rows, key=_row_sort_time)
        grouped_equipment_id = int(group_key.split(':', 1)[1]) if group_key.startswith('equipment:') else None
        equipment_id = grouped_equipment_id if grouped_equipment_id is not None else getattr(latest_row, 'equipment_id', None)
        equipment = equipment_by_id.get(int(equipment_id)) if equipment_id is not None else None
        workshop_id = getattr(latest_row, 'workshop_id', None)
        shift_id = getattr(latest_row, 'shift_config_id', None)
        is_unbound = equipment_id is None
        line_code = group_key if is_unbound else str(getattr(equipment, 'code', None) or f'equipment:{equipment_id}')
        shift_label = f'{shift_id}班' if shift_id is not None else '未知班次'
        line_name = f'未绑定机列 / {shift_label}' if is_unbound else getattr(equipment, 'name', None)
        items.append(
            {
                'line_code': line_code,
                'line_name': line_name,
                'workshop_name': workshop_names.get(int(workshop_id), f'车间{workshop_id}') if workshop_id is not None else None,
                'active_coil_count': len(rows),
                'active_tons': round(sum(_local_weight_tons(row, 'output_weight') for row in rows), 4),
                'finished_tons': round(sum(_local_weight_tons(row, 'output_weight') for row in rows), 4),
                'stalled_count': sum(1 for row in rows if _local_issue_count(row) > 0),
                'machine_binding_status': 'unbound' if is_unbound else 'bound',
                'cost_estimate': _estimate(),
                'margin_estimate': _estimate(label='毛差估算'),
                'freshness': _local_freshness(freshness),
            }
        )
    return sorted(items, key=lambda item: item['line_code'])


def list_machine_lines(
    db: Session,
    *,
    scope: ScopeSummary | None = None,
    now=None,
    current_user: Any | None = None,
) -> list[dict[str, Any]]:
    freshness = build_freshness(db, now=now)
    live_payload = _live_aggregation_for_factory_command(db, current_user=current_user, now=now)
    if live_payload is not None:
        return _machine_lines_from_live_aggregation(db, live_payload, freshness=freshness)
    target_date = _latest_local_business_date(db, fallback=_business_date(now), scope=scope)
    if _should_use_local_shift_data(db, freshness):
        return _list_machine_lines_from_shift_data(
            db,
            freshness=freshness,
            target_date=target_date,
            scope=scope,
        )

    coils = _scoped_coils(db, scope=scope)
    line_rows = _scoped_machine_lines(db, scope=scope)
    line_map = {row.line_code: row for row in line_rows}
    coil_groups: dict[str, list[Any]] = defaultdict(list)
    line_aliases = _line_alias_map(line_rows)
    for coil in coils:
        line_code = _line_code_for_coil(coil, line_aliases)
        if line_code is None:
            line_code = _unmatched_line_code_for_coil(coil)
        coil_groups[line_code].append(coil)

    all_line_codes = set(line_map) | set(coil_groups)
    items = []
    for line_code in sorted(all_line_codes):
        line = line_map.get(line_code)
        rows = coil_groups.get(line_code, [])
        active_rows = [row for row in rows if _destination(row)['kind'] == 'in_progress']
        finished_rows = [row for row in rows if _destination(row)['kind'] != 'in_progress']
        is_unmatched = str(line_code).startswith('未匹配机列:')
        items.append(
            {
                'line_code': line_code,
                'line_name': '未匹配机列' if is_unmatched else getattr(line, 'line_name', None),
                'workshop_name': _canonical_workshop_name_or_none(
                    getattr(line, 'workshop_name', None) or (getattr(rows[0], 'current_workshop', None) if rows else None)
                ),
                'active_coil_count': len(active_rows),
                'active_tons': round(sum(_weight(row) for row in active_rows), 4),
                'finished_tons': round(sum(_weight(row) for row in finished_rows), 4),
                'stalled_count': sum(1 for row in active_rows if _is_stalled(row)),
                'machine_binding_status': 'unmatched' if is_unmatched else 'bound',
                'cost_estimate': _estimate(),
                'margin_estimate': _estimate(label='毛差估算'),
                'freshness': freshness,
            }
        )
    local_items = _list_machine_lines_from_shift_data(
        db,
        freshness=freshness,
        target_date=target_date,
        scope=scope,
    )
    by_code = {str(item['line_code']): item for item in items}
    for local_item in local_items:
        existing = by_code.get(str(local_item['line_code']))
        if existing is None:
            items.append(local_item)
            by_code[str(local_item['line_code'])] = local_item
            continue
        existing['active_coil_count'] += local_item['active_coil_count']
        existing['active_tons'] = round(existing['active_tons'] + local_item['active_tons'], 4)
        existing['finished_tons'] = round(existing['finished_tons'] + local_item['finished_tons'], 4)
        existing['stalled_count'] += local_item['stalled_count']
        existing['freshness'] = _mixed_freshness(freshness)
    return sorted(items, key=lambda item: item['line_code'])


def list_coils(
    db: Session,
    *,
    scope: ScopeSummary | None = None,
    limit: int | None = DEFAULT_COIL_LIST_LIMIT,
    offset: int | None = 0,
    workshop: str | None = None,
    destination: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    freshness = build_freshness(db)
    if _should_use_local_shift_data(db, freshness):
        return []

    normalized_limit = _bounded_limit(limit)
    normalized_offset = _bounded_offset(offset)
    rows = _paged_coils(
        db,
        scope=scope,
        limit=normalized_limit,
        offset=normalized_offset,
        workshop=workshop,
        destination=destination,
        query=query,
    )
    events = _latest_events_by_coil(db, {row.coil_id for row in rows})
    line_aliases = _line_alias_map(_scoped_machine_lines(db, scope=scope))
    latest_process_by_batch = _latest_process_records_by_batch(
        db,
        {str(getattr(row, 'batch_no', '') or '').strip() for row in rows},
    )
    return [
        {
            **_coil_trace_payload(row, line_code=_line_code_for_coil(row, line_aliases)),
            **_process_weight_payload(latest_process_by_batch.get(str(getattr(row, 'batch_no', '') or '').strip())),
            'previous_workshop': _canonical_workshop_name_or_none(getattr(events.get(row.coil_id), 'previous_workshop', None)),
            'previous_process': getattr(events.get(row.coil_id), 'previous_process', None),
            'destination': _destination(row),
        }
        for row in rows
    ]


def get_coil_flow(db: Session, *, coil_key: str, scope: ScopeSummary | None = None) -> dict[str, Any]:
    rows = [row for row in _scoped_coils(db, scope=scope) if row.coil_id == coil_key]
    row = rows[0] if rows else None
    if row is None:
        return {
            'coil_key': coil_key,
            'tracking_card_no': None,
            'previous_workshop': None,
            'previous_process': None,
            'current_workshop': None,
            'current_process': None,
            'next_workshop': None,
            'next_process': None,
            'destination': {'kind': 'unknown', 'label': '未知'},
            'freshness': build_freshness(db),
        }
    events = sorted([event for event in _all(db, CoilFlowEvent) if event.coil_key == coil_key], key=_event_sort_key)
    event = events[-1] if events else None
    batch_no = str(getattr(row, 'batch_no', '') or '').strip()
    latest_process_by_batch = _latest_process_records_by_batch(db, {batch_no})
    process_records = _process_records_for_batch(db, batch_no)
    lifecycle_events, lifecycle_coverage = _lifecycle_events(db, row, process_records=process_records)
    line_aliases = _line_alias_map(_scoped_machine_lines(db, scope=scope))
    return {
        **_coil_trace_payload(row, line_code=_line_code_for_coil(row, line_aliases)),
        **_process_weight_payload(latest_process_by_batch.get(batch_no)),
        'previous_workshop': _canonical_workshop_name_or_none(getattr(event, 'previous_workshop', None)),
        'previous_process': getattr(event, 'previous_process', None),
        'current_workshop': _canonical_workshop_name_or_none(
            getattr(row, 'current_workshop', None) if row else getattr(event, 'current_workshop', None),
        ),
        'current_process': getattr(row, 'current_process', None) if row else getattr(event, 'current_process', None),
        'next_workshop': _canonical_workshop_name_or_none(
            getattr(row, 'next_workshop', None) if row else getattr(event, 'next_workshop', None),
        ),
        'next_process': getattr(row, 'next_process', None) if row else getattr(event, 'next_process', None),
        'destination': _destination(row) if row else {'kind': 'unknown', 'label': '未知'},
        'lifecycle_events': lifecycle_events,
        'lifecycle_coverage': lifecycle_coverage,
        'freshness': build_freshness(db),
    }


def build_cost_benefit(db: Session, *, scope: ScopeSummary | None = None) -> dict[str, Any]:
    _ = scope
    freshness = build_freshness(db)
    estimate = _estimate()
    return {
        'freshness': freshness,
        'label': estimate['label'],
        'estimated_cost': estimate['estimated_cost'],
        'estimated_gross_margin': estimate['estimated_gross_margin'],
        'missing_data': estimate['missing_data'],
    }


def list_destinations(db: Session, *, scope: ScopeSummary | None = None) -> list[dict[str, Any]]:
    freshness = build_freshness(db)
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in _scoped_coils(db, scope=scope):
        grouped[_destination(row)['kind']].append(row)
    labels = {
        'in_progress': '在制',
        'finished_stock': '成品库存',
        'allocation': '已分配',
        'delivery': '交付',
        'unknown': '未知',
    }
    return [
        {
            'kind': kind,
            'label': labels.get(kind, kind),
            'coil_count': len(rows),
            'tons': round(sum(_weight(row) for row in rows), 4),
            'freshness': freshness,
        }
        for kind, rows in grouped.items()
    ]


def find_coil_flow_suggestion(
    db: Session,
    *,
    tracking_card_no: str,
    scope: ScopeSummary | None = None,
) -> dict[str, Any] | None:
    normalized = str(tracking_card_no or '').strip().upper()
    if not normalized:
        return None
    rows = [
        row
        for row in _scoped_coils(db, scope=scope)
        if normalized
        in {
            str(getattr(row, 'coil_id', '') or '').strip().upper(),
            str(getattr(row, 'tracking_card_no', '') or '').strip().upper(),
            str(getattr(row, 'batch_no', '') or '').strip().upper(),
        }
    ]
    if not rows:
        return None
    if len(rows) > 1:
        return {
            'tracking_card_no': tracking_card_no,
            'destination': {},
            'flow_source': 'manual_pending_match',
            'match_status': 'ambiguous',
            'candidate_count': len(rows),
        }
    return get_coil_flow(db, coil_key=rows[0].coil_id, scope=scope)
