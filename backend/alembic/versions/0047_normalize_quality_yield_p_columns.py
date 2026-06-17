"""normalize quality yield p target columns

Revision ID: 0047_normalize_quality_yield_p_columns
Revises: 0046_normalize_quality_yield_target_column
Create Date: 2026-06-17 21:25:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0047_normalize_quality_yield_p_columns'
down_revision = '0046_normalize_quality_yield_target_column'
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return any(column['name'] == column_name for column in inspector.get_columns(table_name))


def _rename_if_needed(inspector: sa.Inspector, table_name: str, old_name: str, new_name: str) -> None:
    if _has_column(inspector, table_name, old_name) and not _has_column(inspector, table_name, new_name):
        op.alter_column(table_name, old_name, new_column_name=new_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = 'quality_yield_daily'
    if not _has_table(inspector, table_name):
        return
    _rename_if_needed(inspector, table_name, 'yield_target_P_casting', 'yield_target_p_casting')
    inspector = sa.inspect(bind)
    _rename_if_needed(inspector, table_name, 'yield_target_P_hot_roll', 'yield_target_p_hot_roll')


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = 'quality_yield_daily'
    if not _has_table(inspector, table_name):
        return
    _rename_if_needed(inspector, table_name, 'yield_target_p_casting', 'yield_target_P_casting')
    inspector = sa.inspect(bind)
    _rename_if_needed(inspector, table_name, 'yield_target_p_hot_roll', 'yield_target_P_hot_roll')
