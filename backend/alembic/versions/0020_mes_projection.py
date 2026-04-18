"""add mes projection tables

Revision ID: 0020_mes_projection
Revises: 0019_workshop_template_configs
Create Date: 2026-04-11 06:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0020_mes_projection'
down_revision = '0019_workshop_template_configs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mes_coil_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('coil_id', sa.String(length=128), nullable=False),
        sa.Column('tracking_card_no', sa.String(length=64), nullable=False),
        sa.Column('qr_code', sa.String(length=128), nullable=True),
        sa.Column('batch_no', sa.String(length=128), nullable=True),
        sa.Column('contract_no', sa.String(length=64), nullable=True),
        sa.Column('workshop_code', sa.String(length=64), nullable=True),
        sa.Column('process_code', sa.String(length=64), nullable=True),
        sa.Column('machine_code', sa.String(length=64), nullable=True),
        sa.Column('shift_code', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('business_date', sa.Date(), nullable=True),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_from_mes_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('source_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('coil_id'),
    )
    op.create_index('ix_mes_coil_snapshots_id', 'mes_coil_snapshots', ['id'], unique=False)
    op.create_index('ix_mes_coil_snapshots_coil_id', 'mes_coil_snapshots', ['coil_id'], unique=True)
    op.create_index('ix_mes_coil_snapshots_tracking_card_no', 'mes_coil_snapshots', ['tracking_card_no'], unique=False)
    op.create_index('ix_mes_coil_snapshots_contract_no', 'mes_coil_snapshots', ['contract_no'], unique=False)
    op.create_index('ix_mes_coil_snapshots_workshop_code', 'mes_coil_snapshots', ['workshop_code'], unique=False)
    op.create_index('ix_mes_coil_snapshots_machine_code', 'mes_coil_snapshots', ['machine_code'], unique=False)
    op.create_index('ix_mes_coil_snapshots_shift_code', 'mes_coil_snapshots', ['shift_code'], unique=False)

    op.create_table(
        'mes_sync_cursors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cursor_key', sa.String(length=64), nullable=False),
        sa.Column('cursor_value', sa.Text(), nullable=True),
        sa.Column('window_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cursor_key'),
    )
    op.create_index('ix_mes_sync_cursors_id', 'mes_sync_cursors', ['id'], unique=False)
    op.create_index('ix_mes_sync_cursors_cursor_key', 'mes_sync_cursors', ['cursor_key'], unique=True)

    op.create_table(
        'mes_sync_run_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cursor_key', sa.String(length=64), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='running'),
        sa.Column('fetched_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('upserted_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('replayed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_cursor', sa.Text(), nullable=True),
        sa.Column('lag_seconds', sa.Numeric(18, 3), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mes_sync_run_logs_id', 'mes_sync_run_logs', ['id'], unique=False)
    op.create_index('ix_mes_sync_run_logs_cursor_key', 'mes_sync_run_logs', ['cursor_key'], unique=False)
    op.create_index('ix_mes_sync_run_logs_status', 'mes_sync_run_logs', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_mes_sync_run_logs_status', table_name='mes_sync_run_logs')
    op.drop_index('ix_mes_sync_run_logs_cursor_key', table_name='mes_sync_run_logs')
    op.drop_index('ix_mes_sync_run_logs_id', table_name='mes_sync_run_logs')
    op.drop_table('mes_sync_run_logs')

    op.drop_index('ix_mes_sync_cursors_cursor_key', table_name='mes_sync_cursors')
    op.drop_index('ix_mes_sync_cursors_id', table_name='mes_sync_cursors')
    op.drop_table('mes_sync_cursors')

    op.drop_index('ix_mes_coil_snapshots_shift_code', table_name='mes_coil_snapshots')
    op.drop_index('ix_mes_coil_snapshots_machine_code', table_name='mes_coil_snapshots')
    op.drop_index('ix_mes_coil_snapshots_workshop_code', table_name='mes_coil_snapshots')
    op.drop_index('ix_mes_coil_snapshots_contract_no', table_name='mes_coil_snapshots')
    op.drop_index('ix_mes_coil_snapshots_tracking_card_no', table_name='mes_coil_snapshots')
    op.drop_index('ix_mes_coil_snapshots_coil_id', table_name='mes_coil_snapshots')
    op.drop_index('ix_mes_coil_snapshots_id', table_name='mes_coil_snapshots')
    op.drop_table('mes_coil_snapshots')

