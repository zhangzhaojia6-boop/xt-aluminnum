"""atomic DingTalk inbound receipts

Revision ID: 0054_dingtalk_inbound_receipts
Revises: 0053_daily_fact_snapshot_key
Create Date: 2026-07-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0054_dingtalk_inbound_receipts'
down_revision = '0053_daily_fact_snapshot_key'
branch_labels = None
depends_on = None


TABLE_NAME = 'dingtalk_inbound_receipts'
EXPECTED_COLUMNS = {
    'id': (sa.Integer, False, None),
    'dedupe_key': (sa.String, False, 64),
    'channel': (sa.String, False, 32),
    'group_id': (sa.String, True, 256),
    'trace_id': (sa.String, False, 128),
    'status': (sa.String, False, 32),
    'attempt_count': (sa.Integer, False, None),
    'created_at': (sa.DateTime, False, None),
    'updated_at': (sa.DateTime, False, None),
}
EXPECTED_INDEXES = (
    ('ix_dingtalk_inbound_receipts_dedupe_key', ('dedupe_key',), True),
    ('ix_dingtalk_inbound_receipts_channel', ('channel',), False),
    ('ix_dingtalk_inbound_receipts_group_id', ('group_id',), False),
    ('ix_dingtalk_inbound_receipts_trace_id', ('trace_id',), False),
    ('ix_dingtalk_inbound_receipts_status', ('status',), False),
)


def _raise_incompatible(reason: str) -> None:
    raise RuntimeError(f'incompatible existing {TABLE_NAME} table: {reason}')


def _validate_existing_table(inspector) -> None:
    columns = {column['name']: column for column in inspector.get_columns(TABLE_NAME)}
    if set(columns) != set(EXPECTED_COLUMNS):
        _raise_incompatible(
            f'expected columns {sorted(EXPECTED_COLUMNS)}, found {sorted(columns)}'
        )

    for name, (type_class, nullable, length) in EXPECTED_COLUMNS.items():
        column = columns[name]
        if not isinstance(column['type'], type_class):
            _raise_incompatible(f'column {name} has type {column["type"]}')
        if bool(column['nullable']) is not nullable:
            _raise_incompatible(f'column {name} nullable={column["nullable"]}')
        if length is not None and getattr(column['type'], 'length', None) != length:
            _raise_incompatible(f'column {name} has length {getattr(column["type"], "length", None)}')

    status_default = str(columns['status'].get('default') or '').lower()
    if 'evidence_pending' not in status_default:
        _raise_incompatible('column status has incompatible default')

    attempt_default = str(columns['attempt_count'].get('default') or '').lower()
    attempt_default = attempt_default.split('::', 1)[0].strip("()' ")
    if attempt_default != '0':
        _raise_incompatible('column attempt_count has incompatible default')

    for name in ('created_at', 'updated_at'):
        timestamp_default = str(columns[name].get('default') or '').lower()
        if 'now()' not in timestamp_default and 'current_timestamp' not in timestamp_default:
            _raise_incompatible(f'column {name} has incompatible default')

    if inspector.bind.dialect.name == 'postgresql':
        id_default = str(columns['id'].get('default') or '').lower()
        if columns['id'].get('identity') is None and 'nextval(' not in id_default:
            _raise_incompatible('column id is not database-generated')

    primary_key = inspector.get_pk_constraint(TABLE_NAME).get('constrained_columns') or []
    if primary_key != ['id']:
        _raise_incompatible(f'primary key is {primary_key}')


def _ensure_indexes(inspector=None) -> None:
    existing = {
        index['name']: index
        for index in inspector.get_indexes(TABLE_NAME)
    } if inspector is not None else {}
    for name, columns, unique in EXPECTED_INDEXES:
        index = existing.get(name)
        if index is None:
            op.create_index(name, TABLE_NAME, list(columns), unique=unique)
            continue
        if tuple(index.get('column_names') or ()) != columns or bool(index.get('unique')) is not unique:
            _raise_incompatible(f'index {name} does not match {columns}, unique={unique}')


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME in inspector.get_table_names():
        _validate_existing_table(inspector)
        _ensure_indexes(inspector)
        return

    op.create_table(
        TABLE_NAME,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('dedupe_key', sa.String(length=64), nullable=False),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('group_id', sa.String(length=256), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='evidence_pending'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    _ensure_indexes()


def downgrade() -> None:
    op.drop_index('ix_dingtalk_inbound_receipts_status', table_name='dingtalk_inbound_receipts')
    op.drop_index('ix_dingtalk_inbound_receipts_trace_id', table_name='dingtalk_inbound_receipts')
    op.drop_index('ix_dingtalk_inbound_receipts_group_id', table_name='dingtalk_inbound_receipts')
    op.drop_index('ix_dingtalk_inbound_receipts_channel', table_name='dingtalk_inbound_receipts')
    op.drop_index('ix_dingtalk_inbound_receipts_dedupe_key', table_name='dingtalk_inbound_receipts')
    op.drop_table('dingtalk_inbound_receipts')
