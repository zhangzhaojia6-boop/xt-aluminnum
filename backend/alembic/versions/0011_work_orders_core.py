"""work orders core foundation

Revision ID: 0011_work_orders_core
Revises: 0010_round12
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = '0011_work_orders_core'
down_revision = '0010_round12'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index['name'] for index in inspector.get_indexes(table_name)}


def _ensure_alembic_version_length(bind) -> None:
    inspector = sa.inspect(bind)
    if 'alembic_version' not in inspector.get_table_names():
        return
    version_columns = {
        column['name']: column
        for column in inspector.get_columns('alembic_version')
    }
    version_column = version_columns.get('version_num')
    if version_column is None:
        return
    current_length = getattr(version_column['type'], 'length', None)
    if current_length is not None and current_length >= 64:
        return
    op.execute('ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)')


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_alembic_version_length(bind)
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'work_orders'):
        op.create_table(
            'work_orders',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('tracking_card_no', sa.String(length=64), nullable=False),
            sa.Column('process_route_code', sa.String(length=32), nullable=False),
            sa.Column('alloy_grade', sa.String(length=64), nullable=True),
            sa.Column('contract_no', sa.String(length=64), nullable=True),
            sa.Column('customer_name', sa.String(length=128), nullable=True),
            sa.Column('contract_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('current_station', sa.String(length=64), nullable=True),
            sa.Column('previous_stage_output', sa.JSON(), nullable=True),
            sa.Column('overall_status', sa.String(length=16), nullable=False, server_default='created'),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
            sa.UniqueConstraint('tracking_card_no', name='uq_work_orders_tracking_card_no'),
        )
        for index_name, columns in {
            'ix_work_orders_id': ['id'],
            'ix_work_orders_tracking_card_no': ['tracking_card_no'],
            'ix_work_orders_process_route_code': ['process_route_code'],
            'ix_work_orders_overall_status': ['overall_status'],
            'ix_work_orders_created_by': ['created_by'],
        }.items():
            op.create_index(index_name, 'work_orders', columns, unique=False)

    if not _has_table(inspector, 'work_order_entries'):
        op.create_table(
            'work_order_entries',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('work_order_id', sa.Integer(), nullable=False),
            sa.Column('workshop_id', sa.Integer(), nullable=False),
            sa.Column('machine_id', sa.Integer(), nullable=True),
            sa.Column('shift_id', sa.Integer(), nullable=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('on_machine_time', sa.Time(), nullable=True),
            sa.Column('off_machine_time', sa.Time(), nullable=True),
            sa.Column('input_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('output_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('input_spec', sa.String(length=64), nullable=True),
            sa.Column('output_spec', sa.String(length=64), nullable=True),
            sa.Column('material_state', sa.String(length=64), nullable=True),
            sa.Column('scrap_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('spool_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('operator_notes', sa.Text(), nullable=True),
            sa.Column('verified_input_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('verified_output_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('weigher_user_id', sa.Integer(), nullable=True),
            sa.Column('weighed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('qc_grade', sa.String(length=64), nullable=True),
            sa.Column('qc_notes', sa.Text(), nullable=True),
            sa.Column('qc_user_id', sa.Integer(), nullable=True),
            sa.Column('qc_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('energy_kwh', sa.Numeric(14, 3), nullable=True),
            sa.Column('gas_m3', sa.Numeric(14, 3), nullable=True),
            sa.Column('yield_rate', sa.Numeric(8, 4), nullable=True),
            sa.Column('entry_type', sa.String(length=16), nullable=False, server_default='in_progress'),
            sa.Column('entry_status', sa.String(length=16), nullable=False, server_default='draft'),
            sa.Column('locked_fields', sa.JSON(), nullable=True),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id']),
            sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id']),
            sa.ForeignKeyConstraint(['machine_id'], ['equipment.id']),
            sa.ForeignKeyConstraint(['shift_id'], ['shift_configs.id']),
            sa.ForeignKeyConstraint(['weigher_user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['qc_user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        )
        for index_name, columns in {
            'ix_work_order_entries_id': ['id'],
            'ix_work_order_entries_work_order_id': ['work_order_id'],
            'ix_work_order_entries_workshop_id': ['workshop_id'],
            'ix_work_order_entries_machine_id': ['machine_id'],
            'ix_work_order_entries_shift_id': ['shift_id'],
            'ix_work_order_entries_business_date': ['business_date'],
            'ix_work_order_entries_entry_status': ['entry_status'],
            'ix_work_order_entries_weigher_user_id': ['weigher_user_id'],
            'ix_work_order_entries_qc_user_id': ['qc_user_id'],
            'ix_work_order_entries_created_by': ['created_by'],
            'ix_work_order_entries_work_order_workshop_date': ['work_order_id', 'workshop_id', 'business_date'],
        }.items():
            op.create_index(index_name, 'work_order_entries', columns, unique=False)

    if not _has_table(inspector, 'field_amendments'):
        op.create_table(
            'field_amendments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('table_name', sa.String(length=64), nullable=False),
            sa.Column('record_id', sa.Integer(), nullable=False),
            sa.Column('field_name', sa.String(length=64), nullable=False),
            sa.Column('old_value', sa.Text(), nullable=True),
            sa.Column('new_value', sa.Text(), nullable=True),
            sa.Column('reason', sa.Text(), nullable=False),
            sa.Column('requested_by', sa.Integer(), nullable=True),
            sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('approved_by', sa.Integer(), nullable=True),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='pending'),
            sa.ForeignKeyConstraint(['requested_by'], ['users.id']),
            sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        )
        for index_name, columns in {
            'ix_field_amendments_id': ['id'],
            'ix_field_amendments_table_name': ['table_name'],
            'ix_field_amendments_record_id': ['record_id'],
            'ix_field_amendments_requested_by': ['requested_by'],
            'ix_field_amendments_approved_by': ['approved_by'],
            'ix_field_amendments_status': ['status'],
            'ix_field_amendments_status_table': ['status', 'table_name'],
        }.items():
            op.create_index(index_name, 'field_amendments', columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'field_amendments'):
        for index_name in [
            'ix_field_amendments_status_table',
            'ix_field_amendments_status',
            'ix_field_amendments_approved_by',
            'ix_field_amendments_requested_by',
            'ix_field_amendments_record_id',
            'ix_field_amendments_table_name',
            'ix_field_amendments_id',
        ]:
            if _has_index(inspector, 'field_amendments', index_name):
                op.drop_index(index_name, table_name='field_amendments')
        op.drop_table('field_amendments')

    if _has_table(inspector, 'work_order_entries'):
        for index_name in [
            'ix_work_order_entries_work_order_workshop_date',
            'ix_work_order_entries_created_by',
            'ix_work_order_entries_qc_user_id',
            'ix_work_order_entries_weigher_user_id',
            'ix_work_order_entries_entry_status',
            'ix_work_order_entries_business_date',
            'ix_work_order_entries_shift_id',
            'ix_work_order_entries_machine_id',
            'ix_work_order_entries_workshop_id',
            'ix_work_order_entries_work_order_id',
            'ix_work_order_entries_id',
        ]:
            if _has_index(inspector, 'work_order_entries', index_name):
                op.drop_index(index_name, table_name='work_order_entries')
        op.drop_table('work_order_entries')

    if _has_table(inspector, 'work_orders'):
        for index_name in [
            'ix_work_orders_created_by',
            'ix_work_orders_overall_status',
            'ix_work_orders_process_route_code',
            'ix_work_orders_tracking_card_no',
            'ix_work_orders_id',
        ]:
            if _has_index(inspector, 'work_orders', index_name):
                op.drop_index(index_name, table_name='work_orders')
        op.drop_table('work_orders')
