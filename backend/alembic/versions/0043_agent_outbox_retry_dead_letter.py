"""agent outbox retry dead letter

Revision ID: 0043_agent_outbox_retry_dead_letter
Revises: 0042_agent_command_audit
Create Date: 2026-06-15 10:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0043_agent_outbox_retry_dead_letter'
down_revision = '0042_agent_command_audit'
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

    if _has_table(inspector, 'agent_outbox_messages') and not _has_column(inspector, 'agent_outbox_messages', 'next_retry_at'):
        op.add_column('agent_outbox_messages', sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_agent_outbox_messages_next_retry_at', 'agent_outbox_messages', ['next_retry_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, 'agent_outbox_messages', 'next_retry_at'):
        _safe_drop_index('ix_agent_outbox_messages_next_retry_at', 'agent_outbox_messages')
        op.drop_column('agent_outbox_messages', 'next_retry_at')
