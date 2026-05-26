"""§3.5 storage (成品库) owner-agent — writes the four storage scalars.

`mobile_shift_reports` is per-(business_date, shift_config, workshop, team).
Storage is a company-level concept; we route to the row identified by an
existing ``shift_report_id`` (resolved by the caller via the storage owner's
扫码上下文 — single virtual_role_qr machine). Keeps the agent narrow: only
the 4 scalars from §3.5.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.production import MobileShiftReport


def write_storage_four(
    db: Session,
    *,
    shift_report_id: int,
    storage_prepared: float | None,
    storage_finished: float | None,
    shipment_weight: float | None,
    contract_received: float | None,
) -> MobileShiftReport:
    row = db.query(MobileShiftReport).filter(MobileShiftReport.id == shift_report_id).one()
    row.storage_prepared = storage_prepared
    row.storage_finished = storage_finished
    row.shipment_weight = shipment_weight
    row.contract_received = contract_received
    db.flush()
    return row
