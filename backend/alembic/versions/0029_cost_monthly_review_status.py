"""cost monthly review status

Revision ID: 0029_cost_monthly_review_status
Revises: 0028_cost_strategy_tables
Create Date: 2026-05-13 13:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0029_cost_monthly_review_status'
down_revision = '0028_cost_strategy_tables'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'cost_monthly_review_status'):
        return

    op.create_table(
        'cost_monthly_review_status',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('month', sa.String(7), nullable=False),
        sa.Column('workshop_code', sa.String(40), nullable=False),
        sa.Column('strategy_code', sa.String(80), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending_review'),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_by', sa.Integer(), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('close_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            'month',
            'workshop_code',
            'strategy_code',
            name='uq_cost_monthly_review_status_version',
        ),
    )
    op.create_index('ix_cost_monthly_review_status_month', 'cost_monthly_review_status', ['month'])
    op.create_index('ix_cost_monthly_review_status_workshop', 'cost_monthly_review_status', ['workshop_code'])
    op.create_index('ix_cost_monthly_review_status_strategy', 'cost_monthly_review_status', ['strategy_code'])
    op.create_index('ix_cost_monthly_review_status_status', 'cost_monthly_review_status', ['status'])


def downgrade() -> None:
    op.drop_table('cost_monthly_review_status')
