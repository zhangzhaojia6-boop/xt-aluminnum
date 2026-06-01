"""mes daily wip snapshots

Revision ID: 0035_mes_daily_wip_snapshots
Revises: 0034_mes_mvc_extended_sources
Create Date: 2026-06-01 21:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0035_mes_daily_wip_snapshots'
down_revision = '0034_mes_mvc_extended_sources'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')
    if _has_table(inspector, 'mes_daily_wip_snapshots'):
        return

    op.create_table(
        'mes_daily_wip_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('workshop_name', sa.String(128), nullable=False),
        sa.Column('process_name', sa.String(128), nullable=False, server_default=''),
        sa.Column('coil_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('material_weight_tons', sa.Numeric(18, 4), nullable=True),
        sa.Column('feeding_weight_tons', sa.Numeric(18, 4), nullable=True),
        sa.Column('snapshot_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('source', sa.String(64), nullable=False, server_default='mes_coil_snapshot'),
        sa.Column('source_payload', json_type, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('business_date', 'workshop_name', 'process_name', 'source', name='uq_mes_daily_wip_snapshot_scope'),
    )
    for column in ('business_date', 'workshop_name', 'process_name', 'snapshot_at', 'source'):
        op.create_index(f'ix_mes_daily_wip_snapshots_{column}', 'mes_daily_wip_snapshots', [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, 'mes_daily_wip_snapshots'):
        return
    for column in ('business_date', 'workshop_name', 'process_name', 'snapshot_at', 'source'):
        _safe_drop_index(f'ix_mes_daily_wip_snapshots_{column}', 'mes_daily_wip_snapshots')
    op.drop_table('mes_daily_wip_snapshots')
