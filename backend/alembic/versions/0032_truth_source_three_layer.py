"""truth source three-layer schema

Revision ID: 0032_truth_source_three_layer
Revises: 0031_daily_consumable_logs
Create Date: 2026-05-26 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0032_truth_source_three_layer'
down_revision = '0031_daily_consumable_logs'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return any(col['name'] == column_name for col in inspector.get_columns(table_name))


def _safe_drop_index(index_name: str, table_name: str) -> None:
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')

    if not _has_table(inspector, 'machine_energy_daily_compare'):
        op.create_table(
            'machine_energy_daily_compare',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('machine_id', sa.Integer(), nullable=False),
            sa.Column('workshop_id', sa.Integer(), nullable=True),
            sa.Column('gas_per_ton_today', sa.Numeric(14, 3), nullable=True),
            sa.Column('gas_per_ton_yesterday', sa.Numeric(14, 3), nullable=True),
            sa.Column('gas_per_ton_target', sa.Numeric(14, 3), nullable=True),
            sa.Column('compare_arrow', sa.String(8), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['machine_id'], ['equipment.id']),
            sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id']),
            sa.UniqueConstraint('business_date', 'machine_id', name='uq_machine_energy_compare_date_machine'),
        )
        op.create_index('ix_machine_energy_compare_business_date', 'machine_energy_daily_compare', ['business_date'])
        op.create_index('ix_machine_energy_compare_machine_id', 'machine_energy_daily_compare', ['machine_id'])
        op.create_index('ix_machine_energy_compare_workshop_id', 'machine_energy_daily_compare', ['workshop_id'])

    if not _has_column(inspector, 'mobile_shift_reports', 'attendance_payload'):
        op.add_column(
            'mobile_shift_reports',
            sa.Column('attendance_payload', json_type, nullable=True),
        )

    if not _has_table(inspector, 'quality_yield_daily'):
        op.create_table(
            'quality_yield_daily',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_code', sa.String(64), nullable=False),
            sa.Column('yield_daily', sa.Numeric(8, 4), nullable=True),
            sa.Column('yield_monthly', sa.Numeric(8, 4), nullable=True),
            sa.Column('yield_target_m', sa.Numeric(8, 4), nullable=True),
            sa.Column('yield_target_p_casting', sa.Numeric(8, 4), nullable=True),
            sa.Column('yield_target_p_hot_roll', sa.Numeric(8, 4), nullable=True),
            sa.Column('yield_overall_company', sa.Numeric(8, 4), nullable=True),
            sa.Column('variance_arrow', sa.String(8), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('business_date', 'workshop_code', name='uq_quality_yield_date_workshop'),
        )
        op.create_index('ix_quality_yield_business_date', 'quality_yield_daily', ['business_date'])
        op.create_index('ix_quality_yield_workshop_code', 'quality_yield_daily', ['workshop_code'])

    if not _has_table(inspector, 'production_plan_daily'):
        op.create_table(
            'production_plan_daily',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_code', sa.String(64), nullable=False),
            sa.Column('input_daily', sa.Numeric(14, 3), nullable=True),
            sa.Column('output_daily', sa.Numeric(14, 3), nullable=True),
            sa.Column('input_monthly_target', sa.Numeric(14, 3), nullable=True),
            sa.Column('output_monthly_target', sa.Numeric(14, 3), nullable=True),
            sa.Column('output_quarterly_target', sa.Numeric(14, 3), nullable=True),
            sa.Column('output_yearly_target', sa.Numeric(14, 3), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('business_date', 'workshop_code', name='uq_production_plan_date_workshop'),
        )
        op.create_index('ix_production_plan_business_date', 'production_plan_daily', ['business_date'])
        op.create_index('ix_production_plan_workshop_code', 'production_plan_daily', ['workshop_code'])

    if not _has_table(inspector, 'alloy_spec_breakdown'):
        op.create_table(
            'alloy_spec_breakdown',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_code', sa.String(64), nullable=False),
            sa.Column('alloy_grade', sa.String(64), nullable=False),
            sa.Column('output_spec', sa.String(128), nullable=True),
            sa.Column('weight_tons', sa.Numeric(14, 3), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_alloy_spec_business_date', 'alloy_spec_breakdown', ['business_date'])
        op.create_index('ix_alloy_spec_workshop_code', 'alloy_spec_breakdown', ['workshop_code'])
        op.create_index('ix_alloy_spec_alloy_grade', 'alloy_spec_breakdown', ['alloy_grade'])

    if not _has_table(inspector, 'shipment_outflow_record'):
        op.create_table(
            'shipment_outflow_record',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('batch_no', sa.String(64), nullable=True),
            sa.Column('source_workshop_code', sa.String(64), nullable=True),
            sa.Column('alloy_grade', sa.String(64), nullable=True),
            sa.Column('output_spec', sa.String(128), nullable=True),
            sa.Column('outflow_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('outflow_destination', sa.String(64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_shipment_outflow_business_date', 'shipment_outflow_record', ['business_date'])
        op.create_index('ix_shipment_outflow_batch_no', 'shipment_outflow_record', ['batch_no'])
        op.create_index('ix_shipment_outflow_source_workshop_code', 'shipment_outflow_record', ['source_workshop_code'])

    if not _has_table(inspector, 'recovery_daily'):
        op.create_table(
            'recovery_daily',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False, unique=True),
            sa.Column('recovery_today', sa.Numeric(14, 3), nullable=True),
            sa.Column('recovery_monthly', sa.Numeric(14, 3), nullable=True),
            sa.Column('recovery_yearly', sa.Numeric(14, 3), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_recovery_daily_business_date', 'recovery_daily', ['business_date'])

    if not _has_table(inspector, 'overhaul_daily'):
        op.create_table(
            'overhaul_daily',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False, unique=True),
            sa.Column('overhaul_today', sa.Numeric(14, 3), nullable=True),
            sa.Column('overhaul_monthly', sa.Numeric(14, 3), nullable=True),
            sa.Column('overhaul_yearly', sa.Numeric(14, 3), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_overhaul_daily_business_date', 'overhaul_daily', ['business_date'])

    if not _has_table(inspector, 'quality_issue_log'):
        op.create_table(
            'quality_issue_log',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_id', sa.Integer(), nullable=True),
            sa.Column('shift_report_id', sa.Integer(), nullable=True),
            sa.Column('tracking_card_no', sa.String(64), nullable=True),
            sa.Column('quality_issue_type', sa.String(32), nullable=True),
            sa.Column('quality_issue_desc', sa.Text(), nullable=True),
            sa.Column('quality_photo_path', sa.String(512), nullable=True),
            sa.Column('reported_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['workshop_id'], ['workshops.id']),
            sa.ForeignKeyConstraint(['shift_report_id'], ['mobile_shift_reports.id']),
            sa.ForeignKeyConstraint(['reported_by'], ['users.id']),
        )
        op.create_index('ix_quality_issue_business_date', 'quality_issue_log', ['business_date'])
        op.create_index('ix_quality_issue_tracking_card_no', 'quality_issue_log', ['tracking_card_no'])
        op.create_index('ix_quality_issue_workshop_id', 'quality_issue_log', ['workshop_id'])
        op.create_index('ix_quality_issue_shift_report_id', 'quality_issue_log', ['shift_report_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, 'quality_issue_log'):
        _safe_drop_index('ix_quality_issue_shift_report_id', 'quality_issue_log')
        _safe_drop_index('ix_quality_issue_workshop_id', 'quality_issue_log')
        _safe_drop_index('ix_quality_issue_tracking_card_no', 'quality_issue_log')
        _safe_drop_index('ix_quality_issue_business_date', 'quality_issue_log')
        op.drop_table('quality_issue_log')

    if _has_table(inspector, 'overhaul_daily'):
        _safe_drop_index('ix_overhaul_daily_business_date', 'overhaul_daily')
        op.drop_table('overhaul_daily')

    if _has_table(inspector, 'recovery_daily'):
        _safe_drop_index('ix_recovery_daily_business_date', 'recovery_daily')
        op.drop_table('recovery_daily')

    if _has_table(inspector, 'shipment_outflow_record'):
        _safe_drop_index('ix_shipment_outflow_source_workshop_code', 'shipment_outflow_record')
        _safe_drop_index('ix_shipment_outflow_batch_no', 'shipment_outflow_record')
        _safe_drop_index('ix_shipment_outflow_business_date', 'shipment_outflow_record')
        op.drop_table('shipment_outflow_record')

    if _has_table(inspector, 'alloy_spec_breakdown'):
        _safe_drop_index('ix_alloy_spec_alloy_grade', 'alloy_spec_breakdown')
        _safe_drop_index('ix_alloy_spec_workshop_code', 'alloy_spec_breakdown')
        _safe_drop_index('ix_alloy_spec_business_date', 'alloy_spec_breakdown')
        op.drop_table('alloy_spec_breakdown')

    if _has_table(inspector, 'production_plan_daily'):
        _safe_drop_index('ix_production_plan_workshop_code', 'production_plan_daily')
        _safe_drop_index('ix_production_plan_business_date', 'production_plan_daily')
        op.drop_table('production_plan_daily')

    if _has_table(inspector, 'quality_yield_daily'):
        _safe_drop_index('ix_quality_yield_workshop_code', 'quality_yield_daily')
        _safe_drop_index('ix_quality_yield_business_date', 'quality_yield_daily')
        op.drop_table('quality_yield_daily')

    if _has_column(inspector, 'mobile_shift_reports', 'attendance_payload'):
        op.drop_column('mobile_shift_reports', 'attendance_payload')

    if _has_table(inspector, 'machine_energy_daily_compare'):
        _safe_drop_index('ix_machine_energy_compare_workshop_id', 'machine_energy_daily_compare')
        _safe_drop_index('ix_machine_energy_compare_machine_id', 'machine_energy_daily_compare')
        _safe_drop_index('ix_machine_energy_compare_business_date', 'machine_energy_daily_compare')
        op.drop_table('machine_energy_daily_compare')
