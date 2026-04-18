"""work order template payload storage

Revision ID: 0012_work_order_template_payloads
Revises: 0011_work_orders_core
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = '0012_work_order_template_payloads'
down_revision = '0011_work_orders_core'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'work_order_entries'):
        if not _has_column(inspector, 'work_order_entries', 'extra_payload'):
            op.add_column('work_order_entries', sa.Column('extra_payload', sa.JSON(), nullable=True))
        if not _has_column(inspector, 'work_order_entries', 'qc_payload'):
            op.add_column('work_order_entries', sa.Column('qc_payload', sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'work_order_entries'):
        if _has_column(inspector, 'work_order_entries', 'qc_payload'):
            op.drop_column('work_order_entries', 'qc_payload')
        if _has_column(inspector, 'work_order_entries', 'extra_payload'):
            op.drop_column('work_order_entries', 'extra_payload')
