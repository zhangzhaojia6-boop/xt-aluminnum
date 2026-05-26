from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import json_object_type


class DailyConsumableLog(Base):
    """Per-workshop daily auxiliary material log.

    One row per (workshop_id, business_date). All values stored under
    `payload` so the schema follows the workshop's consumable template
    (see app.core.templates.MACHINE_OPERATOR_CONSUMABLE_FIELDS) without
    schema migrations when fields evolve.
    """

    __tablename__ = 'daily_consumable_logs'
    __table_args__ = (
        UniqueConstraint('workshop_id', 'business_date', name='uq_daily_consumable_workshop_date'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workshop_id: Mapped[int] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=False, index=True)
    workshop_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
