"""persistent realtime events

Revision ID: 0016_realtime_events_persistent
Revises: 0015_write_isolation_and_audit_meta
Create Date: 2026-03-28 17:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0016_realtime_events_persistent'
down_revision = '0015_write_isolation_and_audit_meta'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'realtime_events',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('workshop_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_realtime_events_created_at', 'realtime_events', ['created_at'], unique=False)
    op.create_index('ix_realtime_events_event_type', 'realtime_events', ['event_type'], unique=False)
    op.create_index('ix_realtime_events_workshop_id', 'realtime_events', ['workshop_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_realtime_events_workshop_id', table_name='realtime_events')
    op.drop_index('ix_realtime_events_event_type', table_name='realtime_events')
    op.drop_index('ix_realtime_events_created_at', table_name='realtime_events')
    op.drop_table('realtime_events')
