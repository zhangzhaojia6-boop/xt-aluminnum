from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, json_object_type


class DataReconciliationItem(Base):
    __tablename__ = 'data_reconciliation_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reconciliation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_a: Mapped[str] = mapped_column(String(64), nullable=False)
    source_b: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_a_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_b_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_value: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='open', index=True)
    resolved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolve_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MappingReconciliationRun(Base):
    __tablename__ = 'mapping_reconciliation_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_mode: Mapped[str] = mapped_column(String(32), nullable=False, default='dry_run', index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='completed', index=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    reference_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reference_source: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    reference_rows_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    system_rows_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_match_rate: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    request_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    result_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
