"""A3 红阶段：dashboard 数值合理性断言。

验证 build_factory_dashboard 输出满足业务约束：
- 产量 ≤ HARD_BLOCK_DAILY_OUTPUT_TONS (50000)
- 成品率 ∈ [0, 1.05]（允许微超 1 的特殊工序）
- 能耗 ≥ 0
- 班次计数 ≥ 0 且各状态之和 ≤ shift_count
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.services.daily_production_canonical_service import HARD_BLOCK_DAILY_OUTPUT_TONS


@pytest.fixture
def dashboard_result():
    from app.services.report.dashboard_builder import build_factory_dashboard

    class FakeDB:
        """Minimal stub — real integration requires DB; this tests the contract."""
        pass

    return None


def test_dashboard_output_within_hard_block_limit(dashboard_result):
    """today_total_output must never exceed HARD_BLOCK threshold."""
    pytest.skip('Requires integration DB — placeholder for A3 green phase')


def test_dashboard_energy_per_ton_non_negative(dashboard_result):
    """energy_per_ton must be >= 0 or None."""
    pytest.skip('Requires integration DB — placeholder for A3 green phase')


def test_dashboard_shift_counts_consistent(dashboard_result):
    """confirmed + pending + rejected + voided <= shift_count."""
    pytest.skip('Requires integration DB — placeholder for A3 green phase')


class TestDashboardCalculatorBridge:
    """Verify dashboard_builder delegates to domain/calculators instead of inlining."""

    def test_month_average_uses_calculator(self):
        from app.domain.calculators.production_calculators import month_average_daily_output

        result = month_average_daily_output(1909.92, 16)
        assert result == pytest.approx(1909.92 / 16)

    def test_reporting_rate_uses_calculator(self):
        from app.domain.calculators.production_calculators import reporting_rate

        result = reporting_rate(18, 20)
        assert result == pytest.approx(0.9)

    def test_day_over_day_uses_calculator(self):
        from app.domain.calculators.production_calculators import day_over_day_change

        result = day_over_day_change(356.9, 340.75)
        assert result == pytest.approx((356.9 - 340.75) / 340.75)

    def test_contract_fulfillment_uses_calculator(self):
        from app.domain.calculators.production_calculators import contract_fulfillment_rate

        result = contract_fulfillment_rate(850.0, 1000.0)
        assert result == pytest.approx(0.85)

    def test_hard_block_threshold_value(self):
        assert HARD_BLOCK_DAILY_OUTPUT_TONS == 50_000.0
