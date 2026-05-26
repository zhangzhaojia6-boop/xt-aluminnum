from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
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


class QualityYieldDaily(Base):
    __tablename__ = 'quality_yield_daily'
    __table_args__ = (
        UniqueConstraint('business_date', 'workshop_code', name='uq_quality_yield_date_workshop'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    yield_daily: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    yield_monthly: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    yield_target_m: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    yield_target_p_casting: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    yield_target_p_hot_roll: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    yield_overall_company: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    variance_arrow: Mapped[str | None] = mapped_column(String(8), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QualityIssueLog(Base):
    __tablename__ = 'quality_issue_log'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=True, index=True)
    shift_report_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('mobile_shift_reports.id'), nullable=True, index=True)
    tracking_card_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    quality_issue_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quality_issue_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reported_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
