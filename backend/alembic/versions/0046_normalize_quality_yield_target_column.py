"""normalize quality yield target column

Revision ID: 0046_normalize_quality_yield_target_column
Revises: 0045_mapping_reconciliation_runs
Create Date: 2026-06-17 21:05:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0046_normalize_quality_yield_target_column'
down_revision = '0045_mapping_reconciliation_runs'
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return any(column['name'] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = 'quality_yield_daily'
    if not _has_table(inspector, table_name):
        return
    if _has_column(inspector, table_name, 'yield_target_M') and not _has_column(inspector, table_name, 'yield_target_m'):
        op.alter_column(table_name, 'yield_target_M', new_column_name='yield_target_m')


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = 'quality_yield_daily'
    if not _has_table(inspector, table_name):
        return
    if _has_column(inspector, table_name, 'yield_target_m') and not _has_column(inspector, table_name, 'yield_target_M'):
        op.alter_column(table_name, 'yield_target_m', new_column_name='yield_target_M')
