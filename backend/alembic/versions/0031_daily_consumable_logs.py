"""daily consumable logs

Revision ID: 0031_daily_consumable_logs
Revises: 0030_assistant_usage
Create Date: 2026-05-26 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0031_daily_consumable_logs'
down_revision = '0030_assistant_usage'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, 'daily_consumable_logs'):
        return

    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')
    op.create_table(
        'daily_consumable_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workshop_id', sa.Integer(), nullable=False),
        sa.Column('workshop_type', sa.String(64), nullable=True),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('payload', json_type, nullable=True),
        sa.Column('note', sa.String(512), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id']),
        sa.UniqueConstraint('workshop_id', 'business_date', name='uq_daily_consumable_workshop_date'),
    )
    op.create_index('ix_daily_consumable_logs_workshop_id', 'daily_consumable_logs', ['workshop_id'])
    op.create_index('ix_daily_consumable_logs_business_date', 'daily_consumable_logs', ['business_date'])
    op.create_index('ix_daily_consumable_logs_workshop_type', 'daily_consumable_logs', ['workshop_type'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, 'daily_consumable_logs'):
        return
    op.drop_index('ix_daily_consumable_logs_workshop_type', table_name='daily_consumable_logs')
    op.drop_index('ix_daily_consumable_logs_business_date', table_name='daily_consumable_logs')
    op.drop_index('ix_daily_consumable_logs_workshop_id', table_name='daily_consumable_logs')
    op.drop_table('daily_consumable_logs')
