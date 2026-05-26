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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')

    # G1 machine_energy_daily_compare
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

    # G3 mobile_shift_reports.attendance_payload
    if not _has_column(inspector, 'mobile_shift_reports', 'attendance_payload'):
        op.add_column(
            'mobile_shift_reports',
            sa.Column('attendance_payload', json_type, nullable=True),
        )

    # G4 quality_yield_daily
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

    # G5a production_plan_daily
    if not _has_table(inspector, 'production_plan_daily'):
        op.create_table(
            'production_plan_daily',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_code', sa.String(64), nullable=False),
            sa.Column('input_daily', sa.Numeric(14, 3), nullable=True),
            sa.Column('input_monthly', sa.Numeric(14, 3), nullable=True),
            sa.Column('contract_today', sa.Numeric(14, 3), nullable=True),
            sa.Column('contract_total_remaining', sa.Numeric(14, 3), nullable=True),
            sa.Column('billet_total', sa.Numeric(14, 3), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('business_date', 'workshop_code', name='uq_production_plan_date_workshop'),
        )
        op.create_index('ix_production_plan_business_date', 'production_plan_daily', ['business_date'])
        op.create_index('ix_production_plan_workshop_code', 'production_plan_daily', ['workshop_code'])

    # G5b alloy_spec_breakdown
    if not _has_table(inspector, 'alloy_spec_breakdown'):
        op.create_table(
            'alloy_spec_breakdown',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_code', sa.String(64), nullable=False),
            sa.Column('alloy_grade', sa.String(32), nullable=False),
            sa.Column('spec_text', sa.String(128), nullable=True),
            sa.Column('weight_tons', sa.Numeric(14, 3), nullable=True),
            sa.Column('scrap_count_casting1', sa.Integer(), nullable=True),
            sa.Column('scrap_count_casting2', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_alloy_spec_business_date', 'alloy_spec_breakdown', ['business_date'])
        op.create_index('ix_alloy_spec_workshop_code', 'alloy_spec_breakdown', ['workshop_code'])
        op.create_index('ix_alloy_spec_alloy_grade', 'alloy_spec_breakdown', ['alloy_grade'])

    # G6 shipment_outflow_record
    if not _has_table(inspector, 'shipment_outflow_record'):
        op.create_table(
            'shipment_outflow_record',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('customer_name', sa.String(128), nullable=True),
            sa.Column('batch_no', sa.String(64), nullable=True),
            sa.Column('alloy_state', sa.String(64), nullable=True),
            sa.Column('finished_spec', sa.String(128), nullable=True),
            sa.Column('coil_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('net_weight', sa.Numeric(14, 3), nullable=True),
            sa.Column('source_workshop_code', sa.String(64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_shipment_outflow_business_date', 'shipment_outflow_record', ['business_date'])
        op.create_index('ix_shipment_outflow_batch_no', 'shipment_outflow_record', ['batch_no'])
        op.create_index('ix_shipment_outflow_source_workshop_code', 'shipment_outflow_record', ['source_workshop_code'])

    # G9a recovery_daily
    if not _has_table(inspector, 'recovery_daily'):
        op.create_table(
            'recovery_daily',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('recovery_output_tons', sa.Numeric(14, 3), nullable=True),
            sa.Column('note', sa.String(512), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('business_date', name='uq_recovery_daily_date'),
        )
        op.create_index('ix_recovery_daily_business_date', 'recovery_daily', ['business_date'])

    # G9b overhaul_daily
    if not _has_table(inspector, 'overhaul_daily'):
        op.create_table(
            'overhaul_daily',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('roller_grind_count', sa.Integer(), nullable=True),
            sa.Column('energy_kwh', sa.Numeric(14, 3), nullable=True),
            sa.Column('gas_m3', sa.Numeric(14, 3), nullable=True),
            sa.Column('note', sa.String(512), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('business_date', name='uq_overhaul_daily_date'),
        )
        op.create_index('ix_overhaul_daily_business_date', 'overhaul_daily', ['business_date'])

    # G10 quality_issue_log
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

    # G10
    if _has_table(inspector, 'quality_issue_log'):
        op.drop_index('ix_quality_issue_shift_report_id', table_name='quality_issue_log')
        op.drop_index('ix_quality_issue_workshop_id', table_name='quality_issue_log')
        op.drop_index('ix_quality_issue_tracking_card_no', table_name='quality_issue_log')
        op.drop_index('ix_quality_issue_business_date', table_name='quality_issue_log')
        op.drop_table('quality_issue_log')

    # G9b
    if _has_table(inspector, 'overhaul_daily'):
        op.drop_index('ix_overhaul_daily_business_date', table_name='overhaul_daily')
        op.drop_table('overhaul_daily')

    # G9a
    if _has_table(inspector, 'recovery_daily'):
        op.drop_index('ix_recovery_daily_business_date', table_name='recovery_daily')
        op.drop_table('recovery_daily')

    # G6
    if _has_table(inspector, 'shipment_outflow_record'):
        op.drop_index('ix_shipment_outflow_source_workshop_code', table_name='shipment_outflow_record')
        op.drop_index('ix_shipment_outflow_batch_no', table_name='shipment_outflow_record')
        op.drop_index('ix_shipment_outflow_business_date', table_name='shipment_outflow_record')
        op.drop_table('shipment_outflow_record')

    # G5b
    if _has_table(inspector, 'alloy_spec_breakdown'):
        op.drop_index('ix_alloy_spec_alloy_grade', table_name='alloy_spec_breakdown')
        op.drop_index('ix_alloy_spec_workshop_code', table_name='alloy_spec_breakdown')
        op.drop_index('ix_alloy_spec_business_date', table_name='alloy_spec_breakdown')
        op.drop_table('alloy_spec_breakdown')

    # G5a
    if _has_table(inspector, 'production_plan_daily'):
        op.drop_index('ix_production_plan_workshop_code', table_name='production_plan_daily')
        op.drop_index('ix_production_plan_business_date', table_name='production_plan_daily')
        op.drop_table('production_plan_daily')

    # G4
    if _has_table(inspector, 'quality_yield_daily'):
        op.drop_index('ix_quality_yield_workshop_code', table_name='quality_yield_daily')
        op.drop_index('ix_quality_yield_business_date', table_name='quality_yield_daily')
        op.drop_table('quality_yield_daily')

    # G3
    if _has_column(inspector, 'mobile_shift_reports', 'attendance_payload'):
        op.drop_column('mobile_shift_reports', 'attendance_payload')

    # G1
    if _has_table(inspector, 'machine_energy_daily_compare'):
        op.drop_index('ix_machine_energy_compare_workshop_id', table_name='machine_energy_daily_compare')
        op.drop_index('ix_machine_energy_compare_machine_id', table_name='machine_energy_daily_compare')
        op.drop_index('ix_machine_energy_compare_business_date', table_name='machine_energy_daily_compare')
        op.drop_table('machine_energy_daily_compare')
