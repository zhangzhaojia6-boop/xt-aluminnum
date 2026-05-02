from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import json_object_type


class MesImportRecord(Base):
    __tablename__ = 'mes_import_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    import_batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('import_batches.id'), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default='mes_export', index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    shift_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metric_value: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_row_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MesCoilSnapshot(Base):
    __tablename__ = 'mes_coil_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coil_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    tracking_card_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    qr_code: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    batch_no: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    contract_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    mes_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    material_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    customer_alias: Mapped[str | None] = mapped_column(String(128), nullable=True)
    alloy_grade: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    material_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spec_thickness: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    spec_width: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    spec_length: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spec_display: Mapped[str | None] = mapped_column(String(128), nullable=True)
    feeding_weight: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    material_weight: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    gross_weight: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    net_weight: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    workshop_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    process_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    machine_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    shift_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    current_workshop: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    current_process: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    current_process_sort: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_workshop: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    next_process: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    next_process_sort: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_route_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    print_process_route_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    card_status_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    production_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delay_hours: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    in_stock_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allocation_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    updated_from_mes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_seen_from_mes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MesMachineLineSnapshot(Base):
    __tablename__ = 'mes_machine_line_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    line_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    line_name: Mapped[str] = mapped_column(String(128), nullable=False)
    workshop_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    slot_no: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    last_seen_from_mes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    source_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CoilFlowEvent(Base):
    __tablename__ = 'coil_flow_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coil_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tracking_card_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_workshop: Mapped[str | None] = mapped_column(String(128), nullable=True)
    previous_process: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_workshop: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    current_process: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    next_workshop: Mapped[str | None] = mapped_column(String(128), nullable=True)
    next_process: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    source_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MesSyncCursor(Base):
    __tablename__ = 'mes_sync_cursors'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cursor_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    cursor_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MesSyncRunLog(Base):
    __tablename__ = 'mes_sync_run_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cursor_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='running', index=True)
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    replayed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    lag_seconds: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
