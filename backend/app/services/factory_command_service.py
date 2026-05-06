from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

from sqlalchemy import and_, false, or_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.scope import ScopeSummary
from app.models.master import Equipment, Workshop
from app.models.mes import CoilFlowEvent, MesCoilSnapshot, MesMachineLineSnapshot
from app.models.production import MobileShiftReport, ShiftProductionData
from app.services.mes_sync_service import latest_sync_status

DEFAULT_COIL_LIST_LIMIT = 100
MAX_COIL_LIST_LIMIT = 500
LOCAL_SHIFT_STATUSES = {'confirmed', 'submitted'}
LOCAL_PENDING_SHIFT_SOURCES = {'mobile_coil_agg'}
LOCAL_MOBILE_REPORT_STATUSES = {'submitted', 'approved', 'auto_confirmed'}
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


def _scope_workshop_tokens(db: Session, scope: ScopeSummary | None) -> set[str] | None:
    if scope is None or scope.is_admin or scope.data_scope_type == 'all':
        return None
    if scope.workshop_id is None:
        return set()
    workshop = _query_first(db.query(Workshop).filter(Workshop.id == scope.workshop_id))
    tokens = {str(scope.workshop_id)}
    if workshop is not None:
        tokens.update(
            token
            for token in (
                getattr(workshop, 'name', None),
                getattr(workshop, 'code', None),
            )
            if token
        )
    return {str(token).strip() for token in tokens if str(token).strip()}


def _matches_workshop(value: Any, tokens: set[str] | None) -> bool:
    if tokens is None:
        return True
    if not tokens:
        return False
    return str(value or '').strip() in tokens


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
        'material_code',
        'machine_code',
        'current_workshop',
        'current_process',
        'next_process',
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


def _workshop_name_map(db: Session) -> dict[int, str]:
    return {
        int(row.id): str(row.name)
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
    return or_(MesCoilSnapshot.current_workshop == text, MesCoilSnapshot.workshop_code == text)


def _filter_text_expression(query: str | None):
    text = str(query or '').strip()
    if not text:
        return None
    pattern = f'%{text}%'
    return or_(
        MesCoilSnapshot.coil_id.ilike(pattern),
        MesCoilSnapshot.tracking_card_no.ilike(pattern),
        MesCoilSnapshot.batch_no.ilike(pattern),
        MesCoilSnapshot.material_code.ilike(pattern),
        MesCoilSnapshot.machine_code.ilike(pattern),
        MesCoilSnapshot.current_workshop.ilike(pattern),
        MesCoilSnapshot.current_process.ilike(pattern),
        MesCoilSnapshot.next_process.ilike(pattern),
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
    return [
        row
        for row in rows
        if (not workshop_text or str(getattr(row, 'current_workshop', '') or '').strip() == workshop_text or str(getattr(row, 'workshop_code', '') or '').strip() == workshop_text)
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


def _line_code_for_coil(row: Any, line_aliases: Mapping[str, str]) -> str:
    machine_code = str(getattr(row, 'machine_code', None) or '').strip()
    if not machine_code:
        return 'unknown'
    for alias in _coil_machine_aliases(row):
        line_code = line_aliases.get(_alias_key(alias))
        if line_code:
            return line_code
    slot_no = _slot_no(machine_code)
    workshop = str(getattr(row, 'current_workshop', None) or '').strip()
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
        return current.date()
    if isinstance(current, date):
        return current
    return datetime.now(timezone.utc).date()


def _same_business_date(value: Any, target: date) -> bool:
    if isinstance(value, datetime):
        return value.date() == target
    if isinstance(value, date):
        return value == target
    return False


def _estimate(*, missing_data: list[str] | None = None, label: str = '经营估算') -> dict[str, Any]:
    return {
        'label': label,
        'estimated_cost': None,
        'estimated_gross_margin': None,
        'missing_data': missing_data or ['cost_inputs'],
    }


def build_freshness(db: Session, *, now=None) -> dict[str, Any]:
    status = latest_sync_status(db, now=now)
    lag_seconds = status.get('lag_seconds')
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
    return {
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


def build_overview(db: Session, *, now=None, scope: ScopeSummary | None = None) -> dict[str, Any]:
    freshness = build_freshness(db, now=now)
    if _should_use_local_shift_data(db, freshness):
        return _build_overview_from_shift_data(
            db,
            freshness=freshness,
            target_date=_business_date(now),
            scope=scope,
        )

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
        target_date=current_date,
        scope=scope,
    )
    has_local_rows = _has_local_overview_rows(local_overview)
    local_output_tons = local_overview['total_output_tons'] if has_local_rows else 0.0
    response_freshness = _mixed_freshness(freshness) if has_local_rows else freshness
    return {
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


def list_workshops(db: Session, *, scope: ScopeSummary | None = None, now=None) -> list[dict[str, Any]]:
    freshness = build_freshness(db, now=now)
    if _should_use_local_shift_data(db, freshness):
        return _list_workshops_from_shift_data(
            db,
            freshness=freshness,
            target_date=_business_date(now),
            scope=scope,
        )

    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in _scoped_coils(db, scope=scope):
        grouped[getattr(row, 'current_workshop', None) or '未识别车间'].append(row)
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
        target_date=_business_date(now),
        scope=scope,
    )
    by_name = {str(item['workshop_name']): item for item in items}
    for local_item in local_items:
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
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in _local_shift_rows(db, target_date=target_date, scope=scope):
        equipment_id = getattr(row, 'equipment_id', None)
        if equipment_id is not None:
            grouped[f'equipment:{int(equipment_id)}'].append(row)
            continue
        workshop_id = getattr(row, 'workshop_id', None)
        shift_id = getattr(row, 'shift_config_id', None)
        workshop_key = workshop_id if workshop_id is not None else 'unknown'
        shift_key = shift_id if shift_id is not None else 'unknown'
        grouped[f'workshop:{workshop_key}:shift:{shift_key}:unbound'].append(row)
    equipment_by_id = _equipment_map(db)
    workshop_names = _workshop_name_map(db)
    items = []
    for group_key, rows in grouped.items():
        latest_row = max(rows, key=_row_sort_time)
        equipment_id = getattr(latest_row, 'equipment_id', None)
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


def list_machine_lines(db: Session, *, scope: ScopeSummary | None = None, now=None) -> list[dict[str, Any]]:
    freshness = build_freshness(db, now=now)
    if _should_use_local_shift_data(db, freshness):
        return _list_machine_lines_from_shift_data(
            db,
            freshness=freshness,
            target_date=_business_date(now),
            scope=scope,
        )

    coils = _scoped_coils(db, scope=scope)
    line_rows = _scoped_machine_lines(db, scope=scope)
    line_map = {row.line_code: row for row in line_rows}
    coil_groups: dict[str, list[Any]] = defaultdict(list)
    line_aliases = _line_alias_map(line_rows)
    for coil in coils:
        line_code = _line_code_for_coil(coil, line_aliases)
        coil_groups[line_code].append(coil)

    all_line_codes = set(line_map) | set(coil_groups)
    items = []
    for line_code in sorted(all_line_codes):
        line = line_map.get(line_code)
        rows = coil_groups.get(line_code, [])
        active_rows = [row for row in rows if _destination(row)['kind'] == 'in_progress']
        finished_rows = [row for row in rows if _destination(row)['kind'] != 'in_progress']
        items.append(
            {
                'line_code': line_code,
                'line_name': getattr(line, 'line_name', None),
                'workshop_name': getattr(line, 'workshop_name', None) or (getattr(rows[0], 'current_workshop', None) if rows else None),
                'active_coil_count': len(active_rows),
                'active_tons': round(sum(_weight(row) for row in active_rows), 4),
                'finished_tons': round(sum(_weight(row) for row in finished_rows), 4),
                'stalled_count': sum(1 for row in active_rows if _is_stalled(row)),
                'cost_estimate': _estimate(),
                'margin_estimate': _estimate(label='毛差估算'),
                'freshness': freshness,
            }
        )
    local_items = _list_machine_lines_from_shift_data(
        db,
        freshness=freshness,
        target_date=_business_date(now),
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
    return [
        {
            'coil_key': row.coil_id,
            'tracking_card_no': row.tracking_card_no,
            'batch_no': getattr(row, 'batch_no', None),
            'material_code': getattr(row, 'material_code', None),
            'line_code': _line_code_for_coil(row, line_aliases),
            'machine_code': getattr(row, 'machine_code', None),
            'previous_workshop': getattr(events.get(row.coil_id), 'previous_workshop', None),
            'previous_process': getattr(events.get(row.coil_id), 'previous_process', None),
            'current_workshop': getattr(row, 'current_workshop', None),
            'current_process': getattr(row, 'current_process', None),
            'next_workshop': getattr(row, 'next_workshop', None),
            'next_process': getattr(row, 'next_process', None),
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
    return {
        'coil_key': coil_key,
        'tracking_card_no': getattr(row, 'tracking_card_no', None),
        'previous_workshop': getattr(event, 'previous_workshop', None),
        'previous_process': getattr(event, 'previous_process', None),
        'current_workshop': getattr(row, 'current_workshop', None) if row else getattr(event, 'current_workshop', None),
        'current_process': getattr(row, 'current_process', None) if row else getattr(event, 'current_process', None),
        'next_workshop': getattr(row, 'next_workshop', None) if row else getattr(event, 'next_workshop', None),
        'next_process': getattr(row, 'next_process', None) if row else getattr(event, 'next_process', None),
        'destination': _destination(row) if row else {'kind': 'unknown', 'label': '未知'},
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
