"""add procurement suppliers

Revision ID: 0059_procurement_suppliers
Revises: 0058_procurement
Create Date: 2026-11-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0059_procurement_suppliers'
down_revision = '0058_procurement'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'procurement_suppliers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('normalized_name', sa.String(128), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('contact', sa.String(128), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('normalized_name', name='uq_procurement_supplier_name'),
    )
    op.create_index('ix_procurement_suppliers_status', 'procurement_suppliers', ['status'])


def downgrade() -> None:
    op.drop_index('ix_procurement_suppliers_status', table_name='procurement_suppliers')
    op.drop_table('procurement_suppliers')
