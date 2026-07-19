"""promote imported daily report metrics into auditable facts

Revision ID: 0057_imported_daily_metric_facts
Revises: 0056_owner_daily_entry_dedupe
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = '0057_imported_daily_metric_facts'
down_revision = '0056_owner_daily_entry_dedupe'
branch_labels = None
depends_on = None


TABLE_NAME = 'imported_daily_metric_facts'
ACTIVE_INDEX = 'uq_imported_daily_metric_active_key'
SHIFT_TABLE_NAME = 'shift_production_data'
SHIFT_ACTIVE_INDEX = 'uq_shift_production_active_key'
json_object_type = sa.JSON().with_variant(JSONB, 'postgresql')


def _ensure_sqlite_shift_active_index() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        return
    inspector = sa.inspect(bind)
    if SHIFT_TABLE_NAME not in inspector.get_table_names():
        return
    indexes = {item['name'] for item in inspector.get_indexes(SHIFT_TABLE_NAME)}
    if SHIFT_ACTIVE_INDEX in indexes:
        op.drop_index(SHIFT_ACTIVE_INDEX, table_name=SHIFT_TABLE_NAME)
    op.create_index(
        SHIFT_ACTIVE_INDEX,
        SHIFT_TABLE_NAME,
        ['business_date', 'shift_config_id', 'workshop_id', 'equipment_id'],
        unique=True,
        sqlite_where=sa.text("data_status <> 'voided'"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        op.create_table(
            TABLE_NAME,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('field_name', sa.String(length=128), nullable=False),
            sa.Column('metric_value', sa.Numeric(18, 6), nullable=False),
            sa.Column('unit', sa.String(length=32), nullable=False),
            sa.Column('source_kind', sa.String(length=64), nullable=False),
            sa.Column('import_batch_id', sa.Integer(), sa.ForeignKey('import_batches.id'), nullable=False),
            sa.Column('import_row_id', sa.Integer(), sa.ForeignKey('import_rows.id'), nullable=False),
            sa.Column('source_anchors', json_object_type, nullable=False),
            sa.Column('lineage_hash', sa.String(length=64), nullable=False),
            sa.Column('metric_contract_version', sa.String(length=32), nullable=False),
            sa.Column('data_status', sa.String(length=16), nullable=False, server_default='confirmed'),
            sa.Column('version_no', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('superseded_by_id', sa.Integer(), sa.ForeignKey(f'{TABLE_NAME}.id'), nullable=True),
            sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('voided_reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)

    indexes = {item['name'] for item in inspector.get_indexes(TABLE_NAME)}
    for column_name in (
        'business_date',
        'field_name',
        'source_kind',
        'import_batch_id',
        'import_row_id',
        'lineage_hash',
        'data_status',
        'superseded_by_id',
    ):
        index_name = f'ix_{TABLE_NAME}_{column_name}'
        if index_name not in indexes:
            op.create_index(index_name, TABLE_NAME, [column_name], unique=False)
    if ACTIVE_INDEX not in indexes:
        op.create_index(
            ACTIVE_INDEX,
            TABLE_NAME,
            ['business_date', 'field_name', 'source_kind'],
            unique=True,
            postgresql_where=sa.text("data_status = 'confirmed'"),
            sqlite_where=sa.text("data_status = 'confirmed'"),
        )
    _ensure_sqlite_shift_active_index()


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME in inspector.get_table_names():
        op.drop_table(TABLE_NAME)
    # Superseded shift rows may now coexist, so keep the corrected active-row invariant.
    _ensure_sqlite_shift_active_index()
