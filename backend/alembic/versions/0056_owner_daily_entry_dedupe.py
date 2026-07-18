"""prevent duplicate owner daily rows for one work order and business date

Revision ID: 0056_owner_daily_entry_dedupe
Revises: 0055_chat_inbox_inbound_dedupe
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0056_owner_daily_entry_dedupe'
down_revision = '0055_chat_inbox_inbound_dedupe'
branch_labels = None
depends_on = None


TABLE_NAME = 'work_order_entries'
INDEX_NAME = 'uq_work_order_entries_owner_daily_work_order_date'
INDEX_COLUMNS = ('work_order_id', 'business_date', 'entry_type')


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return
    duplicate = bind.execute(
        sa.text(
            """
            SELECT work_order_id, business_date, COUNT(*) AS row_count
            FROM work_order_entries
            WHERE entry_type = 'owner_daily'
            GROUP BY work_order_id, business_date
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).mappings().first()
    if duplicate is not None:
        raise RuntimeError(
            'duplicate owner_daily rows must be reviewed before creating '
            f"{INDEX_NAME}: work_order_id={duplicate['work_order_id']}, "
            f"business_date={duplicate['business_date']}, row_count={duplicate['row_count']}"
        )

    indexes = {index['name']: index for index in inspector.get_indexes(TABLE_NAME)}
    existing = indexes.get(INDEX_NAME)
    if existing is None:
        op.create_index(
            INDEX_NAME,
            TABLE_NAME,
            list(INDEX_COLUMNS),
            unique=True,
            postgresql_where=sa.text("entry_type = 'owner_daily'"),
            sqlite_where=sa.text("entry_type = 'owner_daily'"),
        )
    elif tuple(existing.get('column_names') or ()) != INDEX_COLUMNS or not bool(existing.get('unique')):
        raise RuntimeError(f'incompatible {INDEX_NAME} definition')


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return
    if INDEX_NAME in {index['name'] for index in inspector.get_indexes(TABLE_NAME)}:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
