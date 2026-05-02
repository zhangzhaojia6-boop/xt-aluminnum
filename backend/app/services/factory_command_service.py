from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.mes import CoilFlowEvent, MesCoilSnapshot, MesMachineLineSnapshot
from app.services.mes_sync_service import latest_sync_status


def _all(db: Session, model: type) -> list[Any]:
    return list(db.query(model).all())


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_stalled(row: Any) -> bool:
    return _number(getattr(row, 'delay_hours', None)) > 0 or not getattr(row, 'current_process', None)


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
    if lag_seconds is None:
        freshness_status = 'offline_or_blocked'
    elif lag_seconds > 900:
        freshness_status = 'offline_or_blocked'
    elif lag_seconds > 300:
        freshness_status = 'stale'
    else:
        freshness_status = 'fresh'
    return {
        'status': freshness_status,
        'lag_seconds': lag_seconds,
        'last_synced_at': status.get('last_synced_at'),
        'last_event_at': status.get('last_event_at'),
        'source': 'mes_projection',
    }


def build_overview(db: Session, *, now=None) -> dict[str, Any]:
    rows = _all(db, MesCoilSnapshot)
    freshness = build_freshness(db, now=now)
    stock_rows = [row for row in rows if _destination(row)['kind'] == 'finished_stock']
    wip_rows = [row for row in rows if _destination(row)['kind'] == 'in_progress']
    abnormal_count = sum(1 for row in rows if _number(getattr(row, 'delay_hours', None)) > 0)
    abnormal_count += sum(1 for row in rows if not getattr(row, 'current_process', None))
    missing_data = ['cost_inputs']
    return {
        'freshness': freshness,
        'wip_tons': round(sum(_weight(row) for row in wip_rows), 4),
        'today_output_tons': round(sum(_weight(row) for row in stock_rows), 4),
        'stock_tons': round(sum(_weight(row) for row in stock_rows), 4),
        'abnormal_count': abnormal_count,
        'cost_estimate': _estimate(missing_data=missing_data),
        'missing_data': missing_data,
    }


def list_workshops(db: Session) -> list[dict[str, Any]]:
    freshness = build_freshness(db)
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in _all(db, MesCoilSnapshot):
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


def list_machine_lines(db: Session) -> list[dict[str, Any]]:
    freshness = build_freshness(db)
    coils = _all(db, MesCoilSnapshot)
    line_rows = _all(db, MesMachineLineSnapshot)
    line_map = {row.line_code: row for row in line_rows}
    coil_groups: dict[str, list[Any]] = defaultdict(list)
    for coil in coils:
        line_code = getattr(coil, 'machine_code', None) or 'unknown'
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


def list_coils(db: Session) -> list[dict[str, Any]]:
    return [
        {
            'coil_key': row.coil_id,
            'tracking_card_no': row.tracking_card_no,
            'batch_no': getattr(row, 'batch_no', None),
            'material_code': getattr(row, 'material_code', None),
            'current_workshop': getattr(row, 'current_workshop', None),
            'current_process': getattr(row, 'current_process', None),
            'next_workshop': getattr(row, 'next_workshop', None),
            'next_process': getattr(row, 'next_process', None),
            'destination': _destination(row),
        }
        for row in _all(db, MesCoilSnapshot)
    ]


def get_coil_flow(db: Session, *, coil_key: str) -> dict[str, Any]:
    rows = [row for row in _all(db, MesCoilSnapshot) if row.coil_id == coil_key]
    row = rows[0] if rows else None
    events = [event for event in _all(db, CoilFlowEvent) if event.coil_key == coil_key]
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


def build_cost_benefit(db: Session) -> dict[str, Any]:
    freshness = build_freshness(db)
    estimate = _estimate()
    return {
        'freshness': freshness,
        'label': estimate['label'],
        'estimated_cost': estimate['estimated_cost'],
        'estimated_gross_margin': estimate['estimated_gross_margin'],
        'missing_data': estimate['missing_data'],
    }


def list_destinations(db: Session) -> list[dict[str, Any]]:
    freshness = build_freshness(db)
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in _all(db, MesCoilSnapshot):
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
