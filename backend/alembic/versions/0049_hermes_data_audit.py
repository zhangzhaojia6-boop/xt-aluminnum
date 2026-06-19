"""hermes data audit persistence

Revision ID: 0049_hermes_data_audit
Revises: 0048_hermes_rag_memory
Create Date: 2026-06-19 22:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = '0049_hermes_data_audit'
down_revision = '0048_hermes_rag_memory'
branch_labels = None
depends_on = None


json_object_type = sa.JSON().with_variant(JSONB, 'postgresql')


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index['name'] == index_name for index in inspector.get_indexes(table_name))


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def _create_index(inspector: sa.Inspector, table_name: str, column_name: str, *, unique: bool = False) -> None:
    index_name = f'ix_{table_name}_{column_name}'
    if not _has_index(inspector, table_name, index_name):
        op.create_index(index_name, table_name, [column_name], unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'hermes_data_audit_runs'):
        op.create_table(
            'hermes_data_audit_runs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('run_key', sa.String(length=128), nullable=False),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
            sa.Column('source_status', json_object_type, nullable=False),
            sa.Column('source_errors', json_object_type, nullable=False),
            sa.Column('mes_snapshot', json_object_type, nullable=False),
            sa.Column('hub_snapshot', json_object_type, nullable=False),
            sa.Column('output_skill_snapshot', json_object_type, nullable=False),
            sa.Column('diffs', json_object_type, nullable=False),
            sa.Column('suggested_actions', json_object_type, nullable=False),
            sa.Column('match_rate', sa.Numeric(8, 4), nullable=True),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)
        for column_name, unique in (
            ('run_key', True),
            ('business_date', False),
            ('status', False),
            ('created_by_id', False),
        ):
            _create_index(inspector, 'hermes_data_audit_runs', column_name, unique=unique)

    if not _has_table(inspector, 'hermes_correction_actions'):
        op.create_table(
            'hermes_correction_actions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('audit_run_id', sa.Integer(), sa.ForeignKey('hermes_data_audit_runs.id'), nullable=False),
            sa.Column('idempotency_key', sa.String(length=128), nullable=False),
            sa.Column('action_type', sa.String(length=64), nullable=False),
            sa.Column('risk_level', sa.String(length=16), nullable=False, server_default='low'),
            sa.Column('target_table', sa.String(length=128), nullable=False),
            sa.Column('target_key', sa.String(length=256), nullable=False),
            sa.Column('field_name', sa.String(length=128), nullable=True),
            sa.Column('before_value', json_object_type, nullable=True),
            sa.Column('after_value', json_object_type, nullable=True),
            sa.Column('evidence', json_object_type, nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
            sa.Column('applied_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('rollback_status', sa.String(length=32), nullable=False, server_default='not_requested'),
            sa.Column('rollback_payload', json_object_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)
        for column_name, unique in (
            ('audit_run_id', False),
            ('idempotency_key', True),
        ):
            _create_index(inspector, 'hermes_correction_actions', column_name, unique=unique)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'hermes_correction_actions'):
        for column_name in ('audit_run_id', 'idempotency_key'):
            _safe_drop_index(f'ix_hermes_correction_actions_{column_name}', 'hermes_correction_actions')
        op.drop_table('hermes_correction_actions')

    if _has_table(inspector, 'hermes_data_audit_runs'):
        for column_name in ('run_key', 'business_date', 'status', 'created_by_id'):
            _safe_drop_index(f'ix_hermes_data_audit_runs_{column_name}', 'hermes_data_audit_runs')
        op.drop_table('hermes_data_audit_runs')
