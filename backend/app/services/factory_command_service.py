from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.core.scope import ScopeSummary
from app.models.master import Workshop
from app.models.mes import CoilFlowEvent, MesCoilSnapshot, MesMachineLineSnapshot
from app.services.mes_sync_service import latest_sync_status

DEFAULT_COIL_LIST_LIMIT = 100
MAX_COIL_LIST_LIMIT = 500


def _all(db: Session, model: type) -> list[Any]:
    return list(db.query(model).all())


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
    latest: dict[str, Any] = {}
    for event in _all(db, CoilFlowEvent):
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


def build_overview(db: Session, *, now=None, scope: ScopeSummary | None = None) -> dict[str, Any]:
    rows = _scoped_coils(db, scope=scope)
    freshness = build_freshness(db, now=now)
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
    return {
        'freshness': freshness,
        'wip_tons': round(sum(_weight(row) for row in wip_rows), 4),
        'today_output_tons': round(sum(_weight(row) for row in today_output_rows), 4),
        'stock_tons': round(sum(_weight(row) for row in stock_rows), 4),
        'abnormal_count': abnormal_count,
        'cost_estimate': _estimate(missing_data=missing_data),
        'missing_data': missing_data,
    }


def list_workshops(db: Session, *, scope: ScopeSummary | None = None) -> list[dict[str, Any]]:
    freshness = build_freshness(db)
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
    return sorted(items, key=lambda item: item['active_tons'], reverse=True)


def list_machine_lines(db: Session, *, scope: ScopeSummary | None = None) -> list[dict[str, Any]]:
    freshness = build_freshness(db)
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
    return items


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
    normalized_limit = _bounded_limit(limit)
    normalized_offset = _bounded_offset(offset)
    rows = _filter_coils(
        _scoped_coils(db, scope=scope),
        workshop=workshop,
        destination=destination,
        query=query,
    )
    rows = rows[normalized_offset : normalized_offset + normalized_limit]
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
