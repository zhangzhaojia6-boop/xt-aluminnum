from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyReport(Base):
    __tablename__ = 'daily_reports'
    __table_args__ = (UniqueConstraint('report_date', 'report_type', name='uq_report_date_type'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    workshop_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=True, index=True)

    report_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
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
