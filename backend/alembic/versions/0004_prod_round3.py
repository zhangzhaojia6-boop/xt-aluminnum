"""round3 production/report data center

Revision ID: 0004_prod_round3
Revises: 0003_clock_upd_at
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


revision = '0004_prod_round3'
down_revision = '0003_clock_upd_at'
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
        if _has_column(inspector, 'shift_production_data', 'shift_id') and not _has_column(
            inspector, 'shift_production_data', 'shift_config_id'
        ):
            op.alter_column('shift_production_data', 'shift_id', new_column_name='shift_config_id')

        add_columns = [
            ('input_weight', sa.Numeric(14, 3)),
            ('output_weight', sa.Numeric(14, 3)),
            ('qualified_weight', sa.Numeric(14, 3)),
            ('scrap_weight', sa.Numeric(14, 3)),
            ('planned_headcount', sa.Integer()),
            ('actual_headcount', sa.Integer()),
            ('downtime_minutes', sa.Integer()),
            ('downtime_reason', sa.Text()),
            ('issue_count', sa.Integer()),
            ('electricity_kwh', sa.Numeric(14, 3)),
            ('data_source', sa.String(32)),
            ('data_status', sa.String(16)),
            ('notes', sa.Text()),
        ]
        for name, coltype in add_columns:
            if not _has_column(inspector, 'shift_production_data', name):
                op.add_column('shift_production_data', sa.Column(name, coltype, nullable=True))

        if _has_column(inspector, 'shift_production_data', 'actual_qty') and _has_column(
            inspector, 'shift_production_data', 'output_weight'
        ):
            op.execute(sa.text('UPDATE shift_production_data SET output_weight = actual_qty WHERE output_weight IS NULL'))
        if _has_column(inspector, 'shift_production_data', 'scrap_qty') and _has_column(
            inspector, 'shift_production_data', 'scrap_weight'
        ):
            op.execute(sa.text('UPDATE shift_production_data SET scrap_weight = scrap_qty WHERE scrap_weight IS NULL'))
        if _has_column(inspector, 'shift_production_data', 'planned_qty') and _has_column(
            inspector, 'shift_production_data', 'input_weight'
        ):
            op.execute(sa.text('UPDATE shift_production_data SET input_weight = planned_qty WHERE input_weight IS NULL'))

        op.execute(sa.text("UPDATE shift_production_data SET downtime_minutes = 0 WHERE downtime_minutes IS NULL"))
        op.execute(sa.text("UPDATE shift_production_data SET issue_count = 0 WHERE issue_count IS NULL"))
        op.execute(sa.text("UPDATE shift_production_data SET data_source = 'import' WHERE data_source IS NULL"))
        op.execute(sa.text("UPDATE shift_production_data SET data_status = 'pending' WHERE data_status IS NULL"))

        op.alter_column('shift_production_data', 'downtime_minutes', existing_type=sa.Integer(), nullable=False)
        op.alter_column('shift_production_data', 'issue_count', existing_type=sa.Integer(), nullable=False)
        op.alter_column('shift_production_data', 'data_source', existing_type=sa.String(length=32), nullable=False)
        op.alter_column('shift_production_data', 'data_status', existing_type=sa.String(length=16), nullable=False)

        if _has_unique(inspector, 'shift_production_data', 'uq_prod_equipment_date_shift'):
            op.drop_constraint('uq_prod_equipment_date_shift', 'shift_production_data', type_='unique')
        if not _has_unique(inspector, 'shift_production_data', 'uq_shift_production_key'):
            op.create_unique_constraint(
                'uq_shift_production_key',
                'shift_production_data',
                ['business_date', 'shift_config_id', 'workshop_id', 'equipment_id'],
            )

        if not _has_index(inspector, 'shift_production_data', 'ix_shift_production_data_data_status'):
            op.create_index('ix_shift_production_data_data_status', 'shift_production_data', ['data_status'], unique=False)
        if not _has_index(inspector, 'shift_production_data', 'ix_shift_production_data_shift_config_id'):
            op.create_index(
                'ix_shift_production_data_shift_config_id',
                'shift_production_data',
                ['shift_config_id'],
                unique=False,
            )

    if _has_table(inspector, 'production_exceptions'):
        if _has_column(inspector, 'production_exceptions', 'description') and not _has_column(
            inspector, 'production_exceptions', 'exception_desc'
        ):
            op.alter_column('production_exceptions', 'description', new_column_name='exception_desc')

        add_columns = [
            ('production_data_id', sa.Integer()),
            ('team_id', sa.Integer()),
            ('shift_config_id', sa.Integer()),
            ('severity', sa.String(16)),
            ('resolved_by', sa.Integer()),
            ('resolved_at', sa.DateTime(timezone=True)),
        ]
        for name, coltype in add_columns:
            if not _has_column(inspector, 'production_exceptions', name):
                op.add_column('production_exceptions', sa.Column(name, coltype, nullable=True))

        op.execute(sa.text("UPDATE production_exceptions SET exception_desc = '' WHERE exception_desc IS NULL"))
        op.execute(sa.text("UPDATE production_exceptions SET severity = 'warning' WHERE severity IS NULL"))
        op.execute(sa.text("UPDATE production_exceptions SET status = 'open' WHERE status IS NULL"))

        op.alter_column('production_exceptions', 'exception_desc', existing_type=sa.String(length=256), type_=sa.Text(), nullable=False)
        op.alter_column('production_exceptions', 'severity', existing_type=sa.String(length=16), nullable=False)
        op.alter_column('production_exceptions', 'status', existing_type=sa.String(length=16), nullable=False)

        if not _has_fk(inspector, 'production_exceptions', 'fk_production_exceptions_production_data_id'):
            op.create_foreign_key(
                'fk_production_exceptions_production_data_id',
                'production_exceptions',
                'shift_production_data',
                ['production_data_id'],
                ['id'],
            )
        if not _has_fk(inspector, 'production_exceptions', 'fk_production_exceptions_team_id'):
            op.create_foreign_key(
                'fk_production_exceptions_team_id',
                'production_exceptions',
                'teams',
                ['team_id'],
                ['id'],
            )
        if not _has_fk(inspector, 'production_exceptions', 'fk_production_exceptions_shift_config_id'):
            op.create_foreign_key(
                'fk_production_exceptions_shift_config_id',
                'production_exceptions',
                'shift_configs',
                ['shift_config_id'],
                ['id'],
            )
        if not _has_fk(inspector, 'production_exceptions', 'fk_production_exceptions_resolved_by'):
            op.create_foreign_key(
                'fk_production_exceptions_resolved_by',
                'production_exceptions',
                'users',
                ['resolved_by'],
                ['id'],
            )

        if not _has_index(inspector, 'production_exceptions', 'ix_production_exceptions_status'):
            op.create_index('ix_production_exceptions_status', 'production_exceptions', ['status'], unique=False)
        if not _has_index(inspector, 'production_exceptions', 'ix_production_exceptions_production_data_id'):
            op.create_index(
                'ix_production_exceptions_production_data_id',
                'production_exceptions',
                ['production_data_id'],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'production_exceptions'):
        if _has_index(inspector, 'production_exceptions', 'ix_production_exceptions_production_data_id'):
            op.drop_index('ix_production_exceptions_production_data_id', table_name='production_exceptions')
        if _has_index(inspector, 'production_exceptions', 'ix_production_exceptions_status'):
            op.drop_index('ix_production_exceptions_status', table_name='production_exceptions')

    if _has_table(inspector, 'shift_production_data'):
        if _has_index(inspector, 'shift_production_data', 'ix_shift_production_data_shift_config_id'):
            op.drop_index('ix_shift_production_data_shift_config_id', table_name='shift_production_data')
        if _has_index(inspector, 'shift_production_data', 'ix_shift_production_data_data_status'):
            op.drop_index('ix_shift_production_data_data_status', table_name='shift_production_data')
