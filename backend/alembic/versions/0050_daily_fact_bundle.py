"""daily fact bundle

Revision ID: 0050_daily_fact_bundle
Revises: 0049_hermes_data_audit
Create Date: 2026-06-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


json_object_type = sa.JSON().with_variant(JSONB, 'postgresql')


revision = '0050_daily_fact_bundle'
down_revision = '0049_hermes_data_audit'
branch_labels = None
depends_on = None


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

    if not _has_table(inspector, 'daily_fact_bundle_runs'):
        op.create_table(
            'daily_fact_bundle_runs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('run_key', sa.String(length=160), nullable=False),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('requested_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('trace_id', sa.String(length=128), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='partial'),
            sa.Column('source_status', json_object_type, nullable=False),
            sa.Column('missing_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('conflict_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('confidence', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)
    for column_name, unique in (
        ('run_key', True),
        ('business_date', False),
        ('requested_by_id', False),
        ('trace_id', False),
        ('status', False),
    ):
        _create_index(inspector, 'daily_fact_bundle_runs', column_name, unique=unique)

    if not _has_table(inspector, 'daily_fact_bundle_snapshots'):
        op.create_table(
            'daily_fact_bundle_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('run_id', sa.Integer(), sa.ForeignKey('daily_fact_bundle_runs.id'), nullable=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('snapshot_reason', sa.String(length=64), nullable=False),
            sa.Column('facts', json_object_type, nullable=False),
            sa.Column('sources', json_object_type, nullable=False),
            sa.Column('conflicts', json_object_type, nullable=False),
            sa.Column('adopted_values', json_object_type, nullable=False),
            sa.Column('correction_refs', json_object_type, nullable=False),
            sa.Column('dingtalk_refs', json_object_type, nullable=False),
            sa.Column('output_skill_alignment', json_object_type, nullable=False),
            sa.Column('payload_hash', sa.String(length=64), nullable=False),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('trace_id', sa.String(length=128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)
    for column_name in (
        'run_id',
        'business_date',
        'snapshot_reason',
        'payload_hash',
        'created_by_id',
        'trace_id',
    ):
        _create_index(inspector, 'daily_fact_bundle_snapshots', column_name)

    if not _has_table(inspector, 'daily_fact_corrections'):
        op.create_table(
            'daily_fact_corrections',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('field_name', sa.String(length=128), nullable=False),
            sa.Column('value_payload', json_object_type, nullable=False),
            sa.Column('unit', sa.String(length=32), nullable=True),
            sa.Column('source_text', sa.Text(), nullable=True),
            sa.Column('before_value', json_object_type, nullable=True),
            sa.Column('reason', sa.Text(), nullable=False),
            sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('trace_id', sa.String(length=128), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)
    for column_name in (
        'business_date',
        'field_name',
        'actor_user_id',
        'trace_id',
        'status',
    ):
        _create_index(inspector, 'daily_fact_corrections', column_name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'daily_fact_corrections'):
        for column_name in ('business_date', 'field_name', 'actor_user_id', 'trace_id', 'status'):
            _safe_drop_index(f'ix_daily_fact_corrections_{column_name}', 'daily_fact_corrections')
        op.drop_table('daily_fact_corrections')
        inspector = sa.inspect(bind)

    if _has_table(inspector, 'daily_fact_bundle_snapshots'):
        for column_name in (
            'run_id',
            'business_date',
            'snapshot_reason',
            'payload_hash',
            'created_by_id',
            'trace_id',
        ):
            _safe_drop_index(f'ix_daily_fact_bundle_snapshots_{column_name}', 'daily_fact_bundle_snapshots')
        op.drop_table('daily_fact_bundle_snapshots')
        inspector = sa.inspect(bind)

    if _has_table(inspector, 'daily_fact_bundle_runs'):
        for column_name in ('run_key', 'business_date', 'requested_by_id', 'trace_id', 'status'):
            _safe_drop_index(f'ix_daily_fact_bundle_runs_{column_name}', 'daily_fact_bundle_runs')
        op.drop_table('daily_fact_bundle_runs')
