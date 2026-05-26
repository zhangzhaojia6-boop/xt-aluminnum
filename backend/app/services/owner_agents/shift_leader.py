"""§3.2 班长 (shift_leader) owner-agent.

Writes:
- ``daily_consumable_logs.payload`` — validated through ``ConsumablePayload`` (G2 lock)
- ``mobile_shift_reports.attendance_payload`` — jsonb (G3) keeping
  ``attendance_count`` in sync as the legacy scalar
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.consumable import DailyConsumableLog
from app.models.production import MobileShiftReport
from app.schemas.consumable_payload import validate_consumable_payload


def upsert_consumable_log(
    db: Session,
    *,
    workshop_id: int,
    business_date: date,
    payload: dict[str, Any],
    workshop_type: str | None = None,
    note: str | None = None,
    created_by_user_id: int | None = None,
    updated_by_user_id: int | None = None,
) -> DailyConsumableLog:
    cleaned = validate_consumable_payload(payload)

    row = (
        db.query(DailyConsumableLog)
        .filter(
            DailyConsumableLog.workshop_id == workshop_id,
            DailyConsumableLog.business_date == business_date,
        )
        .one_or_none()
    )
    if row is None:
        row = DailyConsumableLog(
            workshop_id=workshop_id,
            business_date=business_date,
            created_by_user_id=created_by_user_id,
        )
        db.add(row)
    row.workshop_type = workshop_type
    row.payload = cleaned
    row.note = note
    if updated_by_user_id is not None:
        row.updated_by_user_id = updated_by_user_id
    db.flush()
    return row


def write_attendance(
    db: Session,
    *,
    shift_report_id: int,
    attendance_payload: dict[str, Any],
    attendance_count: int | None = None,
) -> MobileShiftReport:
    row = db.query(MobileShiftReport).filter(MobileShiftReport.id == shift_report_id).one()
    row.attendance_payload = attendance_payload
    if attendance_count is not None:
        row.attendance_count = attendance_count
    db.flush()
    return row
