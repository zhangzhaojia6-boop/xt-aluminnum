from datetime import date, datetime
from typing import Any, Optional
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


json_list_type = JSON().with_variant(JSONB, "postgresql")


class Workshop(Base):
    __tablename__ = "workshops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    workshop_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class Team(Base):
    __tablename__ = "teams"

    __table_args__ = (
        UniqueConstraint("workshop_id", "code", name="uq_teams_workshop_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workshop_id: Mapped[int] = mapped_column(Integer, ForeignKey("workshops.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    workshop_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workshops.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    workshop_id: Mapped[int] = mapped_column(Integer, ForeignKey("workshops.id"), nullable=False, index=True)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    position_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("positions.id"), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    dingtalk_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    dingtalk_union_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    workshop_id: Mapped[int] = mapped_column(Integer, ForeignKey("workshops.id"), nullable=False, index=True)
    equipment_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    spec: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    operational_status: Mapped[str] = mapped_column(String(20), default="stopped", nullable=False)
    shift_mode: Mapped[str] = mapped_column(String(10), default="three", nullable=False)
    assigned_shift_ids: Mapped[list[int] | None] = mapped_column(json_list_type, nullable=True)
    custom_fields: Mapped[list[dict] | None] = mapped_column(json_list_type, nullable=True, default=list)
    qr_code: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    bound_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    bound_user = relationship("User", foreign_keys=[bound_user_id])

    @property
    def bound_username(self) -> str | None:
        return self.bound_user.username if self.bound_user is not None else None

    @property
    def bound_user_name(self) -> str | None:
        return self.bound_user.name if self.bound_user is not None else None


class WorkshopTemplateConfig(Base):
    __tablename__ = "workshop_template_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    template_key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    tempo: Mapped[str] = mapped_column(String(16), nullable=False, default="fast")
    supports_ocr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    entry_fields: Mapped[list[dict[str, Any]]] = mapped_column(json_list_type, nullable=False, default=list)
    extra_fields: Mapped[list[dict[str, Any]]] = mapped_column(json_list_type, nullable=False, default=list)
    qc_fields: Mapped[list[dict[str, Any]]] = mapped_column(json_list_type, nullable=False, default=list)
    readonly_fields: Mapped[list[dict[str, Any]]] = mapped_column(json_list_type, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class MasterCodeAlias(Base):
    __tablename__ = "master_code_aliases"
    __table_args__ = (
        UniqueConstraint("entity_type", "alias_code", "source_type", name="uq_master_code_aliases_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    canonical_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    alias_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    alias_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
