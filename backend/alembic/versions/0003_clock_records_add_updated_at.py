"""add updated_at to clock_records for timestamp mixin compatibility

Revision ID: 0003_clock_upd_at
Revises: 0002_attendance_round2
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


revision = '0003_clock_upd_at'
down_revision = '0002_attendance_round2'
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'clock_records' in inspector.get_table_names() and not _has_column(inspector, 'clock_records', 'updated_at'):
        op.add_column(
            'clock_records',
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'clock_records' in inspector.get_table_names() and _has_column(inspector, 'clock_records', 'updated_at'):
        op.drop_column('clock_records', 'updated_at')
