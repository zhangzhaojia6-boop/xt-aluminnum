from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import json_object_type


class EnergyImportRecord(Base):
    __tablename__ = 'energy_import_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    import_batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('import_batches.id'), nullable=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    shift_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    energy_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    energy_value: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_row_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MachineEnergyRecord(Base):
    __tablename__ = 'machine_energy_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shift_report_id: Mapped[int] = mapped_column(Integer, ForeignKey('mobile_shift_reports.id'), nullable=False, index=True)
    machine_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=True, index=True)
    machine_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    machine_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    energy_kwh: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    gas_m3: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MachineEnergyDailyCompare(Base):
    __tablename__ = 'machine_energy_daily_compare'
    __table_args__ = (
        UniqueConstraint('business_date', 'machine_id', name='uq_machine_energy_compare_date_machine'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    machine_id: Mapped[int] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=False, index=True)
    workshop_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=True, index=True)
    gas_per_ton_today: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    gas_per_ton_yesterday: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    gas_per_ton_target: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    compare_arrow: Mapped[str | None] = mapped_column(String(8), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class IotEnergySyncRun(Base):
    __tablename__ = 'iot_energy_sync_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False, default='iot_meter', index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='pending', index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class IotEnergySnapshot(Base):
    __tablename__ = 'iot_energy_snapshots'
    __table_args__ = (
        UniqueConstraint('source_system', 'meter_code', 'reading_at', name='uq_iot_energy_snapshot_meter_time'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sync_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('iot_energy_sync_runs.id'), nullable=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=True, index=True)
    machine_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=True, index=True)
    meter_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    meter_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    electricity_kwh: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    gas_m3: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    water_m3: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    reading_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False, default='iot_meter', index=True)
    raw_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
