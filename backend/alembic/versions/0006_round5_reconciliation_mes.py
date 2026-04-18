"""round5 mes import and reconciliation

Revision ID: 0006_round5
Revises: 0005_round4
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0006_round5'
down_revision = '0005_round4'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in inspector.get_columns(table_name)}


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in inspector.get_indexes(table_name)}


def _has_fk(inspector, table_name: str, fk_name: str) -> bool:
    return fk_name in {item.get('name') for item in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'mes_import_records'):
        op.create_table(
            'mes_import_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('import_batch_id', sa.Integer(), nullable=True),
            sa.Column('source_type', sa.String(length=32), nullable=False, server_default='mes_export'),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_code', sa.String(length=64), nullable=True),
            sa.Column('shift_code', sa.String(length=64), nullable=True),
            sa.Column('metric_code', sa.String(length=64), nullable=False),
            sa.Column('metric_name', sa.String(length=128), nullable=True),
            sa.Column('metric_value', sa.Numeric(18, 4), nullable=True),
            sa.Column('unit', sa.String(length=32), nullable=True),
            sa.Column('source_row_no', sa.Integer(), nullable=True),
            sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_mes_import_records_business_date', 'mes_import_records', ['business_date'], unique=False)
        op.create_index('ix_mes_import_records_metric_code', 'mes_import_records', ['metric_code'], unique=False)
        op.create_index('ix_mes_import_records_workshop_code', 'mes_import_records', ['workshop_code'], unique=False)
        op.create_index('ix_mes_import_records_shift_code', 'mes_import_records', ['shift_code'], unique=False)
        if not _has_fk(inspector, 'mes_import_records', 'fk_mes_import_records_import_batch_id'):
            op.create_foreign_key(
                'fk_mes_import_records_import_batch_id',
                'mes_import_records',
                'import_batches',
                ['import_batch_id'],
                ['id'],
            )

    if not _has_table(inspector, 'data_reconciliation_items'):
        op.create_table(
            'data_reconciliation_items',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('reconciliation_type', sa.String(length=64), nullable=False),
            sa.Column('source_a', sa.String(length=64), nullable=False),
            sa.Column('source_b', sa.String(length=64), nullable=False),
            sa.Column('dimension_key', sa.String(length=128), nullable=False),
            sa.Column('field_name', sa.String(length=64), nullable=False),
            sa.Column('source_a_value', sa.Text(), nullable=True),
            sa.Column('source_b_value', sa.Text(), nullable=True),
            sa.Column('diff_value', sa.Numeric(18, 4), nullable=True),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='open'),
            sa.Column('resolved_by', sa.Integer(), nullable=True),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('resolve_note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_data_reconciliation_items_business_date', 'data_reconciliation_items', ['business_date'])
        op.create_index('ix_data_reconciliation_items_reconciliation_type', 'data_reconciliation_items', ['reconciliation_type'])
        op.create_index('ix_data_reconciliation_items_field_name', 'data_reconciliation_items', ['field_name'])
        op.create_index('ix_data_reconciliation_items_status', 'data_reconciliation_items', ['status'])
        if not _has_fk(inspector, 'data_reconciliation_items', 'fk_data_reconciliation_items_resolved_by'):
            op.create_foreign_key(
                'fk_data_reconciliation_items_resolved_by',
                'data_reconciliation_items',
                'users',
                ['resolved_by'],
                ['id'],
            )

    if _has_table(inspector, 'daily_reports'):
        for name, coltype, default in [
            ('final_text_summary', sa.Text(), None),
            ('final_confirmed_by', sa.Integer(), None),
            ('final_confirmed_at', sa.DateTime(timezone=True), None),
            ('is_final_version', sa.Boolean(), sa.text('false')),
        ]:
            if not _has_column(inspector, 'daily_reports', name):
                op.add_column('daily_reports', sa.Column(name, coltype, nullable=True, server_default=default))

        if not _has_fk(inspector, 'daily_reports', 'fk_daily_reports_final_confirmed_by'):
            op.create_foreign_key(
                'fk_daily_reports_final_confirmed_by',
                'daily_reports',
                'users',
                ['final_confirmed_by'],
                ['id'],
            )

        op.execute(sa.text("UPDATE daily_reports SET is_final_version = false WHERE is_final_version IS NULL"))
        op.alter_column('daily_reports', 'is_final_version', existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'daily_reports'):
        if _has_fk(inspector, 'daily_reports', 'fk_daily_reports_final_confirmed_by'):
            op.drop_constraint('fk_daily_reports_final_confirmed_by', 'daily_reports', type_='foreignkey')
        for column_name in ['is_final_version', 'final_confirmed_at', 'final_confirmed_by', 'final_text_summary']:
            if _has_column(inspector, 'daily_reports', column_name):
                op.drop_column('daily_reports', column_name)

    if _has_table(inspector, 'data_reconciliation_items'):
        for index_name in [
            'ix_data_reconciliation_items_status',
            'ix_data_reconciliation_items_field_name',
            'ix_data_reconciliation_items_reconciliation_type',
            'ix_data_reconciliation_items_business_date',
        ]:
            if _has_index(inspector, 'data_reconciliation_items', index_name):
                op.drop_index(index_name, table_name='data_reconciliation_items')
        if _has_fk(inspector, 'data_reconciliation_items', 'fk_data_reconciliation_items_resolved_by'):
            op.drop_constraint('fk_data_reconciliation_items_resolved_by', 'data_reconciliation_items', type_='foreignkey')
        op.drop_table('data_reconciliation_items')

    if _has_table(inspector, 'mes_import_records'):
        for index_name in [
            'ix_mes_import_records_shift_code',
            'ix_mes_import_records_workshop_code',
            'ix_mes_import_records_metric_code',
            'ix_mes_import_records_business_date',
        ]:
            if _has_index(inspector, 'mes_import_records', index_name):
                op.drop_index(index_name, table_name='mes_import_records')
        if _has_fk(inspector, 'mes_import_records', 'fk_mes_import_records_import_batch_id'):
            op.drop_constraint('fk_mes_import_records_import_batch_id', 'mes_import_records', type_='foreignkey')
        op.drop_table('mes_import_records')
