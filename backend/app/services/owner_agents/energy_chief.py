"""§3.1 总电工 (energy_chief) owner-agent.

Writes:
- ``machine_energy_records`` (per-shift, per-machine) — one row per
  ``(shift_report_id, machine_id)``
- ``machine_energy_daily_compare`` (G1) — one row per ``(business_date, machine_id)``
  with ``gas_per_ton_today/yesterday/target`` and the arrow
- ``data_reconciliation_items`` — meter cumulative vs sum-of-shifts diff
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.energy import MachineEnergyDailyCompare, MachineEnergyRecord
from app.models.reconciliation import DataReconciliationItem


def upsert_shift_record(
    db: Session,
    *,
    shift_report_id: int,
    machine_id: int | None,
    machine_code: str | None = None,
    machine_name: str | None = None,
    energy_kwh: float | None = None,
    gas_m3: float | None = None,
) -> MachineEnergyRecord:
    q = db.query(MachineEnergyRecord).filter(
        MachineEnergyRecord.shift_report_id == shift_report_id
    )
    if machine_id is not None:
        q = q.filter(MachineEnergyRecord.machine_id == machine_id)
    else:
        q = q.filter(MachineEnergyRecord.machine_id.is_(None))
        if machine_code is not None:
            q = q.filter(MachineEnergyRecord.machine_code == machine_code)
    row = q.one_or_none()
    if row is None:
        row = MachineEnergyRecord(
            shift_report_id=shift_report_id,
            machine_id=machine_id,
        )
        db.add(row)
    row.machine_code = machine_code
    row.machine_name = machine_name
    row.energy_kwh = energy_kwh
    row.gas_m3 = gas_m3
    db.flush()
    return row


def upsert_daily_compare(
    db: Session,
    *,
    business_date: date,
    machine_id: int,
    workshop_id: int | None = None,
    gas_per_ton_today: float | None = None,
    gas_per_ton_yesterday: float | None = None,
    gas_per_ton_target: float | None = None,
    compare_arrow: str | None = None,
) -> MachineEnergyDailyCompare:
    row = (
        db.query(MachineEnergyDailyCompare)
        .filter(
            MachineEnergyDailyCompare.business_date == business_date,
            MachineEnergyDailyCompare.machine_id == machine_id,
        )
        .one_or_none()
    )
    if row is None:
        row = MachineEnergyDailyCompare(
            business_date=business_date,
            machine_id=machine_id,
        )
        db.add(row)
    row.workshop_id = workshop_id
    row.gas_per_ton_today = gas_per_ton_today
    row.gas_per_ton_yesterday = gas_per_ton_yesterday
    row.gas_per_ton_target = gas_per_ton_target
    row.compare_arrow = compare_arrow
    db.flush()
    return row


def record_meter_vs_shifts_reconciliation(
    db: Session,
    *,
    business_date: date,
    dimension_key: str,
    field_name: str,
    meter_cumulative: float | None,
    sum_of_shifts: float | None,
    tolerance: float = 0.01,
) -> DataReconciliationItem:
    a = float(meter_cumulative) if meter_cumulative is not None else 0.0
    b = float(sum_of_shifts) if sum_of_shifts is not None else 0.0
    diff = a - b
    status = 'ok' if abs(diff) <= tolerance else 'open'

    item = DataReconciliationItem(
        business_date=business_date,
        reconciliation_type='energy_meter_vs_shifts',
        source_a='meter_cumulative',
        source_b='sum_of_shifts',
        dimension_key=dimension_key,
        field_name=field_name,
        source_a_value=str(meter_cumulative) if meter_cumulative is not None else None,
        source_b_value=str(sum_of_shifts) if sum_of_shifts is not None else None,
        diff_value=diff,
        status=status,
    )
    db.add(item)
    db.flush()
    return item
