"""rag documents and chunks

Revision ID: 0041_rag_documents
Revises: 0040_agent_communication_outbox
Create Date: 2026-06-15 09:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0041_rag_documents'
down_revision = '0040_agent_communication_outbox'
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'rag_documents'):
        op.create_table(
            'rag_documents',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('filename', sa.String(255), nullable=False),
            sa.Column('source_name', sa.String(255), nullable=False),
            sa.Column('content_type', sa.String(128), nullable=True),
            sa.Column('encoding', sa.String(32), nullable=False),
            sa.Column('status', sa.String(32), nullable=False, server_default='active'),
            sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('uploaded_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('scope_payload', sa.JSON(), nullable=True),
            sa.Column('metadata_payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('filename', 'status', 'uploaded_by_id'):
            op.create_index(f'ix_rag_documents_{column}', 'rag_documents', [column])

    if not _has_table(inspector, 'rag_chunks'):
        op.create_table(
            'rag_chunks',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('document_id', sa.Integer(), sa.ForeignKey('rag_documents.id'), nullable=False),
            sa.Column('chunk_index', sa.Integer(), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('char_start', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('char_end', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('source_ref', sa.String(320), nullable=False),
            sa.Column('metadata_payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('document_id', 'chunk_index', 'source_ref'):
            op.create_index(f'ix_rag_chunks_{column}', 'rag_chunks', [column])

    if not _has_table(inspector, 'rag_query_logs'):
        op.create_table(
            'rag_query_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('query_text', sa.Text(), nullable=False),
            sa.Column('answer', sa.Text(), nullable=False),
            sa.Column('result_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('citations', sa.JSON(), nullable=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_rag_query_logs_user_id', 'rag_query_logs', ['user_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'rag_query_logs'):
        _safe_drop_index('ix_rag_query_logs_user_id', 'rag_query_logs')
        op.drop_table('rag_query_logs')

    if _has_table(inspector, 'rag_chunks'):
        for column in ('document_id', 'chunk_index', 'source_ref'):
            _safe_drop_index(f'ix_rag_chunks_{column}', 'rag_chunks')
        op.drop_table('rag_chunks')

    if _has_table(inspector, 'rag_documents'):
        for column in ('filename', 'status', 'uploaded_by_id'):
            _safe_drop_index(f'ix_rag_documents_{column}', 'rag_documents')
        op.drop_table('rag_documents')
