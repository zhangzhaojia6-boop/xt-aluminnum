"""cost strategy contract tables

Revision ID: 0028_cost_strategy_tables
Revises: 0027_executive_dashboard
Create Date: 2026-05-13 13:20:00.000000
"""

from datetime import date

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0028_cost_strategy_tables'
down_revision = '0027_executive_dashboard'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')

    if not _has_table(inspector, 'cost_price_master'):
        op.create_table(
            'cost_price_master',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('item_code', sa.String(60), nullable=False),
            sa.Column('item_name', sa.String(120), nullable=False),
            sa.Column('unit', sa.String(20), nullable=False),
            sa.Column('unit_price', sa.Numeric(14, 4), nullable=False),
            sa.Column('effective_from', sa.Date(), nullable=False),
            sa.Column('effective_to', sa.Date(), nullable=True),
            sa.Column('workshop_scope', sa.String(120), nullable=False, server_default='ALL'),
            sa.Column('process_scope', sa.String(80), nullable=False, server_default='ALL'),
            sa.Column('source_note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'item_code',
                'effective_from',
                'workshop_scope',
                'process_scope',
                name='uq_cost_price_master_version',
            ),
        )
        op.create_index('ix_cost_price_master_item_code', 'cost_price_master', ['item_code'])
        op.create_index('ix_cost_price_master_effective', 'cost_price_master', ['effective_from'])
        op.create_index('ix_cost_price_master_workshop', 'cost_price_master', ['workshop_scope'])
        op.create_index('ix_cost_price_master_process', 'cost_price_master', ['process_scope'])

    if not _has_table(inspector, 'cost_workshop_strategy'):
        op.create_table(
            'cost_workshop_strategy',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('workshop_code', sa.String(40), nullable=False),
            sa.Column('strategy_code', sa.String(80), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('effective_from', sa.Date(), nullable=False),
            sa.Column('caliber', sa.String(20), nullable=False, server_default='output'),
            sa.Column('config_snapshot', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'workshop_code',
                'strategy_code',
                'effective_from',
                name='uq_cost_workshop_strategy_version',
            ),
        )
        op.create_index('ix_cost_workshop_strategy_workshop', 'cost_workshop_strategy', ['workshop_code'])
        op.create_index('ix_cost_workshop_strategy_code', 'cost_workshop_strategy', ['strategy_code'])
        op.create_index('ix_cost_workshop_strategy_effective', 'cost_workshop_strategy', ['effective_from'])

    if not _has_table(inspector, 'cost_daily_result'):
        op.create_table(
            'cost_daily_result',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_code', sa.String(40), nullable=False),
            sa.Column('strategy_code', sa.String(80), nullable=False),
            sa.Column('total_cost', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('output_ton_cost', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('throughput_ton_cost', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('caliber', sa.String(20), nullable=False, server_default='output'),
            sa.Column('breakdown_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('process_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'business_date',
                'workshop_code',
                'strategy_code',
                'caliber',
                name='uq_cost_daily_result_version',
            ),
        )
        op.create_index('ix_cost_daily_result_date', 'cost_daily_result', ['business_date'])
        op.create_index('ix_cost_daily_result_workshop', 'cost_daily_result', ['workshop_code'])
        op.create_index('ix_cost_daily_result_strategy', 'cost_daily_result', ['strategy_code'])

    if not _has_table(inspector, 'cost_monthly_rollup'):
        op.create_table(
            'cost_monthly_rollup',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('month', sa.String(7), nullable=False),
            sa.Column('workshop_code', sa.String(40), nullable=False),
            sa.Column('strategy_code', sa.String(80), nullable=False),
            sa.Column('month_total_cost', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('month_output_ton_cost', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('month_throughput_ton_cost', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('source', sa.String(60), nullable=False, server_default='frontend_strategy_snapshot'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'month',
                'workshop_code',
                'strategy_code',
                name='uq_cost_monthly_rollup_version',
            ),
        )
        op.create_index('ix_cost_monthly_rollup_month', 'cost_monthly_rollup', ['month'])
        op.create_index('ix_cost_monthly_rollup_workshop', 'cost_monthly_rollup', ['workshop_code'])
        op.create_index('ix_cost_monthly_rollup_strategy', 'cost_monthly_rollup', ['strategy_code'])

    if not _has_table(inspector, 'cost_variance_record'):
        op.create_table(
            'cost_variance_record',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('business_date', sa.Date(), nullable=False),
            sa.Column('workshop_code', sa.String(40), nullable=False),
            sa.Column('variance_type', sa.String(80), nullable=False),
            sa.Column('baseline_value', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('current_value', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('diff_value', sa.Numeric(14, 2), nullable=False, server_default='0'),
            sa.Column('status', sa.String(20), nullable=False, server_default='normal'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'business_date',
                'workshop_code',
                'variance_type',
                name='uq_cost_variance_record_version',
            ),
        )
        op.create_index('ix_cost_variance_record_date', 'cost_variance_record', ['business_date'])
        op.create_index('ix_cost_variance_record_workshop', 'cost_variance_record', ['workshop_code'])
        op.create_index('ix_cost_variance_record_type', 'cost_variance_record', ['variance_type'])
        op.create_index('ix_cost_variance_record_status', 'cost_variance_record', ['status'])

    _seed_cost_price_master(bind)


def _seed_cost_price_master(bind: sa.engine.Connection) -> None:
    effective_from = date(2026, 4, 1)
    seed_rows = [
        ('ELECTRICITY', '电费', 'kWh', 0.8, None, 'ALL', 'ALL', '大推进.md 默认单价'),
        ('NATURAL_GAS', '天然气', 'm3', 3.6, None, 'ALL', 'ALL', '大推进.md 默认单价'),
        ('WATER', '水', 't', 1.1, None, 'HR', 'ALL', '热轧默认单价'),
        ('WATER_LEVELING', '拉矫水', 't', 4, None, 'LJ', 'leveling', '拉矫主线默认单价'),
        ('D40', 'D40 包装材', 'kg', 9.5, None, 'JZ,LJ', 'packaging', '精整/拉矫默认单价'),
        ('ALUMINUM_SLEEVE', '铝套筒', 'kg', 5, None, 'LJ', 'leveling', '拉矫主线默认单价'),
        ('STEEL_BELT', '钢带', 'kg', 4.1, None, 'LJ', 'slitting', '拉矫大分切默认单价'),
        ('STEEL_BUCKLE', '钢带扣', 'kg', 4.37, None, 'LJ', 'slitting', '拉矫大分切默认单价'),
        ('THERMOCOUPLE', '热电偶', 'm', 17, None, 'LJ', 'anneal', '退火炉默认单价'),
        ('ROLLING_OIL', '轧制油', 'kg', 8.2, None, '2050,1650,1850,HWB,HR', 'rolling', '损耗策略默认单价'),
        ('WHITE_SOIL', '白土', 'bag', 39, None, '2050,1650,1850,HWB', 'loss', '损耗策略默认单价'),
        ('DIATOMITE', '硅藻土', 'bag', 54, None, '2050,1650,1850,HWB', 'loss', '损耗策略默认单价'),
        ('ROLLER_GUARANTEE', '辊系保障', 'time', 2000, None, '2050,1650,1850', 'support', '损耗策略默认单价'),
        ('PATTERN_ROLLER_GUARANTEE', '花纹板辊系保障', 'time', 6000, None, 'HWB', 'support', '花纹板额外单价'),
        ('PATTERN_ROLL_MATCHING', '花纹板配辊', 'time', 1000, None, 'HWB', 'support', '花纹板额外单价'),
        ('FILTER_AGENT', '飞滤素', 'kg', 9, None, 'HWB', 'loss', '花纹板额外单价'),
        ('STEAM', '蒸汽', 't', 0, None, 'ALL', 'utility', '预留价格主数据'),
        ('AIR_ELECTRICITY', '空压机电耗', 'kWh', 0.8, None, 'LJ', 'utility', '公辅分摊默认单价'),
    ]
    insert_price = sa.text(
        """
        INSERT INTO cost_price_master
            (item_code, item_name, unit, unit_price, effective_from, effective_to,
             workshop_scope, process_scope, source_note)
        VALUES
            (:item_code, :item_name, :unit, :unit_price, :effective_from, :effective_to,
             :workshop_scope, :process_scope, :source_note)
        ON CONFLICT (item_code, effective_from, workshop_scope, process_scope) DO NOTHING
        """
    )
    for row in seed_rows:
        bind.execute(
            insert_price,
            {
                'item_code': row[0],
                'item_name': row[1],
                'unit': row[2],
                'unit_price': row[3],
                'effective_from': effective_from,
                'effective_to': row[4],
                'workshop_scope': row[5],
                'process_scope': row[6],
                'source_note': row[7],
            },
        )


def downgrade() -> None:
    op.drop_table('cost_variance_record')
    op.drop_table('cost_monthly_rollup')
    op.drop_table('cost_daily_result')
    op.drop_table('cost_workshop_strategy')
    op.drop_table('cost_price_master')
