"""add ai assistant state

Revision ID: 0023_ai_assistant_state
Revises: 0022_factory_command_projection
Create Date: 2026-05-02 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0023_ai_assistant_state'
down_revision = '0022_factory_command_projection'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=64), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('scope_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id'),
    )
    op.create_index('ix_ai_conversations_id', 'ai_conversations', ['id'], unique=False)
    op.create_index('ix_ai_conversations_public_id', 'ai_conversations', ['public_id'], unique=True)
    op.create_index('ix_ai_conversations_owner_user_id', 'ai_conversations', ['owner_user_id'], unique=False)

    op.create_table(
        'ai_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('ai_conversations.id'), nullable=True),
        sa.Column('conversation_public_id', sa.String(length=64), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_messages_id', 'ai_messages', ['id'], unique=False)
    op.create_index('ix_ai_messages_conversation_id', 'ai_messages', ['conversation_id'], unique=False)
    op.create_index('ix_ai_messages_conversation_public_id', 'ai_messages', ['conversation_public_id'], unique=False)

    op.create_table(
        'ai_context_packs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=True),
        sa.Column('intent', sa.String(length=64), nullable=False),
        sa.Column('scope_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('source_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_context_packs_id', 'ai_context_packs', ['id'], unique=False)
    op.create_index('ix_ai_context_packs_owner_user_id', 'ai_context_packs', ['owner_user_id'], unique=False)
    op.create_index('ix_ai_context_packs_intent', 'ai_context_packs', ['intent'], unique=False)
    op.create_index('ix_ai_context_packs_source_hash', 'ai_context_packs', ['source_hash'], unique=False)

    op.create_table(
        'ai_briefing_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=64), nullable=False),
        sa.Column('briefing_type', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='info'),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('scope_key', sa.String(length=128), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('follow_up_status', sa.String(length=32), nullable=False, server_default='none'),
        sa.Column('delivery_suppressed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id'),
    )
    op.create_index('ix_ai_briefing_events_id', 'ai_briefing_events', ['id'], unique=False)
    op.create_index('ix_ai_briefing_events_public_id', 'ai_briefing_events', ['public_id'], unique=True)
    op.create_index('ix_ai_briefing_events_briefing_type', 'ai_briefing_events', ['briefing_type'], unique=False)
    op.create_index('ix_ai_briefing_events_severity', 'ai_briefing_events', ['severity'], unique=False)
    op.create_index('ix_ai_briefing_events_scope_key', 'ai_briefing_events', ['scope_key'], unique=False)

    op.create_table(
        'ai_watchlist_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=64), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=True),
        sa.Column('watch_type', sa.String(length=64), nullable=False),
        sa.Column('scope_key', sa.String(length=128), nullable=False),
        sa.Column('trigger_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('quiet_hours', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('frequency', sa.String(length=32), nullable=False, server_default='hourly'),
        sa.Column('channels', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id'),
    )
    op.create_index('ix_ai_watchlist_items_id', 'ai_watchlist_items', ['id'], unique=False)
    op.create_index('ix_ai_watchlist_items_public_id', 'ai_watchlist_items', ['public_id'], unique=True)
    op.create_index('ix_ai_watchlist_items_owner_user_id', 'ai_watchlist_items', ['owner_user_id'], unique=False)
    op.create_index('ix_ai_watchlist_items_watch_type', 'ai_watchlist_items', ['watch_type'], unique=False)
    op.create_index('ix_ai_watchlist_items_scope_key', 'ai_watchlist_items', ['scope_key'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ai_watchlist_items_scope_key', table_name='ai_watchlist_items')
    op.drop_index('ix_ai_watchlist_items_watch_type', table_name='ai_watchlist_items')
    op.drop_index('ix_ai_watchlist_items_owner_user_id', table_name='ai_watchlist_items')
    op.drop_index('ix_ai_watchlist_items_public_id', table_name='ai_watchlist_items')
    op.drop_index('ix_ai_watchlist_items_id', table_name='ai_watchlist_items')
    op.drop_table('ai_watchlist_items')

    op.drop_index('ix_ai_briefing_events_scope_key', table_name='ai_briefing_events')
    op.drop_index('ix_ai_briefing_events_severity', table_name='ai_briefing_events')
    op.drop_index('ix_ai_briefing_events_briefing_type', table_name='ai_briefing_events')
    op.drop_index('ix_ai_briefing_events_public_id', table_name='ai_briefing_events')
    op.drop_index('ix_ai_briefing_events_id', table_name='ai_briefing_events')
    op.drop_table('ai_briefing_events')

    op.drop_index('ix_ai_context_packs_source_hash', table_name='ai_context_packs')
    op.drop_index('ix_ai_context_packs_intent', table_name='ai_context_packs')
    op.drop_index('ix_ai_context_packs_owner_user_id', table_name='ai_context_packs')
    op.drop_index('ix_ai_context_packs_id', table_name='ai_context_packs')
    op.drop_table('ai_context_packs')

    op.drop_index('ix_ai_messages_conversation_public_id', table_name='ai_messages')
    op.drop_index('ix_ai_messages_conversation_id', table_name='ai_messages')
    op.drop_index('ix_ai_messages_id', table_name='ai_messages')
    op.drop_table('ai_messages')

    op.drop_index('ix_ai_conversations_owner_user_id', table_name='ai_conversations')
    op.drop_index('ix_ai_conversations_public_id', table_name='ai_conversations')
    op.drop_index('ix_ai_conversations_id', table_name='ai_conversations')
    op.drop_table('ai_conversations')
