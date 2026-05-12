from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.production import WorkOrder, WorkOrderEntry
from app.services import scan_lookup_service


ELIGIBLE_ENTRY_STATUSES = ('submitted', 'verified', 'approved')


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _flow_context_for_tracking_card(db: Session, tracking_card_no: str) -> dict[str, Any]:
    try:
        return scan_lookup_service.flow_context_for_identifier(db, identifier=tracking_card_no)
    except scan_lookup_service.ScanLookupUnavailable:
        return {}


def enrich_mobile_coil_flow_context(
    db: Session,
    *,
    business_date: date,
    apply: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    max_candidates = int(limit) if limit is not None else None
    if max_candidates is not None and max_candidates <= 0:
        max_candidates = None

    rows = (
        db.query(WorkOrderEntry, WorkOrder.tracking_card_no)
        .join(WorkOrder, WorkOrder.id == WorkOrderEntry.work_order_id)
        .filter(
            WorkOrderEntry.business_date == business_date,
            WorkOrderEntry.entry_type == 'mobile_coil',
            WorkOrderEntry.entry_status.in_(ELIGIBLE_ENTRY_STATUSES),
        )
        .order_by(WorkOrderEntry.created_at.asc(), WorkOrderEntry.id.asc())
        .all()
    )

    scanned_count = 0
    candidate_count = 0
    updated_count = 0
    skipped_existing_flow_count = 0
    samples: list[dict[str, Any]] = []

    for entry, tracking_card_no in rows:
        scanned_count += 1
        extra_payload = dict(entry.extra_payload or {})
        if extra_payload.get('flow'):
            skipped_existing_flow_count += 1
            continue

        context = _flow_context_for_tracking_card(db, str(tracking_card_no or ''))
        if not context:
            continue

        candidate_count += 1
        merged_payload = {**extra_payload, **context}
        sample = {
            'entry_id': entry.id,
            'tracking_card_no': tracking_card_no,
            'flow': context.get('flow'),
            'mes_reference': context.get('mes_reference'),
        }
        if len(samples) < 20:
            samples.append(_json_safe(sample))

        if apply:
            entry.extra_payload = merged_payload
            updated_count += 1

        if max_candidates is not None and candidate_count >= max_candidates:
            break

    if apply and updated_count:
        db.commit()

    return {
        'business_date': business_date.isoformat(),
        'apply': apply,
        'scanned_count': scanned_count,
        'candidate_count': candidate_count,
        'updated_count': updated_count,
        'skipped_existing_flow_count': skipped_existing_flow_count,
        'samples': samples,
    }
