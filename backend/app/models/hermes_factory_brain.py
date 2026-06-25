from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, json_object_type


class HermesSoulProfile(Base):
    __tablename__ = 'hermes_soul_profiles'
    __table_args__ = (
        UniqueConstraint('profile_key', 'version', name='uq_hermes_soul_profile_key_version'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    soul_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class HermesLongTermRule(Base):
    __tablename__ = 'hermes_long_term_rules'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_rule: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    scope_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default='low', index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    source_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class HermesDingTalkSamplingRule(Base):
    __tablename__ = 'hermes_dingtalk_sampling_rules'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    channel_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    specialist_user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content_types: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    time_window_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default='high', index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class HermesKnowledgeUnit(Base):
    __tablename__ = 'hermes_knowledge_units'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    layer: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    unit_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    verification_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='candidate', index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey('rag_documents.id'), nullable=True, index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    verified_by: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class HermesCodexConstructionRun(Base):
    __tablename__ = 'hermes_codex_construction_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    construction_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    authorization_level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='requested', index=True)
    payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    result_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
