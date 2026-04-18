"""round4 review publish and text report

Revision ID: 0005_round4
Revises: 0004_prod_round3
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


revision = '0005_round4'
down_revision = '0004_prod_round3'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column['name'] for column in inspector.get_columns(table_name)}


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in inspector.get_indexes(table_name)}


def _has_unique(inspector, table_name: str, constraint_name: str) -> bool:
    return constraint_name in {item['name'] for item in inspector.get_unique_constraints(table_name)}


def _has_fk(inspector, table_name: str, fk_name: str) -> bool:
    return fk_name in {item.get('name') for item in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'shift_production_data'):
        add_columns = [
            ('version_no', sa.Integer()),
            ('superseded_by_id', sa.Integer()),
            ('reviewed_by', sa.Integer()),
            ('reviewed_at', sa.DateTime(timezone=True)),
            ('confirmed_by', sa.Integer()),
            ('confirmed_at', sa.DateTime(timezone=True)),
            ('rejected_by', sa.Integer()),
            ('rejected_at', sa.DateTime(timezone=True)),
            ('rejected_reason', sa.Text()),
            ('voided_by', sa.Integer()),
            ('voided_at', sa.DateTime(timezone=True)),
            ('voided_reason', sa.Text()),
            ('published_by', sa.Integer()),
            ('published_at', sa.DateTime(timezone=True)),
        ]
        for name, coltype in add_columns:
            if not _has_column(inspector, 'shift_production_data', name):
                op.add_column('shift_production_data', sa.Column(name, coltype, nullable=True))

        op.execute(sa.text('UPDATE shift_production_data SET version_no = 1 WHERE version_no IS NULL'))
        op.alter_column('shift_production_data', 'version_no', existing_type=sa.Integer(), nullable=False)

        if not _has_fk(inspector, 'shift_production_data', 'fk_shift_production_data_superseded_by_id'):
            op.create_foreign_key(
                'fk_shift_production_data_superseded_by_id',
                'shift_production_data',
                'shift_production_data',
                ['superseded_by_id'],
                ['id'],
            )
        for fk_name, column_name in [
            ('fk_shift_production_data_reviewed_by', 'reviewed_by'),
            ('fk_shift_production_data_confirmed_by', 'confirmed_by'),
            ('fk_shift_production_data_rejected_by', 'rejected_by'),
            ('fk_shift_production_data_voided_by', 'voided_by'),
            ('fk_shift_production_data_published_by', 'published_by'),
        ]:
            if not _has_fk(inspector, 'shift_production_data', fk_name):
                op.create_foreign_key(
                    fk_name,
                    'shift_production_data',
                    'users',
                    [column_name],
                    ['id'],
                )

        for index_name, column_name in [
            ('ix_shift_production_data_superseded_by_id', 'superseded_by_id'),
            ('ix_shift_production_data_reviewed_by', 'reviewed_by'),
            ('ix_shift_production_data_confirmed_by', 'confirmed_by'),
            ('ix_shift_production_data_rejected_by', 'rejected_by'),
            ('ix_shift_production_data_voided_by', 'voided_by'),
            ('ix_shift_production_data_published_by', 'published_by'),
        ]:
            if not _has_index(inspector, 'shift_production_data', index_name):
                op.create_index(index_name, 'shift_production_data', [column_name], unique=False)

        if _has_unique(inspector, 'shift_production_data', 'uq_shift_production_key'):
            op.drop_constraint('uq_shift_production_key', 'shift_production_data', type_='unique')
        if not _has_index(inspector, 'shift_production_data', 'uq_shift_production_active_key'):
            op.create_index(
                'uq_shift_production_active_key',
                'shift_production_data',
                ['business_date', 'shift_config_id', 'workshop_id', 'equipment_id'],
                unique=True,
                postgresql_where=sa.text("data_status <> 'voided'"),
            )

    if _has_table(inspector, 'daily_reports'):
        add_columns = [
            ('text_summary', sa.Text()),
            ('generated_scope', sa.String(length=32)),
            ('output_mode', sa.String(length=16)),
        ]
        for name, coltype in add_columns:
            if not _has_column(inspector, 'daily_reports', name):
                op.add_column('daily_reports', sa.Column(name, coltype, nullable=True))

        op.execute(sa.text("UPDATE daily_reports SET generated_scope = 'confirmed_only' WHERE generated_scope IS NULL"))
        op.execute(sa.text("UPDATE daily_reports SET output_mode = 'both' WHERE output_mode IS NULL"))
        op.execute(sa.text("UPDATE daily_reports SET status = 'draft' WHERE status IN ('generated', 'completed')"))

        op.alter_column('daily_reports', 'generated_scope', existing_type=sa.String(length=32), nullable=False)
        op.alter_column('daily_reports', 'output_mode', existing_type=sa.String(length=16), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'daily_reports'):
        for column_name in ['output_mode', 'generated_scope', 'text_summary']:
            if _has_column(inspector, 'daily_reports', column_name):
                op.drop_column('daily_reports', column_name)

    if _has_table(inspector, 'shift_production_data'):
        if _has_index(inspector, 'shift_production_data', 'uq_shift_production_active_key'):
            op.drop_index('uq_shift_production_active_key', table_name='shift_production_data')
        if not _has_unique(inspector, 'shift_production_data', 'uq_shift_production_key'):
            op.create_unique_constraint(
                'uq_shift_production_key',
                'shift_production_data',
                ['business_date', 'shift_config_id', 'workshop_id', 'equipment_id'],
            )

        for index_name in [
            'ix_shift_production_data_superseded_by_id',
            'ix_shift_production_data_reviewed_by',
            'ix_shift_production_data_confirmed_by',
            'ix_shift_production_data_rejected_by',
            'ix_shift_production_data_voided_by',
            'ix_shift_production_data_published_by',
        ]:
            if _has_index(inspector, 'shift_production_data', index_name):
                op.drop_index(index_name, table_name='shift_production_data')

        for fk_name in [
            'fk_shift_production_data_superseded_by_id',
            'fk_shift_production_data_reviewed_by',
            'fk_shift_production_data_confirmed_by',
            'fk_shift_production_data_rejected_by',
            'fk_shift_production_data_voided_by',
            'fk_shift_production_data_published_by',
        ]:
            if _has_fk(inspector, 'shift_production_data', fk_name):
                op.drop_constraint(fk_name, 'shift_production_data', type_='foreignkey')

        for column_name in [
            'published_at',
            'published_by',
            'voided_reason',
            'voided_at',
            'voided_by',
            'rejected_reason',
            'rejected_at',
            'rejected_by',
            'confirmed_at',
            'confirmed_by',
            'reviewed_at',
            'reviewed_by',
            'superseded_by_id',
            'version_no',
        ]:
            if _has_column(inspector, 'shift_production_data', column_name):
                op.drop_column('shift_production_data', column_name)
