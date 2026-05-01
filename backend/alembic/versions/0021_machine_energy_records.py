"""add machine_energy_records table

Revision ID: 0021_machine_energy_records
Revises: 0020_mes_projection
Create Date: 2026-05-01 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0021_machine_energy_records'
down_revision = '0020_mes_projection'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'machine_energy_records',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('shift_report_id', sa.Integer(), sa.ForeignKey('mobile_shift_reports.id'), nullable=False, index=True),
        sa.Column('machine_id', sa.Integer(), sa.ForeignKey('equipment.id'), nullable=True, index=True),
        sa.Column('machine_code', sa.String(64), nullable=True),
        sa.Column('machine_name', sa.String(128), nullable=True),
        sa.Column('energy_kwh', sa.Numeric(14, 3), nullable=True),
        sa.Column('gas_m3', sa.Numeric(14, 3), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('machine_energy_records')
