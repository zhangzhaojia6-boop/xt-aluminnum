"""add factory command projection fields

Revision ID: 0022_factory_command_projection
Revises: 0021_machine_energy_records
Create Date: 2026-05-02 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0022_factory_command_projection'
down_revision = '0021_machine_energy_records'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        sa.Column('mes_product_id', sa.String(length=64), nullable=True),
        sa.Column('material_code', sa.String(length=64), nullable=True),
        sa.Column('customer_alias', sa.String(length=128), nullable=True),
        sa.Column('alloy_grade', sa.String(length=64), nullable=True),
        sa.Column('material_state', sa.String(length=64), nullable=True),
        sa.Column('spec_thickness', sa.Numeric(12, 4), nullable=True),
        sa.Column('spec_width', sa.Numeric(12, 4), nullable=True),
        sa.Column('spec_length', sa.String(length=64), nullable=True),
        sa.Column('spec_display', sa.String(length=128), nullable=True),
        sa.Column('feeding_weight', sa.Numeric(18, 4), nullable=True),
        sa.Column('material_weight', sa.Numeric(18, 4), nullable=True),
        sa.Column('gross_weight', sa.Numeric(18, 4), nullable=True),
        sa.Column('net_weight', sa.Numeric(18, 4), nullable=True),
        sa.Column('current_workshop', sa.String(length=128), nullable=True),
        sa.Column('current_process', sa.String(length=128), nullable=True),
        sa.Column('current_process_sort', sa.Integer(), nullable=True),
        sa.Column('next_workshop', sa.String(length=128), nullable=True),
        sa.Column('next_process', sa.String(length=128), nullable=True),
        sa.Column('next_process_sort', sa.Integer(), nullable=True),
        sa.Column('process_route_text', sa.Text(), nullable=True),
        sa.Column('print_process_route_text', sa.Text(), nullable=True),
        sa.Column('status_name', sa.String(length=128), nullable=True),
        sa.Column('card_status_name', sa.String(length=128), nullable=True),
        sa.Column('production_status', sa.String(length=64), nullable=True),
        sa.Column('delay_hours', sa.Numeric(12, 3), nullable=True),
        sa.Column('in_stock_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('allocation_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen_from_mes_at', sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column('mes_coil_snapshots', column)

    for name in (
        'mes_product_id',
        'material_code',
        'alloy_grade',
        'current_workshop',
        'current_process',
        'next_workshop',
        'next_process',
        'last_seen_from_mes_at',
    ):
        op.create_index(f'ix_mes_coil_snapshots_{name}', 'mes_coil_snapshots', [name], unique=False)

    op.create_table(
        'mes_machine_line_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('line_code', sa.String(length=128), nullable=False),
        sa.Column('line_name', sa.String(length=128), nullable=False),
        sa.Column('workshop_name', sa.String(length=128), nullable=True),
        sa.Column('slot_no', sa.Integer(), nullable=True),
        sa.Column('last_seen_from_mes_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('line_code'),
    )
    op.create_index('ix_mes_machine_line_snapshots_id', 'mes_machine_line_snapshots', ['id'], unique=False)
    op.create_index('ix_mes_machine_line_snapshots_line_code', 'mes_machine_line_snapshots', ['line_code'], unique=True)
    op.create_index('ix_mes_machine_line_snapshots_workshop_name', 'mes_machine_line_snapshots', ['workshop_name'], unique=False)
    op.create_index('ix_mes_machine_line_snapshots_slot_no', 'mes_machine_line_snapshots', ['slot_no'], unique=False)
    op.create_index(
        'ix_mes_machine_line_snapshots_last_seen_from_mes_at',
        'mes_machine_line_snapshots',
        ['last_seen_from_mes_at'],
        unique=False,
    )

    op.create_table(
        'coil_flow_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('coil_key', sa.String(length=128), nullable=False),
        sa.Column('tracking_card_no', sa.String(length=64), nullable=False),
        sa.Column('previous_workshop', sa.String(length=128), nullable=True),
        sa.Column('previous_process', sa.String(length=128), nullable=True),
        sa.Column('current_workshop', sa.String(length=128), nullable=True),
        sa.Column('current_process', sa.String(length=128), nullable=True),
        sa.Column('next_workshop', sa.String(length=128), nullable=True),
        sa.Column('next_process', sa.String(length=128), nullable=True),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_coil_flow_events_id', 'coil_flow_events', ['id'], unique=False)
    op.create_index('ix_coil_flow_events_coil_key', 'coil_flow_events', ['coil_key'], unique=False)
    op.create_index('ix_coil_flow_events_tracking_card_no', 'coil_flow_events', ['tracking_card_no'], unique=False)
    op.create_index('ix_coil_flow_events_current_workshop', 'coil_flow_events', ['current_workshop'], unique=False)
    op.create_index('ix_coil_flow_events_current_process', 'coil_flow_events', ['current_process'], unique=False)
    op.create_index('ix_coil_flow_events_event_time', 'coil_flow_events', ['event_time'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_coil_flow_events_event_time', table_name='coil_flow_events')
    op.drop_index('ix_coil_flow_events_current_process', table_name='coil_flow_events')
    op.drop_index('ix_coil_flow_events_current_workshop', table_name='coil_flow_events')
    op.drop_index('ix_coil_flow_events_tracking_card_no', table_name='coil_flow_events')
    op.drop_index('ix_coil_flow_events_coil_key', table_name='coil_flow_events')
    op.drop_index('ix_coil_flow_events_id', table_name='coil_flow_events')
    op.drop_table('coil_flow_events')

    op.drop_index('ix_mes_machine_line_snapshots_last_seen_from_mes_at', table_name='mes_machine_line_snapshots')
    op.drop_index('ix_mes_machine_line_snapshots_slot_no', table_name='mes_machine_line_snapshots')
    op.drop_index('ix_mes_machine_line_snapshots_workshop_name', table_name='mes_machine_line_snapshots')
    op.drop_index('ix_mes_machine_line_snapshots_line_code', table_name='mes_machine_line_snapshots')
    op.drop_index('ix_mes_machine_line_snapshots_id', table_name='mes_machine_line_snapshots')
    op.drop_table('mes_machine_line_snapshots')

    for name in (
        'last_seen_from_mes_at',
        'next_process',
        'next_workshop',
        'current_process',
        'current_workshop',
        'alloy_grade',
        'material_code',
        'mes_product_id',
    ):
        op.drop_index(f'ix_mes_coil_snapshots_{name}', table_name='mes_coil_snapshots')

    for name in (
        'last_seen_from_mes_at',
        'allocation_date',
        'delivery_date',
        'in_stock_date',
        'delay_hours',
        'production_status',
        'card_status_name',
        'status_name',
        'print_process_route_text',
        'process_route_text',
        'next_process_sort',
        'next_process',
        'next_workshop',
        'current_process_sort',
        'current_process',
        'current_workshop',
        'net_weight',
        'gross_weight',
        'material_weight',
        'feeding_weight',
        'spec_display',
        'spec_length',
        'spec_width',
        'spec_thickness',
        'material_state',
        'alloy_grade',
        'customer_alias',
        'material_code',
        'mes_product_id',
    ):
        op.drop_column('mes_coil_snapshots', name)
