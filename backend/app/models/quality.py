from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DataQualityIssue(Base):
    __tablename__ = 'data_quality_issues'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    dimension_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    field_name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    issue_level: Mapped[str] = mapped_column(String(16), nullable=False, default='warning', index=True)
    issue_desc: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='open', index=True)
    resolved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolve_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
