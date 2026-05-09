"""executive dashboard tables (phase 1) + processing fee engine with surcharges

Revision ID: 0027_executive_dashboard
Revises: 0026_unique_user_dingtalk_bindings
Create Date: 2026-05-09 14:40:00.000000
"""

from datetime import date

from alembic import op
import sqlalchemy as sa


revision = '0027_executive_dashboard'
down_revision = '0026_unique_user_dingtalk_bindings'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    json_type = sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), 'postgresql')

    if not _has_table(inspector, 'aluminum_price_daily'):
        op.create_table(
            'aluminum_price_daily',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('price_date', sa.Date(), nullable=False),
            sa.Column('price_per_ton', sa.Numeric(10, 2), nullable=False),
            sa.Column('source', sa.String(50), nullable=False, server_default='changjiang_a00'),
            sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('raw_payload', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('price_date', name='uq_aluminum_price_daily_date'),
        )
        op.create_index('ix_aluminum_price_daily_date', 'aluminum_price_daily', ['price_date'])

    if not _has_table(inspector, 'processing_fee_rules'):
        op.create_table(
            'processing_fee_rules',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('customer_tier', sa.String(40), nullable=False, server_default='default'),
            sa.Column('alloy_grade', sa.String(20), nullable=False),
            sa.Column('process_type', sa.String(20), nullable=False),
            sa.Column('temper', sa.String(20), nullable=True),
            sa.Column('thickness_min_mm', sa.Numeric(6, 3), nullable=True),
            sa.Column('thickness_max_mm', sa.Numeric(6, 3), nullable=True),
            sa.Column('fee_per_ton', sa.Numeric(10, 2), nullable=False),
            sa.Column('is_vat_inclusive', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('effective_from', sa.Date(), nullable=False),
            sa.Column('effective_to', sa.Date(), nullable=True),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'customer_tier', 'alloy_grade', 'process_type', 'temper',
                'thickness_min_mm', 'effective_from',
                name='uq_processing_fee_rule_version',
            ),
        )
        op.create_index('ix_processing_fee_rules_customer', 'processing_fee_rules', ['customer_tier'])
        op.create_index('ix_processing_fee_rules_alloy', 'processing_fee_rules', ['alloy_grade'])
        op.create_index('ix_processing_fee_rules_process', 'processing_fee_rules', ['process_type'])
        op.create_index('ix_processing_fee_rules_effective', 'processing_fee_rules', ['effective_from'])

    if not _has_table(inspector, 'processing_fee_surcharges'):
        op.create_table(
            'processing_fee_surcharges',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('customer_tier', sa.String(40), nullable=False, server_default='default'),
            sa.Column('surcharge_type', sa.String(20), nullable=False),
            sa.Column('condition_json', json_type, nullable=False),
            sa.Column('fee_per_ton', sa.Numeric(10, 2), nullable=False),
            sa.Column('effective_from', sa.Date(), nullable=False),
            sa.Column('effective_to', sa.Date(), nullable=True),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_surcharges_customer', 'processing_fee_surcharges', ['customer_tier'])
        op.create_index('ix_surcharges_type', 'processing_fee_surcharges', ['surcharge_type'])
        op.create_index('ix_surcharges_effective', 'processing_fee_surcharges', ['effective_from'])

    if not _has_table(inspector, 'machine_daily_cost_snapshots'):
        op.create_table(
            'machine_daily_cost_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=False),
            sa.Column('machine_line_id', sa.Integer(), sa.ForeignKey('equipment.id'), nullable=True),
            sa.Column('electricity_kwh', sa.Numeric(14, 3), nullable=True),
            sa.Column('electricity_cost', sa.Numeric(14, 2), nullable=True),
            sa.Column('natural_gas_m3', sa.Numeric(14, 3), nullable=True),
            sa.Column('natural_gas_cost', sa.Numeric(14, 2), nullable=True),
            sa.Column('labor_cost', sa.Numeric(14, 2), nullable=True),
            sa.Column('aux_material_cost', sa.Numeric(14, 2), nullable=True),
            sa.Column('total_cost', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('is_estimated', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('estimation_note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'business_date', 'workshop_id', 'machine_line_id',
                name='uq_machine_daily_cost',
            ),
        )
        op.create_index('ix_machine_daily_cost_date', 'machine_daily_cost_snapshots', ['business_date'])
        op.create_index('ix_machine_daily_cost_workshop', 'machine_daily_cost_snapshots', ['workshop_id'])
        op.create_index('ix_machine_daily_cost_machine', 'machine_daily_cost_snapshots', ['machine_line_id'])

    if not _has_table(inspector, 'machine_daily_profit_snapshots'):
        op.create_table(
            'machine_daily_profit_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_id', sa.Integer(), sa.ForeignKey('workshops.id'), nullable=False),
            sa.Column('machine_line_id', sa.Integer(), sa.ForeignKey('equipment.id'), nullable=True),
            sa.Column('alloy_grade', sa.String(20), nullable=True),
            sa.Column('process_type', sa.String(20), nullable=True),
            sa.Column('output_tons', sa.Numeric(12, 3), nullable=True),
            sa.Column('processing_fee_per_ton', sa.Numeric(10, 2), nullable=True),
            sa.Column('processing_revenue', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('total_cost', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('gross_profit', sa.Numeric(14, 2), nullable=True),
            sa.Column('gross_margin_pct', sa.Numeric(6, 2), nullable=True),
            sa.Column('is_estimated', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('has_missing_fee_rule', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('estimation_note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'business_date', 'workshop_id', 'machine_line_id', 'alloy_grade',
                name='uq_machine_daily_profit',
            ),
        )
        op.create_index('ix_machine_daily_profit_date', 'machine_daily_profit_snapshots', ['business_date'])
        op.create_index('ix_machine_daily_profit_workshop', 'machine_daily_profit_snapshots', ['workshop_id'])
        op.create_index('ix_machine_daily_profit_machine', 'machine_daily_profit_snapshots', ['machine_line_id'])
        op.create_index('ix_machine_daily_profit_alloy', 'machine_daily_profit_snapshots', ['alloy_grade'])

    _seed_processing_fee_rules(bind)


def _seed_processing_fee_rules(bind: sa.engine.Connection) -> None:
    effective_from = date(2026, 1, 1)
    effective_note_default = '阶段 1 种子数据，来自手写加工费表（客户A 含税出厂价）'
    effective_note_hc = '阶段 1 种子数据，来自报价单X(河南鑫泰/巩义恒昌)含税出厂价'
    default_seeds = [
        ('default', '1060', 'cold_rolling', None, None, None, 1400),
        ('default', '1100', 'cold_rolling', None, None, None, 1500),
        ('default', '3003', 'cold_rolling', None, None, None, 1800),
        ('default', '3003', 'hot_rolling', None, None, None, 2700),
        ('default', '5005', 'hot_rolling', None, None, None, 2600),
        ('default', '5052', 'hot_rolling', None, None, None, 2600),
        ('default', '5754', 'hot_rolling', None, None, None, 3100),
        ('default', '5083', 'hot_rolling', None, None, None, 3100),
        ('default', '6061', 'cold_rolling', None, None, None, 4700),
        ('default', '6061', 'hot_rolling', None, None, None, 4700),
        ('default', '6063', 'hot_rolling', None, None, None, 4700),
        ('default', '6016', 'hot_rolling', None, None, None, 9500),
        ('default', '6106', 'hot_rolling', None, None, None, 9500),
    ]
    hengchang_seeds = [
        ('hengchang', '5052', 'new_process', 'H32/O', 1.0, 3.0, 2300),
        ('hengchang', '5005', 'new_process', 'H32/O', 1.0, 3.0, 2300),
        ('hengchang', '5052', 'hot_rolling', 'H32/O', 3.0, 6.0, 2600),
        ('hengchang', '5005', 'hot_rolling', 'H32/O', 3.0, 6.0, 2600),
        ('hengchang', '3004', 'new_process', 'H24', 0.8, 3.0, 2100),
        ('hengchang', '5754', 'new_process', 'H32/O', 1.0, 3.0, 3100),
        ('hengchang', '6061', 'hot_rolling', 'T6/T4', 4.5, 6.0, 4500),
        ('hengchang', '6063', 'hot_rolling', 'T6/T4', 4.5, 6.0, 4500),
        ('hengchang', '6082', 'hot_rolling', 'T6/T4', 4.5, 6.0, 4500),
        ('hengchang', '6061', 'hot_rolling', 'O', 4.5, 6.0, 3200),
        ('hengchang', '6063', 'hot_rolling', 'O', 4.5, 6.0, 3200),
        ('hengchang', '6082', 'hot_rolling', 'O', 4.5, 6.0, 3200),
        ('hengchang', '6061', 'hot_rolling', 'T6/T4', 1.5, 4.5, 4850),
        ('hengchang', '6063', 'hot_rolling', 'T6/T4', 1.5, 4.5, 4850),
        ('hengchang', '6082', 'hot_rolling', 'T6/T4', 1.5, 4.5, 4850),
        ('hengchang', '6061', 'hot_rolling', 'T6/T4', 1.0, 1.5, 5500),
        ('hengchang', '6063', 'hot_rolling', 'T6/T4', 1.0, 1.5, 5500),
        ('hengchang', '6082', 'hot_rolling', 'T6/T4', 1.0, 1.5, 5500),
        ('hengchang', '6061', 'hot_rolling', 'T6/T4', 0.8, 1.0, 6000),
        ('hengchang', '6063', 'hot_rolling', 'T6/T4', 0.8, 1.0, 6000),
        ('hengchang', '6082', 'hot_rolling', 'T6/T4', 0.8, 1.0, 6000),
        ('hengchang', '6061', 'hot_rolling', 'T6/T4', 0.7, 0.8, 6500),
        ('hengchang', '6063', 'hot_rolling', 'T6/T4', 0.7, 0.8, 6500),
        ('hengchang', '6082', 'hot_rolling', 'T6/T4', 0.7, 0.8, 6500),
        ('hengchang', '6061', 'hot_rolling', 'T6/T4', 0.6, 0.7, 7000),
        ('hengchang', '6063', 'hot_rolling', 'T6/T4', 0.6, 0.7, 7000),
        ('hengchang', '6082', 'hot_rolling', 'T6/T4', 0.6, 0.7, 7000),
    ]
    insert_rule = sa.text(
        """
        INSERT INTO processing_fee_rules
            (customer_tier, alloy_grade, process_type, temper,
             thickness_min_mm, thickness_max_mm, fee_per_ton,
             is_vat_inclusive, effective_from, note)
        VALUES
            (:customer_tier, :alloy_grade, :process_type, :temper,
             :thickness_min_mm, :thickness_max_mm, :fee_per_ton,
             TRUE, :effective_from, :note)
        ON CONFLICT (customer_tier, alloy_grade, process_type, temper, thickness_min_mm, effective_from) DO NOTHING
        """
    )
    for row in default_seeds:
        bind.execute(insert_rule, {
            'customer_tier': row[0], 'alloy_grade': row[1], 'process_type': row[2],
            'temper': row[3], 'thickness_min_mm': row[4], 'thickness_max_mm': row[5],
            'fee_per_ton': row[6], 'effective_from': effective_from, 'note': effective_note_default,
        })
    for row in hengchang_seeds:
        bind.execute(insert_rule, {
            'customer_tier': row[0], 'alloy_grade': row[1], 'process_type': row[2],
            'temper': row[3], 'thickness_min_mm': row[4], 'thickness_max_mm': row[5],
            'fee_per_ton': row[6], 'effective_from': effective_from, 'note': effective_note_hc,
        })

    insert_surcharge = sa.text(
        """
        INSERT INTO processing_fee_surcharges
            (customer_tier, surcharge_type, condition_json, fee_per_ton, effective_from, note)
        VALUES
            (:customer_tier, :surcharge_type, :condition_json, :fee_per_ton, :effective_from, :note)
        """
    )
    import json
    surcharges = [
        ('hengchang', 'thin_gauge', {'thickness_lt': 1.0}, 300, '1.0mm 以下加 300 元/吨'),
        ('hengchang', 'thin_gauge', {'thickness_lt': 0.4}, 300, '0.4mm 以下再加 300 元/吨（3004 专用）'),
        ('hengchang', 'length', {'length_min': 4000, 'length_max': 4999}, 100, '板材长度 4000-4999mm 加 100 元/吨'),
        ('hengchang', 'length', {'length_min': 5000, 'length_max': 5999}, 200, '板材长度 5000-5999mm 加 200 元/吨'),
        ('hengchang', 'length', {'length_min': 6000, 'length_max': 6900}, 300, '板材长度 6000-6900mm 加 300 元/吨'),
        ('hengchang', 'width', {'width_gte': 1000}, 200, '板材宽度 1000mm 及以上加 200 元/吨'),
    ]
    for customer_tier, surcharge_type, condition, fee, note in surcharges:
        bind.execute(insert_surcharge, {
            'customer_tier': customer_tier,
            'surcharge_type': surcharge_type,
            'condition_json': json.dumps(condition),
            'fee_per_ton': fee,
            'effective_from': effective_from,
            'note': note,
        })


def downgrade() -> None:
    op.drop_table('machine_daily_profit_snapshots')
    op.drop_table('machine_daily_cost_snapshots')
    op.drop_table('processing_fee_surcharges')
    op.drop_table('processing_fee_rules')
    op.drop_table('aluminum_price_daily')
