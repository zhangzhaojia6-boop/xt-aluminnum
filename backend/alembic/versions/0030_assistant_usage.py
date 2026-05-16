"""assistant usage tracking

Revision ID: 0030_assistant_usage
Revises: 0029_cost_monthly_review_status
Create Date: 2026-05-16 21:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0030_assistant_usage'
down_revision = '0029_cost_monthly_review_status'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, 'assistant_usage'):
        return

    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')
    op.create_table(
        'assistant_usage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(64), nullable=False, server_default='query'),
        sa.Column('model', sa.String(128), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('raw_usage', json_type, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_assistant_usage_user_id', 'assistant_usage', ['user_id'])
    op.create_index('ix_assistant_usage_created_at', 'assistant_usage', ['created_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, 'assistant_usage'):
        return
    op.drop_index('ix_assistant_usage_created_at', table_name='assistant_usage')
    op.drop_index('ix_assistant_usage_user_id', table_name='assistant_usage')
    op.drop_table('assistant_usage')
