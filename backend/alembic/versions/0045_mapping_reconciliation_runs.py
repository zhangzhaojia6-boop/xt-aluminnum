"""mapping reconciliation runs

Revision ID: 0045_mapping_reconciliation_runs
Revises: 0044_agent_outbox_dedupe_window
Create Date: 2026-06-15 16:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0045_mapping_reconciliation_runs'
down_revision = '0044_agent_outbox_dedupe_window'
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

    if _has_table(inspector, 'mapping_reconciliation_runs'):
        return
    op.create_table(
        'mapping_reconciliation_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_mode', sa.String(32), nullable=False, server_default='dry_run'),
        sa.Column('status', sa.String(32), nullable=False, server_default='completed'),
        sa.Column('business_date', sa.Date(), nullable=True),
        sa.Column('reference_file', sa.String(512), nullable=True),
        sa.Column('reference_source', sa.String(512), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reference_rows_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('system_rows_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('overall_match_rate', sa.Numeric(8, 4), nullable=False, server_default='0'),
        sa.Column('request_payload', sa.JSON(), nullable=True),
        sa.Column('result_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ('run_mode', 'status', 'business_date', 'created_by_id'):
        op.create_index(f'ix_mapping_reconciliation_runs_{column}', 'mapping_reconciliation_runs', [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'mapping_reconciliation_runs'):
        return
    for column in ('run_mode', 'status', 'business_date', 'created_by_id'):
        _safe_drop_index(f'ix_mapping_reconciliation_runs_{column}', 'mapping_reconciliation_runs')
    op.drop_table('mapping_reconciliation_runs')
