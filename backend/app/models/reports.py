from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import json_object_type


class DailyReport(Base):
    __tablename__ = 'daily_reports'
    __table_args__ = (UniqueConstraint('report_date', 'report_type', name='uq_report_date_type'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    workshop_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=True, index=True)

    report_data: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    text_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_scope: Mapped[str] = mapped_column(String(32), nullable=False, default='auto_confirmed')
    output_mode: Mapped[str] = mapped_column(String(16), nullable=False, default='both')
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='draft')
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    final_text_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_confirmed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    final_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_final_version: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quality_gate_status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending')
    quality_gate_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DailyFactBundleRun(Base):
    __tablename__ = 'daily_fact_bundle_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    requested_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='partial', index=True)
    source_status: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DailyFactBundleSnapshot(Base):
    __tablename__ = 'daily_fact_bundle_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('daily_fact_bundle_runs.id'), nullable=True, index=True)
    snapshot_key: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    snapshot_reason: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    facts: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    sources: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    conflicts: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    adopted_values: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    correction_refs: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    dingtalk_refs: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    output_skill_alignment: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DailyFactCorrection(Base):
    __tablename__ = 'daily_fact_corrections'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_value: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DailyReportHistoryRecord(Base):
    __tablename__ = 'daily_report_history_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, default='daily', index=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    period_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source_snapshot_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('daily_fact_bundle_snapshots.id'), nullable=True, index=True
    )
    source_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('daily_fact_bundle_runs.id'), nullable=True, index=True
    )
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    report_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    source_summary: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    facts_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OperationPeriodSnapshot(Base):
    __tablename__ = 'operation_period_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='ready', index=True)
    cumulative_metrics: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    analysis_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    source_daily_report_ids: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    source_snapshot_ids: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    missing_dates: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('period_type', 'period_start', 'period_end', name='uq_operation_period_snapshot_period'),
    )
