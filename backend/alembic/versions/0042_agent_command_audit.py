"""agent command audit

Revision ID: 0042_agent_command_audit
Revises: 0041_rag_documents
Create Date: 2026-06-15 09:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0042_agent_command_audit'
down_revision = '0041_rag_documents'
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

    if not _has_table(inspector, 'chat_inbox'):
        op.create_table(
            'chat_inbox',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('channel', sa.String(32), nullable=False),
            sa.Column('group_id', sa.String(256), nullable=True),
            sa.Column('sender_external_id', sa.String(128), nullable=True),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('agent_code', sa.String(64), nullable=True),
            sa.Column('trace_id', sa.String(128), nullable=False),
            sa.Column('source_payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('channel', 'group_id', 'sender_external_id', 'agent_code', 'trace_id'):
            op.create_index(f'ix_chat_inbox_{column}', 'chat_inbox', [column])

    if not _has_table(inspector, 'agent_runs'):
        op.create_table(
            'agent_runs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('trace_id', sa.String(128), nullable=False),
            sa.Column('agent_code', sa.String(64), nullable=False),
            sa.Column('chat_inbox_id', sa.Integer(), sa.ForeignKey('chat_inbox.id'), nullable=True),
            sa.Column('status', sa.String(32), nullable=False, server_default='answered'),
            sa.Column('status_color', sa.String(16), nullable=False, server_default='green'),
            sa.Column('answer', sa.Text(), nullable=False),
            sa.Column('rag_citation_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('result_payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('trace_id', 'agent_code', 'chat_inbox_id', 'status', 'status_color'):
            op.create_index(f'ix_agent_runs_{column}', 'agent_runs', [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'agent_runs'):
        for column in ('trace_id', 'agent_code', 'chat_inbox_id', 'status', 'status_color'):
            _safe_drop_index(f'ix_agent_runs_{column}', 'agent_runs')
        op.drop_table('agent_runs')

    if _has_table(inspector, 'chat_inbox'):
        for column in ('channel', 'group_id', 'sender_external_id', 'agent_code', 'trace_id'):
            _safe_drop_index(f'ix_chat_inbox_{column}', 'chat_inbox')
        op.drop_table('chat_inbox')
