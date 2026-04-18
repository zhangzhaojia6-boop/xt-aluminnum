"""
阈值配置。
集中定义自动校验使用的阈值，替代旧流程中人工凭经验判断的环节。
"""

from __future__ import annotations

# 考勤
MIN_ATTENDANCE = 1
MAX_ATTENDANCE = 50

# 重量（吨）
MIN_WEIGHT = 0.0
MAX_SINGLE_SHIFT_WEIGHT = 500.0

# 能耗
MIN_ENERGY = 0.0
MAX_ELECTRICITY_DAILY = 100000.0
MAX_GAS_DAILY = 50000.0

# 差异核对
RECONCILIATION_TOLERANCE_PERCENT = 5.0

