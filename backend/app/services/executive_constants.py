"""经营驾驶舱阶段 1 的单价常量 + 默认映射。

阶段 2 会把这些抽到 SystemConfig 或 master_data 里，阶段 1 先硬编码。
"""

from __future__ import annotations

from decimal import Decimal

# 能源单价（含税）—— 参考 4 月 Excel 成本核算表
ELECTRICITY_PRICE_PER_KWH = Decimal('0.80')
NATURAL_GAS_PRICE_PER_M3 = Decimal('3.60')

# 人工粗摊：阶段 1 按月固定工资摊到每人天，待业务部给准数后改
LABOR_COST_PER_HEADCOUNT_PER_DAY = Decimal('350')

# 车间 → (默认合金, 默认工艺)。阶段 2 后会按 MobileShiftReport 扩字段记实际牌号
WORKSHOP_DEFAULT_PRODUCT: dict[str, tuple[str, str]] = {
    # 按 workshop_type 或 code 前缀兜底（找不到的使用 '5052' hot_rolling）
    'hot_rolling': ('5052', 'hot_rolling'),
    'cold_rolling': ('3003', 'cold_rolling'),
    'casting': ('5052', 'hot_rolling'),    # 铸轧归为热轧加工费口径
    'casting_rolling': ('5052', 'hot_rolling'),
    'extrusion': ('6063', 'hot_rolling'),
    'six_series': ('6061', 'hot_rolling'),
}

# 最终兜底：任何查不到的车间都算 5052 热轧
FALLBACK_ALLOY_GRADE = '5052'
FALLBACK_PROCESS_TYPE = 'hot_rolling'

# 默认客户分层（查加工费时用，找不到自动 fallback 到 default）
DEFAULT_CUSTOMER_TIER = 'default'


__all__ = [
    'ELECTRICITY_PRICE_PER_KWH',
    'NATURAL_GAS_PRICE_PER_M3',
    'LABOR_COST_PER_HEADCOUNT_PER_DAY',
    'WORKSHOP_DEFAULT_PRODUCT',
    'FALLBACK_ALLOY_GRADE',
    'FALLBACK_PROCESS_TYPE',
    'DEFAULT_CUSTOMER_TIER',
]
