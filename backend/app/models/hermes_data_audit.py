from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, json_object_type


class HermesDataAuditRun(Base):
    __tablename__ = 'hermes_data_audit_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='pending', index=True)
    source_status: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    source_errors: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    mes_snapshot: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    hub_snapshot: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    output_skill_snapshot: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    diffs: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    suggested_actions: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    match_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class HermesCorrectionAction(Base):
    __tablename__ = 'hermes_correction_actions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_run_id: Mapped[int] = mapped_column(Integer, ForeignKey('hermes_data_audit_runs.id'), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default='low')
    target_table: Mapped[str] = mapped_column(String(128), nullable=False)
    target_key: Mapped[str] = mapped_column(String(256), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    before_value: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    evidence: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='pending')
    applied_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_status: Mapped[str] = mapped_column(String(32), nullable=False, default='not_requested')
    rollback_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
