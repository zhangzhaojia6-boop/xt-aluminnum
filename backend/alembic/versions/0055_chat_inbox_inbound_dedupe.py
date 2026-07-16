"""make DingTalk ingress inbox creation concurrency-safe

Revision ID: 0055_chat_inbox_inbound_dedupe
Revises: 0054_dingtalk_inbound_receipts
Create Date: 2026-07-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0055_chat_inbox_inbound_dedupe'
down_revision = '0054_dingtalk_inbound_receipts'
branch_labels = None
depends_on = None


TABLE_NAME = 'chat_inbox'
COLUMN_NAME = 'inbound_dedupe_key'
INDEX_NAME = 'ix_chat_inbox_inbound_dedupe_key'


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return
    columns = {column['name']: column for column in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME not in columns:
        op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, sa.String(length=64), nullable=True))
    else:
        column = columns[COLUMN_NAME]
        if not isinstance(column['type'], sa.String) or getattr(column['type'], 'length', None) != 64:
            raise RuntimeError(f'incompatible {TABLE_NAME}.{COLUMN_NAME} type')
        if not bool(column['nullable']):
            raise RuntimeError(f'incompatible {TABLE_NAME}.{COLUMN_NAME} nullability')

    inspector = sa.inspect(op.get_bind())
    indexes = {index['name']: index for index in inspector.get_indexes(TABLE_NAME)}
    index = indexes.get(INDEX_NAME)
    if index is None:
        op.create_index(INDEX_NAME, TABLE_NAME, [COLUMN_NAME], unique=True)
    elif tuple(index.get('column_names') or ()) != (COLUMN_NAME,) or not bool(index.get('unique')):
        raise RuntimeError(f'incompatible {INDEX_NAME} definition')


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return
    indexes = {index['name'] for index in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns(TABLE_NAME)}
    if COLUMN_NAME in columns:
        op.drop_column(TABLE_NAME, COLUMN_NAME)
