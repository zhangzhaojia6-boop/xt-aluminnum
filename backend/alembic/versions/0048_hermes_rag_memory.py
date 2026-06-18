"""hermes rag memory

Revision ID: 0048_hermes_rag_memory
Revises: 0047_normalize_quality_yield_p_columns
Create Date: 2026-06-18 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0048_hermes_rag_memory'
down_revision = '0047_normalize_quality_yield_p_columns'
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def _create_index(table_name: str, column_name: str, *, unique: bool = False) -> None:
    op.create_index(f'ix_{table_name}_{column_name}', table_name, [column_name], unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'rag_embeddings'):
        op.create_table(
            'rag_embeddings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('document_id', sa.Integer(), sa.ForeignKey('rag_documents.id'), nullable=False),
            sa.Column('chunk_id', sa.Integer(), sa.ForeignKey('rag_chunks.id'), nullable=False),
            sa.Column('provider', sa.String(32), nullable=False),
            sa.Column('model', sa.String(128), nullable=True),
            sa.Column('vector_payload', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(32), nullable=False, server_default='ready'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('document_id', 'provider', 'model', 'status'):
            _create_index('rag_embeddings', column)
        _create_index('rag_embeddings', 'chunk_id', unique=True)

    if not _has_table(inspector, 'rag_source_ingestions'):
        op.create_table(
            'rag_source_ingestions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_type', sa.String(64), nullable=False),
            sa.Column('source_ref', sa.String(512), nullable=False),
            sa.Column('status', sa.String(32), nullable=False, server_default='active'),
            sa.Column('document_id', sa.Integer(), sa.ForeignKey('rag_documents.id'), nullable=True),
            sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('metadata_payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('source_type', 'source_ref', 'status', 'document_id', 'actor_user_id'):
            _create_index('rag_source_ingestions', column)

    if not _has_table(inspector, 'hermes_learning_events'):
        op.create_table(
            'hermes_learning_events',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('trace_id', sa.String(128), nullable=True),
            sa.Column('question', sa.Text(), nullable=False),
            sa.Column('tools_called', sa.JSON(), nullable=True),
            sa.Column('sources', sa.JSON(), nullable=True),
            sa.Column('answer', sa.Text(), nullable=False),
            sa.Column('user_feedback', sa.Text(), nullable=True),
            sa.Column('human_correction', sa.Text(), nullable=True),
            sa.Column('status', sa.String(32), nullable=False, server_default='candidate'),
            sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('trace_id', 'status', 'actor_user_id'):
            _create_index('hermes_learning_events', column)

    if not _has_table(inspector, 'hermes_short_term_memories'):
        op.create_table(
            'hermes_short_term_memories',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('conversation_key', sa.String(256), nullable=False),
            sa.Column('memory_key', sa.String(128), nullable=False),
            sa.Column('memory_value', sa.JSON(), nullable=True),
            sa.Column('trace_id', sa.String(128), nullable=True),
            sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('conversation_key', 'memory_key', 'trace_id', 'actor_user_id', 'expires_at'):
            _create_index('hermes_short_term_memories', column)

    if not _has_table(inspector, 'hermes_approved_lessons'):
        op.create_table(
            'hermes_approved_lessons',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('learning_event_id', sa.Integer(), sa.ForeignKey('hermes_learning_events.id'), nullable=True),
            sa.Column('lesson_text', sa.Text(), nullable=False),
            sa.Column('source_payload', sa.JSON(), nullable=True),
            sa.Column('document_id', sa.Integer(), sa.ForeignKey('rag_documents.id'), nullable=True),
            sa.Column('approved_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('status', sa.String(32), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('learning_event_id', 'document_id', 'approved_by_id', 'status'):
            _create_index('hermes_approved_lessons', column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, indexes in (
        ('hermes_approved_lessons', ('learning_event_id', 'document_id', 'approved_by_id', 'status')),
        ('hermes_short_term_memories', ('conversation_key', 'memory_key', 'trace_id', 'actor_user_id', 'expires_at')),
        ('hermes_learning_events', ('trace_id', 'status', 'actor_user_id')),
        ('rag_source_ingestions', ('source_type', 'source_ref', 'status', 'document_id', 'actor_user_id')),
        ('rag_embeddings', ('document_id', 'provider', 'model', 'status', 'chunk_id')),
    ):
        if not _has_table(inspector, table_name):
            continue
        for column in indexes:
            _safe_drop_index(f'ix_{table_name}_{column}', table_name)
        op.drop_table(table_name)
