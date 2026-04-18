from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.mes import MesCoilSnapshot
from app.models.production import WorkOrder, WorkOrderEntry


ACTIVE_STATUSES = {'created', 'in_progress', 'queued', 'waiting', 'processing', 'submitted'}
COMPLETED_STATUSES = {'completed', 'done', 'closed', 'shipped'}


def _to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _normalize_status(value: str | None) -> str:
    return str(value or '').strip().lower()


def _is_active_status(value: str | None) -> bool:
    normalized = _normalize_status(value)
    if normalized in COMPLETED_STATUSES:
        return False
    if normalized in ACTIVE_STATUSES:
        return True
    return normalized != ''


def _is_stalled(*, updated_at: datetime | None, target_date: date) -> bool:
    if updated_at is None:
        return False
    return updated_at.date() < target_date


def build_contract_progress_projection(db: Session, *, target_date: date) -> dict[str, Any]:
    snapshots = db.query(MesCoilSnapshot).all()
    work_orders = db.query(WorkOrder).all()
    entries = db.query(WorkOrderEntry).all()

    work_order_by_card = {
        str(item.tracking_card_no or '').strip().upper(): item
        for item in work_orders
        if getattr(item, 'tracking_card_no', None)
    }
    latest_entry_by_work_order: dict[int, WorkOrderEntry] = {}
    for entry in entries:
        current = latest_entry_by_work_order.get(entry.work_order_id)
        if current is None:
            latest_entry_by_work_order[entry.work_order_id] = entry
            continue
        current_dt = current.approved_at or current.verified_at or current.submitted_at or current.updated_at or current.created_at
        incoming_dt = entry.approved_at or entry.verified_at or entry.submitted_at or entry.updated_at or entry.created_at
        if incoming_dt and current_dt and incoming_dt >= current_dt:
            latest_entry_by_work_order[entry.work_order_id] = entry

    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            'contract_no': '',
            'active_coil_count': 0,
            'stalled_coil_count': 0,
            'today_advanced_coil_count': 0,
            'today_advanced_weight': 0.0,
            'remaining_weight': 0.0,
            'workshops': set(),
            'processes': set(),
            'statuses': set(),
            'tracking_cards': [],
        }
    )

    active_contract_count = 0
    stalled_contract_count = 0
    total_active_coils = 0
    total_stalled_coils = 0
    total_today_advanced_weight = 0.0
    total_remaining_weight = 0.0

    for snapshot in snapshots:
        contract_no = str(snapshot.contract_no or '').strip()
        if not contract_no:
            continue

        tracking_card_no = str(snapshot.tracking_card_no or '').strip().upper()
        work_order = work_order_by_card.get(tracking_card_no)
        latest_entry = latest_entry_by_work_order.get(work_order.id) if work_order else None
        current_status = _normalize_status(snapshot.status or getattr(work_order, 'overall_status', None))
        active = _is_active_status(current_status)
        updated_at = snapshot.updated_from_mes_at or snapshot.event_time or snapshot.updated_at
        stalled = active and _is_stalled(updated_at=updated_at, target_date=target_date)
        advanced_today = bool(updated_at and updated_at.date() == target_date)

        weight = 0.0
        if latest_entry is not None:
            weight = _to_float(latest_entry.verified_output_weight) or _to_float(latest_entry.output_weight)
        if weight == 0.0:
            weight = _to_float(getattr(work_order, 'contract_weight', None))

        item = grouped[contract_no]
        item['contract_no'] = contract_no
        item['statuses'].add(current_status or 'unknown')
        if snapshot.workshop_code:
            item['workshops'].add(snapshot.workshop_code)
        if snapshot.process_code:
            item['processes'].add(snapshot.process_code)
        item['tracking_cards'].append(
            {
                'tracking_card_no': tracking_card_no,
                'coil_id': snapshot.coil_id,
                'status': current_status or 'unknown',
                'workshop_code': snapshot.workshop_code,
                'process_code': snapshot.process_code,
                'updated_at': updated_at.isoformat() if updated_at else None,
            }
        )

        if active:
            item['active_coil_count'] += 1
            item['remaining_weight'] += _to_float(getattr(work_order, 'contract_weight', None))
            total_active_coils += 1
        if stalled:
            item['stalled_coil_count'] += 1
            total_stalled_coils += 1
        if advanced_today:
            item['today_advanced_coil_count'] += 1
            item['today_advanced_weight'] += weight
            total_today_advanced_weight += weight
        total_remaining_weight += _to_float(getattr(work_order, 'contract_weight', None)) if active else 0.0

    contracts: list[dict[str, Any]] = []
    for contract_no, item in grouped.items():
        status = 'stalled' if item['stalled_coil_count'] > 0 else ('active' if item['active_coil_count'] > 0 else 'completed')
        if item['active_coil_count'] > 0:
            active_contract_count += 1
        if item['stalled_coil_count'] > 0:
            stalled_contract_count += 1
        contracts.append(
            {
                'contract_no': contract_no,
                'status': status,
                'active_coil_count': item['active_coil_count'],
                'stalled_coil_count': item['stalled_coil_count'],
                'today_advanced_coil_count': item['today_advanced_coil_count'],
                'today_advanced_weight': round(item['today_advanced_weight'], 2),
                'remaining_weight': round(item['remaining_weight'], 2),
                'workshops': sorted(item['workshops']),
                'processes': sorted(item['processes']),
                'statuses': sorted(item['statuses']),
                'tracking_cards': sorted(item['tracking_cards'], key=lambda row: (row['updated_at'] or '', row['tracking_card_no']), reverse=True),
            }
        )

    contracts.sort(key=lambda row: (row['status'] != 'stalled', row['contract_no']))
    return {
        'target_date': target_date.isoformat(),
        'active_contract_count': active_contract_count,
        'stalled_contract_count': stalled_contract_count,
        'active_coil_count': total_active_coils,
        'stalled_coil_count': total_stalled_coils,
        'today_advanced_weight': round(total_today_advanced_weight, 2),
        'remaining_weight': round(total_remaining_weight, 2),
        'contracts': contracts,
    }
