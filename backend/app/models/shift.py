from datetime import datetime, time
from typing import Optional
from sqlalchemy import Integer, String, Boolean, DateTime, Time, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ShiftConfig(Base):
    __tablename__ = "shift_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    shift_type: Mapped[str] = mapped_column(String(16), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_cross_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    business_day_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    late_tolerance_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    early_tolerance_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    workshop_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workshops.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
