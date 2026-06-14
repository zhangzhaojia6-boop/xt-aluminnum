"""agent outbox dedupe window

Revision ID: 0044_agent_outbox_dedupe_window
Revises: 0043_agent_outbox_retry_dead_letter
Create Date: 2026-06-15 10:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0044_agent_outbox_dedupe_window'
down_revision = '0043_agent_outbox_retry_dead_letter'
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return any(column.get('name') == column_name for column in inspector.get_columns(table_name))


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'agent_outbox_messages'):
        return
    if not _has_column(inspector, 'agent_outbox_messages', 'dedupe_key'):
        op.add_column('agent_outbox_messages', sa.Column('dedupe_key', sa.String(160), nullable=True))
        op.create_index('ix_agent_outbox_messages_dedupe_key', 'agent_outbox_messages', ['dedupe_key'])
    if not _has_column(inspector, 'agent_outbox_messages', 'dedupe_expires_at'):
        op.add_column('agent_outbox_messages', sa.Column('dedupe_expires_at', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_agent_outbox_messages_dedupe_expires_at', 'agent_outbox_messages', ['dedupe_expires_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, 'agent_outbox_messages', 'dedupe_expires_at'):
        _safe_drop_index('ix_agent_outbox_messages_dedupe_expires_at', 'agent_outbox_messages')
        op.drop_column('agent_outbox_messages', 'dedupe_expires_at')
    if _has_column(inspector, 'agent_outbox_messages', 'dedupe_key'):
        _safe_drop_index('ix_agent_outbox_messages_dedupe_key', 'agent_outbox_messages')
        op.drop_column('agent_outbox_messages', 'dedupe_key')
