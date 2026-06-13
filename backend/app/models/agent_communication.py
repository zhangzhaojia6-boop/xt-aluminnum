from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, json_object_type


class AgentProfile(Base):
    __tablename__ = 'agent_profiles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False, default='reporting', index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default='factory', index=True)
    workshop_id: Mapped[int | None] = mapped_column(ForeignKey('workshops.id'), nullable=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id'), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    config_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CommunicationChannel(Base):
    __tablename__ = 'communication_channels'
    __table_args__ = (UniqueConstraint('channel_type', 'channel_key', name='uq_communication_channel_type_key'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    channel_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    workshop_id: Mapped[int | None] = mapped_column(ForeignKey('workshops.id'), nullable=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id'), nullable=True, index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    secret_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AgentChannelBinding(Base):
    __tablename__ = 'agent_channel_bindings'
    __table_args__ = (UniqueConstraint('agent_profile_id', 'channel_id', name='uq_agent_channel_binding'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_profile_id: Mapped[int] = mapped_column(ForeignKey('agent_profiles.id'), nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey('communication_channels.id'), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    min_severity: Mapped[str] = mapped_column(String(32), nullable=False, default='info')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AgentEvent(Base):
    __tablename__ = 'agent_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default='info', index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='pending', index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default='factory', index=True)
    workshop_id: Mapped[int | None] = mapped_column(ForeignKey('workshops.id'), nullable=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey('teams.id'), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default='system', index=True)
    source_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AgentOutboxMessage(Base):
    __tablename__ = 'agent_outbox_messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dispatch_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    agent_profile_id: Mapped[int | None] = mapped_column(ForeignKey('agent_profiles.id'), nullable=True, index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey('communication_channels.id'), nullable=True, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey('agent_events.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='pending', index=True)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default='markdown')
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source_summary: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ExternalMessageLog(Base):
    __tablename__ = 'external_message_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    outbox_message_id: Mapped[int | None] = mapped_column(ForeignKey('agent_outbox_messages.id'), nullable=True, index=True)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    channel_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MultimodalEvidence(Base):
    __tablename__ = 'multimodal_evidence'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_channel_id: Mapped[int | None] = mapped_column(ForeignKey('communication_channels.id'), nullable=True, index=True)
    source_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey('agent_events.id'), nullable=True, index=True)
    file_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recognized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_status: Mapped[str] = mapped_column(String(32), nullable=False, default='machine_only', index=True)
    payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AgentOperationApproval(Base):
    __tablename__ = 'agent_operation_approvals'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='pending', index=True)
    requester_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    approver_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey('communication_channels.id'), nullable=True, index=True)
    preview_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    result_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AgentRateLimit(Base):
    __tablename__ = 'agent_rate_limits'
    __table_args__ = (UniqueConstraint('scope_key', 'event_key', name='uq_agent_rate_limit_scope_event'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
