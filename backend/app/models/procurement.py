from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

json_type = JSON().with_variant(JSONB, 'postgresql')


class ProcurementAssignment(Base):
    __tablename__ = 'procurement_assignments'
    __table_args__ = (UniqueConstraint('user_id', 'role', name='uq_procurement_assignment'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcurementRequest(Base):
    __tablename__ = 'procurement_requests'

    id: Mapped[int] = mapped_column(primary_key=True)
    request_no: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    workshop_id: Mapped[int | None] = mapped_column(ForeignKey('workshops.id'), nullable=True, index=True)

    material_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    specification: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    purchase_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    estimated_unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    needed_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    backfill_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    needs_quality_check: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    supplier: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    current_step: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='open', index=True)
    step_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ProcurementQuote(Base):
    __tablename__ = 'procurement_quotes'

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey('procurement_requests.id'), nullable=False, index=True)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supplier: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcurementDocument(Base):
    """上传后不改不删，留作单据依据。"""

    __tablename__ = 'procurement_documents'

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey('procurement_requests.id'), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcurementStepLog(Base):
    """每次办理一条，只增不改。"""

    __tablename__ = 'procurement_step_logs'

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey('procurement_requests.id'), nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    to_step: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
