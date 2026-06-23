"""report history period knowledge

Revision ID: 0051_report_history_period_knowledge
Revises: 0050_daily_fact_bundle
Create Date: 2026-06-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


json_object_type = sa.JSON().with_variant(JSONB, 'postgresql')


revision = '0051_report_history_period_knowledge'
down_revision = '0050_daily_fact_bundle'
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index['name'] == index_name for index in inspector.get_indexes(table_name))


def _has_unique_constraint(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    try:
        return any(
            constraint.get('name') == constraint_name for constraint in inspector.get_unique_constraints(table_name)
        )
    except NotImplementedError:
        return False


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def _create_index(inspector: sa.Inspector, table_name: str, column_name: str, *, unique: bool = False) -> None:
    index_name = f'ix_{table_name}_{column_name}'
    if not _has_index(inspector, table_name, index_name):
        op.create_index(index_name, table_name, [column_name], unique=unique)


def _create_unique_constraint(
    inspector: sa.Inspector, table_name: str, constraint_name: str, columns: tuple[str, ...]
) -> None:
    if _has_unique_constraint(inspector, table_name, constraint_name):
        return
    if op.get_bind().dialect.name == 'sqlite':
        return
    op.create_unique_constraint(constraint_name, table_name, list(columns))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, 'daily_report_history_records'):
        op.create_table(
            'daily_report_history_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('report_type', sa.String(length=32), nullable=False, server_default='daily'),
            sa.Column('business_date', sa.Date(), nullable=True),
            sa.Column('period_type', sa.String(length=32), nullable=True),
            sa.Column('period_start', sa.Date(), nullable=True),
            sa.Column('period_end', sa.Date(), nullable=True),
            sa.Column('source_snapshot_id', sa.Integer(), sa.ForeignKey('daily_fact_bundle_snapshots.id'), nullable=True),
            sa.Column('source_run_id', sa.Integer(), sa.ForeignKey('daily_fact_bundle_runs.id'), nullable=True),
            sa.Column('report_text', sa.Text(), nullable=False),
            sa.Column('report_payload', json_object_type, nullable=False),
            sa.Column('source_summary', json_object_type, nullable=False),
            sa.Column('facts_hash', sa.String(length=64), nullable=False),
            sa.Column('text_hash', sa.String(length=64), nullable=False),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('trace_id', sa.String(length=128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)
    for column_name in (
        'report_type',
        'business_date',
        'period_type',
        'period_start',
        'period_end',
        'source_snapshot_id',
        'source_run_id',
        'facts_hash',
        'text_hash',
        'created_by_id',
        'trace_id',
    ):
        _create_index(inspector, 'daily_report_history_records', column_name)

    if not _has_table(inspector, 'operation_period_snapshots'):
        op.create_table(
            'operation_period_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('period_type', sa.String(length=32), nullable=False),
            sa.Column('period_start', sa.Date(), nullable=False),
            sa.Column('period_end', sa.Date(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='ready'),
            sa.Column('cumulative_metrics', json_object_type, nullable=False),
            sa.Column('analysis_payload', json_object_type, nullable=False),
            sa.Column('source_daily_report_ids', json_object_type, nullable=False),
            sa.Column('source_snapshot_ids', json_object_type, nullable=False),
            sa.Column('missing_dates', json_object_type, nullable=False),
            sa.Column('payload_hash', sa.String(length=64), nullable=False),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('trace_id', sa.String(length=128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('period_type', 'period_start', 'period_end', name='uq_operation_period_snapshot_period'),
        )
        inspector = sa.inspect(bind)
    _create_unique_constraint(
        inspector,
        'operation_period_snapshots',
        'uq_operation_period_snapshot_period',
        ('period_type', 'period_start', 'period_end'),
    )
    for column_name in (
        'period_type',
        'period_start',
        'period_end',
        'status',
        'payload_hash',
        'created_by_id',
        'trace_id',
    ):
        _create_index(inspector, 'operation_period_snapshots', column_name)

    if not _has_table(inspector, 'hermes_professional_knowledge_entries'):
        op.create_table(
            'hermes_professional_knowledge_entries',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('domain', sa.String(length=64), nullable=False),
            sa.Column('topic', sa.String(length=128), nullable=False),
            sa.Column('knowledge_type', sa.String(length=64), nullable=False),
            sa.Column('source_type', sa.String(length=64), nullable=False),
            sa.Column('source_ref', sa.String(length=256), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('structured_payload', json_object_type, nullable=False),
            sa.Column('confidence', sa.Integer(), nullable=False, server_default='80'),
            sa.Column('valid_from', sa.Date(), nullable=True),
            sa.Column('valid_to', sa.Date(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('trace_id', sa.String(length=128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'domain',
                'topic',
                'knowledge_type',
                'source_ref',
                name='uq_hermes_professional_knowledge_source',
            ),
        )
        inspector = sa.inspect(bind)
    _create_unique_constraint(
        inspector,
        'hermes_professional_knowledge_entries',
        'uq_hermes_professional_knowledge_source',
        ('domain', 'topic', 'knowledge_type', 'source_ref'),
    )
    for column_name in (
        'domain',
        'topic',
        'knowledge_type',
        'source_type',
        'source_ref',
        'valid_from',
        'valid_to',
        'status',
        'created_by_id',
        'trace_id',
    ):
        _create_index(inspector, 'hermes_professional_knowledge_entries', column_name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'hermes_professional_knowledge_entries'):
        for column_name in (
            'domain',
            'topic',
            'knowledge_type',
            'source_type',
            'source_ref',
            'valid_from',
            'valid_to',
            'status',
            'created_by_id',
            'trace_id',
        ):
            _safe_drop_index(f'ix_hermes_professional_knowledge_entries_{column_name}', 'hermes_professional_knowledge_entries')
        op.drop_table('hermes_professional_knowledge_entries')
        inspector = sa.inspect(bind)

    if _has_table(inspector, 'operation_period_snapshots'):
        for column_name in (
            'period_type',
            'period_start',
            'period_end',
            'status',
            'payload_hash',
            'created_by_id',
            'trace_id',
        ):
            _safe_drop_index(f'ix_operation_period_snapshots_{column_name}', 'operation_period_snapshots')
        op.drop_table('operation_period_snapshots')
        inspector = sa.inspect(bind)

    if _has_table(inspector, 'daily_report_history_records'):
        for column_name in (
            'report_type',
            'business_date',
            'period_type',
            'period_start',
            'period_end',
            'source_snapshot_id',
            'source_run_id',
            'facts_hash',
            'text_hash',
            'created_by_id',
            'trace_id',
        ):
            _safe_drop_index(f'ix_daily_report_history_records_{column_name}', 'daily_report_history_records')
        op.drop_table('daily_report_history_records')
