"""daily fact scheduled snapshot key

Revision ID: 0053_daily_fact_snapshot_key
Revises: 0052_hermes_factory_brain
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0053_daily_fact_snapshot_key'
down_revision = '0052_hermes_factory_brain'
branch_labels = None
depends_on = None


TABLE_NAME = 'daily_fact_bundle_snapshots'
INDEX_NAME = 'ix_daily_fact_bundle_snapshots_snapshot_key'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns(TABLE_NAME)}
    if 'snapshot_key' not in columns:
        op.add_column(TABLE_NAME, sa.Column('snapshot_key', sa.String(length=200), nullable=True))

    inspector = sa.inspect(bind)
    indexes = {index['name'] for index in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME not in indexes:
        op.create_index(INDEX_NAME, TABLE_NAME, ['snapshot_key'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index['name'] for index in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)

    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns(TABLE_NAME)}
    if 'snapshot_key' in columns:
        with op.batch_alter_table(TABLE_NAME) as batch_op:
            batch_op.drop_column('snapshot_key')
