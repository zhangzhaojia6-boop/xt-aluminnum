"""agent communication outbox

Revision ID: 0040_agent_communication_outbox
Revises: 0039_iot_energy_shadow
Create Date: 2026-06-13 17:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0040_agent_communication_outbox'
down_revision = '0039_iot_energy_shadow'
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

    if not _has_table(inspector, 'agent_profiles'):
        op.create_table(
            'agent_profiles',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('code', sa.String(64), nullable=False),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('agent_type', sa.String(64), nullable=False, server_default='reporting'),
            sa.Column('scope_type', sa.String(32), nullable=False, server_default='factory'),
            sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=True),
            sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('config_payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('code', 'agent_type', 'scope_type', 'workshop_id', 'team_id', 'is_active'):
            op.create_index(f'ix_agent_profiles_{column}', 'agent_profiles', [column], unique=(column == 'code'))

    if not _has_table(inspector, 'communication_channels'):
        op.create_table(
            'communication_channels',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('channel_type', sa.String(32), nullable=False),
            sa.Column('channel_key', sa.String(256), nullable=False),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('target_type', sa.String(32), nullable=False),
            sa.Column('target_key', sa.String(128), nullable=True),
            sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=True),
            sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
            sa.Column('dry_run', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('secret_ref', sa.String(256), nullable=True),
            sa.Column('metadata_payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('channel_type', 'channel_key', name='uq_communication_channel_type_key'),
        )
        for column in ('channel_type', 'channel_key', 'target_type', 'target_key', 'workshop_id', 'team_id', 'dry_run', 'is_active'):
            op.create_index(f'ix_communication_channels_{column}', 'communication_channels', [column])

    if not _has_table(inspector, 'agent_channel_bindings'):
        op.create_table(
            'agent_channel_bindings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('agent_profile_id', sa.Integer(), sa.ForeignKey('agent_profiles.id'), nullable=False),
            sa.Column('channel_id', sa.Integer(), sa.ForeignKey('communication_channels.id'), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('min_severity', sa.String(32), nullable=False, server_default='info'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('agent_profile_id', 'channel_id', name='uq_agent_channel_binding'),
        )
        for column in ('agent_profile_id', 'channel_id', 'is_active'):
            op.create_index(f'ix_agent_channel_bindings_{column}', 'agent_channel_bindings', [column])

    if not _has_table(inspector, 'agent_events'):
        op.create_table(
            'agent_events',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('event_type', sa.String(64), nullable=False),
            sa.Column('severity', sa.String(32), nullable=False, server_default='info'),
            sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
            sa.Column('scope_type', sa.String(32), nullable=False, server_default='factory'),
            sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=True),
            sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
            sa.Column('source_type', sa.String(64), nullable=False, server_default='system'),
            sa.Column('source_ref', sa.String(128), nullable=True),
            sa.Column('business_date', sa.Date(), nullable=True),
            sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('event_type', 'severity', 'status', 'scope_type', 'workshop_id', 'team_id', 'source_type', 'source_ref', 'business_date', 'occurred_at'):
            op.create_index(f'ix_agent_events_{column}', 'agent_events', [column])

    if not _has_table(inspector, 'agent_outbox_messages'):
        op.create_table(
            'agent_outbox_messages',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('dispatch_key', sa.String(128), nullable=False),
            sa.Column('agent_profile_id', sa.Integer(), sa.ForeignKey('agent_profiles.id'), nullable=True),
            sa.Column('channel_id', sa.Integer(), sa.ForeignKey('communication_channels.id'), nullable=True),
            sa.Column('event_id', sa.Integer(), sa.ForeignKey('agent_events.id'), nullable=True),
            sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
            sa.Column('message_type', sa.String(32), nullable=False, server_default='markdown'),
            sa.Column('title', sa.String(128), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('business_date', sa.Date(), nullable=True),
            sa.Column('source_summary', sa.String(128), nullable=True),
            sa.Column('trace_id', sa.String(128), nullable=False),
            sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('payload', sa.JSON(), nullable=True),
            sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_agent_outbox_messages_dispatch_key', 'agent_outbox_messages', ['dispatch_key'], unique=True)
        for column in ('agent_profile_id', 'channel_id', 'event_id', 'status', 'business_date', 'trace_id'):
            op.create_index(f'ix_agent_outbox_messages_{column}', 'agent_outbox_messages', [column])

    if not _has_table(inspector, 'external_message_logs'):
        op.create_table(
            'external_message_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('outbox_message_id', sa.Integer(), sa.ForeignKey('agent_outbox_messages.id'), nullable=True),
            sa.Column('channel_type', sa.String(32), nullable=False),
            sa.Column('channel_key', sa.String(256), nullable=True),
            sa.Column('status', sa.String(32), nullable=False),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('provider_message_id', sa.String(128), nullable=True),
            sa.Column('response_payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('outbox_message_id', 'channel_type', 'channel_key', 'status'):
            op.create_index(f'ix_external_message_logs_{column}', 'external_message_logs', [column])

    if not _has_table(inspector, 'multimodal_evidence'):
        op.create_table(
            'multimodal_evidence',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('evidence_type', sa.String(32), nullable=False),
            sa.Column('source_channel_id', sa.Integer(), sa.ForeignKey('communication_channels.id'), nullable=True),
            sa.Column('source_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('event_id', sa.Integer(), sa.ForeignKey('agent_events.id'), nullable=True),
            sa.Column('file_uri', sa.String(512), nullable=True),
            sa.Column('recognized_text', sa.Text(), nullable=True),
            sa.Column('confirmation_status', sa.String(32), nullable=False, server_default='machine_only'),
            sa.Column('payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('evidence_type', 'source_channel_id', 'source_user_id', 'event_id', 'confirmation_status'):
            op.create_index(f'ix_multimodal_evidence_{column}', 'multimodal_evidence', [column])

    if not _has_table(inspector, 'agent_operation_approvals'):
        op.create_table(
            'agent_operation_approvals',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('operation_type', sa.String(64), nullable=False),
            sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
            sa.Column('requester_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('approver_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('channel_id', sa.Integer(), sa.ForeignKey('communication_channels.id'), nullable=True),
            sa.Column('preview_payload', sa.JSON(), nullable=True),
            sa.Column('result_payload', sa.JSON(), nullable=True),
            sa.Column('trace_id', sa.String(128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for column in ('operation_type', 'status', 'requester_user_id', 'approver_user_id', 'channel_id', 'trace_id'):
            op.create_index(f'ix_agent_operation_approvals_{column}', 'agent_operation_approvals', [column])

    if not _has_table(inspector, 'agent_rate_limits'):
        op.create_table(
            'agent_rate_limits',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('scope_key', sa.String(128), nullable=False),
            sa.Column('event_key', sa.String(128), nullable=False),
            sa.Column('window_started_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('window_expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('hit_count', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('scope_key', 'event_key', name='uq_agent_rate_limit_scope_event'),
        )
        for column in ('scope_key', 'event_key', 'window_expires_at'):
            op.create_index(f'ix_agent_rate_limits_{column}', 'agent_rate_limits', [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, columns in (
        ('agent_rate_limits', ('scope_key', 'event_key', 'window_expires_at')),
        ('agent_operation_approvals', ('operation_type', 'status', 'requester_user_id', 'approver_user_id', 'channel_id', 'trace_id')),
        ('multimodal_evidence', ('evidence_type', 'source_channel_id', 'source_user_id', 'event_id', 'confirmation_status')),
        ('external_message_logs', ('outbox_message_id', 'channel_type', 'channel_key', 'status')),
        ('agent_outbox_messages', ('dispatch_key', 'agent_profile_id', 'channel_id', 'event_id', 'status', 'business_date', 'trace_id')),
        ('agent_events', ('event_type', 'severity', 'status', 'scope_type', 'workshop_id', 'team_id', 'source_type', 'source_ref', 'business_date', 'occurred_at')),
        ('agent_channel_bindings', ('agent_profile_id', 'channel_id', 'is_active')),
        ('communication_channels', ('channel_type', 'channel_key', 'target_type', 'target_key', 'workshop_id', 'team_id', 'dry_run', 'is_active')),
        ('agent_profiles', ('code', 'agent_type', 'scope_type', 'workshop_id', 'team_id', 'is_active')),
    ):
        if not _has_table(inspector, table_name):
            continue
        for column in columns:
            _safe_drop_index(f'ix_{table_name}_{column}', table_name)
        op.drop_table(table_name)
