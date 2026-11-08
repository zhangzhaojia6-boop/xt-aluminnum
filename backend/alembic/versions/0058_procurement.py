"""add procurement workflow tables

Revision ID: 0058_procurement
Revises: 0057_imported_daily_metric_facts
Create Date: 2026-11-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = '0058_procurement'
down_revision = '0057_imported_daily_metric_facts'
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(JSONB, 'postgresql')


def upgrade() -> None:
    op.create_table(
        'procurement_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(32), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'role', name='uq_procurement_assignment'),
    )
    op.create_index('ix_procurement_assignments_user_id', 'procurement_assignments', ['user_id'])
    op.create_index('ix_procurement_assignments_role', 'procurement_assignments', ['role'])

    op.create_table(
        'procurement_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_no', sa.String(32), nullable=True, unique=True),
        sa.Column('trace_id', sa.String(64), nullable=False),
        sa.Column('requester_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=True),
        sa.Column('material_name', sa.String(128), nullable=False),
        sa.Column('specification', sa.String(128), nullable=True),
        sa.Column('unit', sa.String(16), nullable=False),
        sa.Column('category', sa.String(16), nullable=False),
        sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
        sa.Column('purchase_quantity', sa.Numeric(14, 3), nullable=True),
        sa.Column('estimated_unit_price', sa.Numeric(14, 2), nullable=False),
        sa.Column('needed_by', sa.Date(), nullable=True),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('is_emergency', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('backfill_due_on', sa.Date(), nullable=True),
        sa.Column('needs_quality_check', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('supplier', sa.String(128), nullable=True),
        sa.Column('approved_amount', sa.Numeric(14, 2), nullable=True),
        sa.Column('paid_amount', sa.Numeric(14, 2), nullable=True),
        sa.Column('current_step', sa.String(32), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='open'),
        sa.Column('step_entered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('details', json_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ('trace_id', 'requester_id', 'workshop_id', 'material_name', 'supplier', 'current_step', 'status'):
        op.create_index(f'ix_procurement_requests_{column}', 'procurement_requests', [column])

    op.create_table(
        'procurement_quotes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('procurement_requests.id'), nullable=False),
        sa.Column('round_no', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('supplier', sa.String(128), nullable=False),
        sa.Column('unit_price', sa.Numeric(14, 2), nullable=False),
        sa.Column('is_selected', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_procurement_quotes_request_id', 'procurement_quotes', ['request_id'])

    op.create_table(
        'procurement_documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('procurement_requests.id'), nullable=False),
        sa.Column('doc_type', sa.String(32), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('stored_path', sa.String(512), nullable=False),
        sa.Column('content_type', sa.String(128), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_procurement_documents_request_id', 'procurement_documents', ['request_id'])
    op.create_index('ix_procurement_documents_doc_type', 'procurement_documents', ['doc_type'])

    op.create_table(
        'procurement_step_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('procurement_requests.id'), nullable=False),
        sa.Column('step', sa.String(32), nullable=False),
        sa.Column('action', sa.String(32), nullable=False),
        sa.Column('to_step', sa.String(32), nullable=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('actor_name', sa.String(64), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('payload', json_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_procurement_step_logs_request_id', 'procurement_step_logs', ['request_id'])


def downgrade() -> None:
    op.drop_table('procurement_step_logs')
    op.drop_table('procurement_documents')
    op.drop_table('procurement_quotes')
    op.drop_table('procurement_requests')
    op.drop_table('procurement_assignments')
