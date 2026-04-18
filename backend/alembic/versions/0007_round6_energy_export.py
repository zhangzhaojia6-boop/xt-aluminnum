"""round6 energy module and report export

Revision ID: 0007_round6
Revises: 0006_round5
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0007_round6'
down_revision = '0006_round5'
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

    if not _has_table(inspector, 'energy_import_records'):
        op.create_table(
            'energy_import_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('import_batch_id', sa.Integer(), nullable=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_code', sa.String(length=64), nullable=True),
            sa.Column('shift_code', sa.String(length=64), nullable=True),
            sa.Column('energy_type', sa.String(length=32), nullable=False),
            sa.Column('energy_value', sa.Numeric(18, 4), nullable=True),
            sa.Column('unit', sa.String(length=32), nullable=True),
            sa.Column('source_row_no', sa.Integer(), nullable=True),
            sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_energy_import_records_business_date', 'energy_import_records', ['business_date'], unique=False)
        op.create_index('ix_energy_import_records_workshop_code', 'energy_import_records', ['workshop_code'], unique=False)
        op.create_index('ix_energy_import_records_shift_code', 'energy_import_records', ['shift_code'], unique=False)
        op.create_index('ix_energy_import_records_energy_type', 'energy_import_records', ['energy_type'], unique=False)
        if not _has_fk(inspector, 'energy_import_records', 'fk_energy_import_records_import_batch_id'):
            op.create_foreign_key(
                'fk_energy_import_records_import_batch_id',
                'energy_import_records',
                'import_batches',
                ['import_batch_id'],
                ['id'],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'energy_import_records'):
        for index_name in [
            'ix_energy_import_records_energy_type',
            'ix_energy_import_records_shift_code',
            'ix_energy_import_records_workshop_code',
            'ix_energy_import_records_business_date',
        ]:
            if _has_index(inspector, 'energy_import_records', index_name):
                op.drop_index(index_name, table_name='energy_import_records')
        if _has_fk(inspector, 'energy_import_records', 'fk_energy_import_records_import_batch_id'):
            op.drop_constraint('fk_energy_import_records_import_batch_id', 'energy_import_records', type_='foreignkey')
        op.drop_table('energy_import_records')
