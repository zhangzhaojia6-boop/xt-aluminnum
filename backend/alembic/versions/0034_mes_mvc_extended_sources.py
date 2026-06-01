"""mes mvc extended source tables

Revision ID: 0034_mes_mvc_extended_sources
Revises: 0033_fix_machine_operator_roles
Create Date: 2026-06-01 16:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0034_mes_mvc_extended_sources'
down_revision = '0033_fix_machine_operator_roles'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')

    if not _has_table(inspector, 'mes_workshop_process_records'):
        op.create_table(
            'mes_workshop_process_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_id', sa.String(128), nullable=False, unique=True),
            sa.Column('source_path', sa.String(128), nullable=False),
            sa.Column('batch_no', sa.String(128), nullable=True),
            sa.Column('customer_alias', sa.String(128), nullable=True),
            sa.Column('workshop_name', sa.String(128), nullable=True),
            sa.Column('process_name', sa.String(128), nullable=True),
            sa.Column('worker_name', sa.String(128), nullable=True),
            sa.Column('device_name', sa.String(128), nullable=True),
            sa.Column('input_weight_kg', sa.Numeric(18, 4), nullable=True),
            sa.Column('input_weight_tons', sa.Numeric(18, 4), nullable=True),
            sa.Column('output_weight_kg', sa.Numeric(18, 4), nullable=True),
            sa.Column('output_weight_tons', sa.Numeric(18, 4), nullable=True),
            sa.Column('yield_rate', sa.Numeric(10, 4), nullable=True),
            sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
            sa.Column('business_date', sa.Date(), nullable=True),
            sa.Column('last_seen_from_mes_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('source_payload', json_type, nullable=True),
            *_timestamps(),
        )
        for column in ('source_id', 'batch_no', 'customer_alias', 'workshop_name', 'process_name', 'worker_name', 'device_name', 'end_time', 'business_date', 'last_seen_from_mes_at'):
            op.create_index(f'ix_mes_workshop_process_records_{column}', 'mes_workshop_process_records', [column])

    if not _has_table(inspector, 'mes_stock_records'):
        op.create_table(
            'mes_stock_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_id', sa.String(128), nullable=False, unique=True),
            sa.Column('source_path', sa.String(128), nullable=False),
            sa.Column('batch_no', sa.String(128), nullable=True),
            sa.Column('contract_no', sa.String(64), nullable=True),
            sa.Column('customer_alias', sa.String(128), nullable=True),
            sa.Column('net_weight_kg', sa.Numeric(18, 4), nullable=True),
            sa.Column('net_weight_tons', sa.Numeric(18, 4), nullable=True),
            sa.Column('gross_weight_kg', sa.Numeric(18, 4), nullable=True),
            sa.Column('gross_weight_tons', sa.Numeric(18, 4), nullable=True),
            sa.Column('in_stock_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('business_date', sa.Date(), nullable=True),
            sa.Column('status_name', sa.String(128), nullable=True),
            sa.Column('last_seen_from_mes_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('source_payload', json_type, nullable=True),
            *_timestamps(),
        )
        for column in ('source_id', 'batch_no', 'contract_no', 'customer_alias', 'in_stock_date', 'business_date', 'status_name', 'last_seen_from_mes_at'):
            op.create_index(f'ix_mes_stock_records_{column}', 'mes_stock_records', [column])

    if not _has_table(inspector, 'mes_material_records'):
        op.create_table(
            'mes_material_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_id', sa.String(128), nullable=False, unique=True),
            sa.Column('source_path', sa.String(128), nullable=False),
            sa.Column('material_code', sa.String(128), nullable=True),
            sa.Column('workshop_name', sa.String(128), nullable=True),
            sa.Column('line_name', sa.String(128), nullable=True),
            sa.Column('position_name', sa.String(128), nullable=True),
            sa.Column('alloy_grade', sa.String(64), nullable=True),
            sa.Column('spec_display', sa.String(128), nullable=True),
            sa.Column('weight_kg', sa.Numeric(18, 4), nullable=True),
            sa.Column('weight_tons', sa.Numeric(18, 4), nullable=True),
            sa.Column('production_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('business_date', sa.Date(), nullable=True),
            sa.Column('status_name', sa.String(128), nullable=True),
            sa.Column('last_seen_from_mes_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('source_payload', json_type, nullable=True),
            *_timestamps(),
        )
        for column in ('source_id', 'material_code', 'workshop_name', 'line_name', 'alloy_grade', 'production_date', 'business_date', 'status_name', 'last_seen_from_mes_at'):
            op.create_index(f'ix_mes_material_records_{column}', 'mes_material_records', [column])

    if not _has_table(inspector, 'mes_yield_records'):
        op.create_table(
            'mes_yield_records',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_id', sa.String(128), nullable=False, unique=True),
            sa.Column('source_path', sa.String(128), nullable=False),
            sa.Column('batch_no', sa.String(128), nullable=True),
            sa.Column('contract_no', sa.String(64), nullable=True),
            sa.Column('customer_alias', sa.String(128), nullable=True),
            sa.Column('contract_total_weight_tons', sa.Numeric(18, 4), nullable=True),
            sa.Column('feeding_weight_tons', sa.Numeric(18, 4), nullable=True),
            sa.Column('in_stock_net_weight_tons', sa.Numeric(18, 4), nullable=True),
            sa.Column('yield_rate', sa.Numeric(10, 4), nullable=True),
            sa.Column('report_time', sa.DateTime(timezone=True), nullable=True),
            sa.Column('business_date', sa.Date(), nullable=True),
            sa.Column('last_seen_from_mes_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('source_payload', json_type, nullable=True),
            *_timestamps(),
        )
        for column in ('source_id', 'batch_no', 'contract_no', 'customer_alias', 'report_time', 'business_date', 'last_seen_from_mes_at'):
            op.create_index(f'ix_mes_yield_records_{column}', 'mes_yield_records', [column])

    if not _has_table(inspector, 'mes_reference_items'):
        op.create_table(
            'mes_reference_items',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_type', sa.String(64), nullable=False),
            sa.Column('source_id', sa.String(128), nullable=False),
            sa.Column('source_path', sa.String(128), nullable=False),
            sa.Column('code', sa.String(128), nullable=True),
            sa.Column('name', sa.String(128), nullable=True),
            sa.Column('parent_id', sa.String(128), nullable=True),
            sa.Column('workshop_name', sa.String(128), nullable=True),
            sa.Column('status_name', sa.String(128), nullable=True),
            sa.Column('last_seen_from_mes_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('source_payload', json_type, nullable=True),
            *_timestamps(),
            sa.UniqueConstraint('source_type', 'source_id', name='uq_mes_reference_type_source'),
        )
        for column in ('source_type', 'source_id', 'code', 'name', 'parent_id', 'workshop_name', 'status_name', 'last_seen_from_mes_at'):
            op.create_index(f'ix_mes_reference_items_{column}', 'mes_reference_items', [column])

    if not _has_table(inspector, 'mes_wip_total_snapshots'):
        op.create_table(
            'mes_wip_total_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_id', sa.String(192), nullable=False, unique=True),
            sa.Column('workshop_name', sa.String(128), nullable=False),
            sa.Column('process_name', sa.String(128), nullable=True),
            sa.Column('doing_count', sa.Integer(), nullable=True),
            sa.Column('doing_weight_tons', sa.Numeric(18, 4), nullable=True),
            sa.Column('snapshot_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('source_payload', json_type, nullable=True),
            *_timestamps(),
        )
        for column in ('source_id', 'workshop_name', 'process_name', 'snapshot_at'):
            op.create_index(f'ix_mes_wip_total_snapshots_{column}', 'mes_wip_total_snapshots', [column])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name, columns in (
        ('mes_wip_total_snapshots', ('source_id', 'workshop_name', 'process_name', 'snapshot_at')),
        ('mes_reference_items', ('source_type', 'source_id', 'code', 'name', 'parent_id', 'workshop_name', 'status_name', 'last_seen_from_mes_at')),
        ('mes_yield_records', ('source_id', 'batch_no', 'contract_no', 'customer_alias', 'report_time', 'business_date', 'last_seen_from_mes_at')),
        ('mes_material_records', ('source_id', 'material_code', 'workshop_name', 'line_name', 'alloy_grade', 'production_date', 'business_date', 'status_name', 'last_seen_from_mes_at')),
        ('mes_stock_records', ('source_id', 'batch_no', 'contract_no', 'customer_alias', 'in_stock_date', 'business_date', 'status_name', 'last_seen_from_mes_at')),
        ('mes_workshop_process_records', ('source_id', 'batch_no', 'customer_alias', 'workshop_name', 'process_name', 'worker_name', 'device_name', 'end_time', 'business_date', 'last_seen_from_mes_at')),
    ):
        if _has_table(inspector, table_name):
            for column in columns:
                _safe_drop_index(f'ix_{table_name}_{column}', table_name)
            op.drop_table(table_name)
