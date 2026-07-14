"""atomic DingTalk inbound receipts

Revision ID: 0054_dingtalk_inbound_receipts
Revises: 0053_daily_fact_snapshot_key
Create Date: 2026-07-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0054_dingtalk_inbound_receipts'
down_revision = '0053_daily_fact_snapshot_key'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'dingtalk_inbound_receipts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('dedupe_key', sa.String(length=64), nullable=False),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('group_id', sa.String(length=256), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='evidence_pending'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_dingtalk_inbound_receipts_dedupe_key', 'dingtalk_inbound_receipts', ['dedupe_key'], unique=True)
    op.create_index('ix_dingtalk_inbound_receipts_channel', 'dingtalk_inbound_receipts', ['channel'])
    op.create_index('ix_dingtalk_inbound_receipts_group_id', 'dingtalk_inbound_receipts', ['group_id'])
    op.create_index('ix_dingtalk_inbound_receipts_trace_id', 'dingtalk_inbound_receipts', ['trace_id'])
    op.create_index('ix_dingtalk_inbound_receipts_status', 'dingtalk_inbound_receipts', ['status'])


def downgrade() -> None:
    op.drop_index('ix_dingtalk_inbound_receipts_status', table_name='dingtalk_inbound_receipts')
    op.drop_index('ix_dingtalk_inbound_receipts_trace_id', table_name='dingtalk_inbound_receipts')
    op.drop_index('ix_dingtalk_inbound_receipts_group_id', table_name='dingtalk_inbound_receipts')
    op.drop_index('ix_dingtalk_inbound_receipts_channel', table_name='dingtalk_inbound_receipts')
    op.drop_index('ix_dingtalk_inbound_receipts_dedupe_key', table_name='dingtalk_inbound_receipts')
    op.drop_table('dingtalk_inbound_receipts')
