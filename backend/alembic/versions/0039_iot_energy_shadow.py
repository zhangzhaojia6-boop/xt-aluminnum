"""iot energy shadow

Revision ID: 0039_iot_energy_shadow
Revises: 0038_mes_terminal_bindings
Create Date: 2026-06-12 10:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0039_iot_energy_shadow'
down_revision = '0038_mes_terminal_bindings'
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'iot_energy_sync_runs'):
        op.create_table(
            'iot_energy_sync_runs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_system', sa.String(64), nullable=False, server_default='iot_meter'),
            sa.Column('status', sa.String(24), nullable=False, server_default='pending'),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('records_read', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('records_written', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('raw_payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_iot_energy_sync_runs_source_system', 'iot_energy_sync_runs', ['source_system'])
        op.create_index('ix_iot_energy_sync_runs_status', 'iot_energy_sync_runs', ['status'])

    if _has_table(inspector, 'iot_energy_snapshots'):
        return

    op.create_table(
        'iot_energy_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sync_run_id', sa.Integer(), sa.ForeignKey('iot_energy_sync_runs.id'), nullable=True),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=True),
        sa.Column('machine_id', sa.Integer(), sa.ForeignKey('equipment.id'), nullable=True),
        sa.Column('meter_code', sa.String(128), nullable=False),
        sa.Column('meter_name', sa.String(128), nullable=True),
        sa.Column('electricity_kwh', sa.Numeric(18, 4), nullable=True),
        sa.Column('gas_m3', sa.Numeric(18, 4), nullable=True),
        sa.Column('water_m3', sa.Numeric(18, 4), nullable=True),
        sa.Column('reading_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_system', sa.String(64), nullable=False, server_default='iot_meter'),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('source_system', 'meter_code', 'reading_at', name='uq_iot_energy_snapshot_meter_time'),
    )
    for column in ('sync_run_id', 'business_date', 'workshop_id', 'machine_id', 'meter_code', 'reading_at', 'source_system'):
        op.create_index(f'ix_iot_energy_snapshots_{column}', 'iot_energy_snapshots', [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'iot_energy_snapshots'):
        for column in ('sync_run_id', 'business_date', 'workshop_id', 'machine_id', 'meter_code', 'reading_at', 'source_system'):
            _safe_drop_index(f'ix_iot_energy_snapshots_{column}', 'iot_energy_snapshots')
        op.drop_table('iot_energy_snapshots')

    if _has_table(inspector, 'iot_energy_sync_runs'):
        _safe_drop_index('ix_iot_energy_sync_runs_source_system', 'iot_energy_sync_runs')
        _safe_drop_index('ix_iot_energy_sync_runs_status', 'iot_energy_sync_runs')
        op.drop_table('iot_energy_sync_runs')
