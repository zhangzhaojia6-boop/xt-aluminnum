"""add owner scope to ai briefing events

Revision ID: 0024_ai_briefing_owner_scope
Revises: 0023_ai_assistant_state
Create Date: 2026-05-03 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0024_ai_briefing_owner_scope'
down_revision = '0023_ai_assistant_state'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ai_briefing_events', sa.Column('owner_user_id', sa.Integer(), nullable=True))
    op.create_index('ix_ai_briefing_events_owner_user_id', 'ai_briefing_events', ['owner_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ai_briefing_events_owner_user_id', table_name='ai_briefing_events')
    op.drop_column('ai_briefing_events', 'owner_user_id')
