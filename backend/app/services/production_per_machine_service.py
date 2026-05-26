"""Per-machine ``ShiftProductionData`` upsert (G13).

Splits the legacy report-level (workshop-bucket) production write into one
row per machine, keyed on
``(business_date, shift_config_id, workshop_id, equipment_id)`` so the
ShiftReportForm can ship machine-granular entries that align with the
真值底 #6 #7 铸二/铸三能耗表 column shape (机列×班次粒度).
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, TypedDict

from sqlalchemy.orm import Session

from app.models.production import ShiftProductionData


class PerMachineRow(TypedDict, total=False):
    equipment_id: int
    input_weight: float | None
    output_weight: float | None
    qualified_weight: float | None
    scrap_weight: float | None
    electricity_kwh: float | None
    actual_headcount: int | None
    notes: str | None


def upsert_per_machine_rows(
    db: Session,
    *,
    business_date: date,
    shift_config_id: int,
    workshop_id: int,
    team_id: int | None,
    rows: Iterable[PerMachineRow],
) -> list[ShiftProductionData]:
    saved: list[ShiftProductionData] = []
    for raw in rows:
        eq_id = raw['equipment_id']
        existing = (
            db.query(ShiftProductionData)
            .filter(
                ShiftProductionData.business_date == business_date,
                ShiftProductionData.shift_config_id == shift_config_id,
                ShiftProductionData.workshop_id == workshop_id,
                ShiftProductionData.equipment_id == eq_id,
                ShiftProductionData.data_status != 'voided',
            )
            .one_or_none()
        )
        if existing is None:
            existing = ShiftProductionData(
                business_date=business_date,
                shift_config_id=shift_config_id,
                workshop_id=workshop_id,
                team_id=team_id,
                equipment_id=eq_id,
                data_source='mobile',
                data_status='pending',
            )
            db.add(existing)
        existing.team_id = team_id
        existing.input_weight = raw.get('input_weight')
        existing.output_weight = raw.get('output_weight')
        existing.qualified_weight = raw.get('qualified_weight')
        existing.scrap_weight = raw.get('scrap_weight')
        existing.electricity_kwh = raw.get('electricity_kwh')
        if 'actual_headcount' in raw:
            existing.actual_headcount = raw.get('actual_headcount')
        if 'notes' in raw:
            existing.notes = raw.get('notes')
        existing.data_source = 'mobile'
        existing.data_status = 'pending'
        db.flush()
        saved.append(existing)
    return saved
