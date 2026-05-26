"""§3.6 园区剪切 (shipment_outflow) owner-agent.

Append-style flow: each scan/entry is a new row. We support a
``replace_for_date`` for end-of-day re-submissions to keep the day
authoritative.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, TypedDict

from sqlalchemy.orm import Session

from app.models.production import ShipmentOutflowRecord


class OutflowRow(TypedDict, total=False):
    customer_name: str | None
    batch_no: str | None
    alloy_state: str | None
    finished_spec: str | None
    coil_weight: float | None
    net_weight: float | None
    source_workshop_code: str | None


def add_record(
    db: Session,
    *,
    business_date: date,
    customer_name: str | None = None,
    batch_no: str | None = None,
    alloy_state: str | None = None,
    finished_spec: str | None = None,
    coil_weight: float | None = None,
    net_weight: float | None = None,
    source_workshop_code: str | None = None,
) -> ShipmentOutflowRecord:
    item = ShipmentOutflowRecord(
        business_date=business_date,
        customer_name=customer_name,
        batch_no=batch_no,
        alloy_state=alloy_state,
        finished_spec=finished_spec,
        coil_weight=coil_weight,
        net_weight=net_weight,
        source_workshop_code=source_workshop_code,
    )
    db.add(item)
    db.flush()
    return item


def replace_for_date(
    db: Session,
    *,
    business_date: date,
    rows: Iterable[OutflowRow],
) -> list[ShipmentOutflowRecord]:
    db.query(ShipmentOutflowRecord).filter(
        ShipmentOutflowRecord.business_date == business_date
    ).delete(synchronize_session=False)

    created: list[ShipmentOutflowRecord] = []
    for raw in rows:
        item = ShipmentOutflowRecord(
            business_date=business_date,
            customer_name=raw.get('customer_name'),
            batch_no=raw.get('batch_no'),
            alloy_state=raw.get('alloy_state'),
            finished_spec=raw.get('finished_spec'),
            coil_weight=raw.get('coil_weight'),
            net_weight=raw.get('net_weight'),
            source_workshop_code=raw.get('source_workshop_code'),
        )
        db.add(item)
        created.append(item)
    db.flush()
    return created
