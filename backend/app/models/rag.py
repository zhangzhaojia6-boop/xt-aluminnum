from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, json_object_type


class RagDocument(Base):
    __tablename__ = 'rag_documents'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    encoding: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    scope_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class RagChunk(Base):
    __tablename__ = 'rag_chunks'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('rag_documents.id'), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_ref: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    metadata_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RagQueryLog(Base):
    __tablename__ = 'rag_query_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    citations: Mapped[list | None] = mapped_column(json_object_type, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RagEmbedding(Base):
    __tablename__ = 'rag_embeddings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('rag_documents.id'), nullable=False, index=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey('rag_chunks.id'), nullable=False, unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    vector_payload: Mapped[list | None] = mapped_column(json_object_type, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='ready', index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class RagSourceIngestion(Base):
    __tablename__ = 'rag_source_ingestions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey('rag_documents.id'), nullable=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    metadata_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class HermesLearningEvent(Base):
    __tablename__ = 'hermes_learning_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    tools_called: Mapped[list | None] = mapped_column(json_object_type, nullable=True)
    sources: Mapped[list | None] = mapped_column(json_object_type, nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    user_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_correction: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='candidate', index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class HermesShortTermMemory(Base):
    __tablename__ = 'hermes_short_term_memories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    memory_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    memory_value: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class HermesApprovedLesson(Base):
    __tablename__ = 'hermes_approved_lessons'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    learning_event_id: Mapped[int | None] = mapped_column(ForeignKey('hermes_learning_events.id'), nullable=True, index=True)
    lesson_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey('rag_documents.id'), nullable=True, index=True)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class HermesProfessionalKnowledgeEntry(Base):
    __tablename__ = 'hermes_professional_knowledge_entries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint('domain', 'topic', 'knowledge_type', 'source_ref', name='uq_hermes_professional_knowledge_source'),
    )
