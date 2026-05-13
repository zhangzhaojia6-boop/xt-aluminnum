from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import json_object_type


class AluminumPriceDaily(Base):
    """长江有色 A00 铝锭每日牌价。代采代付，不进 P&L，仅做现金流可视化。"""

    __tablename__ = 'aluminum_price_daily'
    __table_args__ = (UniqueConstraint('price_date', name='uq_aluminum_price_daily_date'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    price_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    price_per_ton: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default='changjiang_a00')
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProcessingFeeRule(Base):
    """加工费基础规则。按 (客户分层 × 牌号 × 工艺 × 状态 × 厚度区间) 定价。"""

    __tablename__ = 'processing_fee_rules'
    __table_args__ = (
        UniqueConstraint(
            'customer_tier',
            'alloy_grade',
            'process_type',
            'temper',
            'thickness_min_mm',
            'effective_from',
            name='uq_processing_fee_rule_version',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_tier: Mapped[str] = mapped_column(String(40), nullable=False, default='default', index=True)
    alloy_grade: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    process_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    temper: Mapped[str | None] = mapped_column(String(20), nullable=True)
    thickness_min_mm: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    thickness_max_mm: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    fee_per_ton: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_vat_inclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProcessingFeeSurcharge(Base):
    """加工费附加费规则。薄板、长度、宽度等按条件叠加。"""

    __tablename__ = 'processing_fee_surcharges'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_tier: Mapped[str] = mapped_column(String(40), nullable=False, default='default', index=True)
    surcharge_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    condition_json: Mapped[dict] = mapped_column(json_object_type, nullable=False)
    fee_per_ton: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CostPriceMaster(Base):
    """成本策略价格主数据。承接前端策略引擎的 price master contract。"""

    __tablename__ = 'cost_price_master'
    __table_args__ = (
        UniqueConstraint(
            'item_code',
            'effective_from',
            'workshop_scope',
            'process_scope',
            name='uq_cost_price_master_version',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_code: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    workshop_scope: Mapped[str] = mapped_column(String(120), nullable=False, default='ALL', index=True)
    process_scope: Mapped[str] = mapped_column(String(80), nullable=False, default='ALL', index=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CostWorkshopStrategy(Base):
    """车间成本策略版本。保存前端策略选择与运行配置快照。"""

    __tablename__ = 'cost_workshop_strategy'
    __table_args__ = (
        UniqueConstraint(
            'workshop_code',
            'strategy_code',
            'effective_from',
            name='uq_cost_workshop_strategy_version',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workshop_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    strategy_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    caliber: Mapped[str] = mapped_column(String(20), nullable=False, default='output')
    config_snapshot: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CostDailyResult(Base):
    """成本策略日结果。保存策略引擎按业务日输出的经营估算。"""

    __tablename__ = 'cost_daily_result'
    __table_args__ = (
        UniqueConstraint(
            'business_date',
            'workshop_code',
            'strategy_code',
            'caliber',
            name='uq_cost_daily_result_version',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    strategy_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    output_ton_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    throughput_ton_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    caliber: Mapped[str] = mapped_column(String(20), nullable=False, default='output')
    breakdown_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    process_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CostMonthlyRollup(Base):
    """成本策略月汇总。当前承接策略快照，不作为财务结账凭证。"""

    __tablename__ = 'cost_monthly_rollup'
    __table_args__ = (
        UniqueConstraint(
            'month',
            'workshop_code',
            'strategy_code',
            name='uq_cost_monthly_rollup_version',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    workshop_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    strategy_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    month_total_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_output_ton_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_throughput_ton_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(60), nullable=False, default='frontend_strategy_snapshot')

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CostVarianceRecord(Base):
    """成本策略校差记录。用于保留不同口径之间的差异提示。"""

    __tablename__ = 'cost_variance_record'
    __table_args__ = (
        UniqueConstraint(
            'business_date',
            'workshop_code',
            'variance_type',
            name='uq_cost_variance_record_version',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    variance_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    baseline_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    current_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    diff_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='normal', index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MachineDailyCostSnapshot(Base):
    """机列日成本快照。阶段 1 仅含能耗 + 粗人工摊。is_estimated=True。"""

    __tablename__ = 'machine_daily_cost_snapshots'
    __table_args__ = (
        UniqueConstraint(
            'business_date',
            'workshop_id',
            'machine_line_id',
            name='uq_machine_daily_cost',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('workshops.id'), nullable=False, index=True
    )
    machine_line_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('equipment.id'), nullable=True, index=True
    )

    electricity_kwh: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    electricity_cost: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    natural_gas_m3: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    natural_gas_cost: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    labor_cost: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    aux_material_cost: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    estimation_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MachineDailyProfitSnapshot(Base):
    """机列日毛利快照。收入(加工费x产量) - 成本 = 毛利。阶段 1 is_estimated=True。"""

    __tablename__ = 'machine_daily_profit_snapshots'
    __table_args__ = (
        UniqueConstraint(
            'business_date',
            'workshop_id',
            'machine_line_id',
            'alloy_grade',
            name='uq_machine_daily_profit',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('workshops.id'), nullable=False, index=True
    )
    machine_line_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('equipment.id'), nullable=True, index=True
    )
    alloy_grade: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    process_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    output_tons: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    processing_fee_per_ton: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    processing_revenue: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    gross_profit: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    gross_margin_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    has_missing_fee_rule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimation_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
