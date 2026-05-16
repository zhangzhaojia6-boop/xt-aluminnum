from __future__ import annotations

import pytest

from app.domain.calculators.attendance_calculators import attendance_rate, makeup_card_rate, overtime_hours
from app.domain.calculators.energy_calculators import (
    cross_workshop_aggregate,
    peak_valley_split,
    unit_energy_consumption,
)
from app.domain.calculators.production_calculators import (
    daily_cumulative_output,
    monthly_cumulative_output,
    scrap_rate,
    shift_output,
    yield_rate,
)
from app.domain.calculators.quality_calculators import defect_rate, disposition_breakdown, pareto_top_n


@pytest.mark.parametrize(
    ('chan_liang_ton', 'tou_liao_liang_ton', 'expected_rate'),
    [
        pytest.param(1678.246, 1761.996, 0.95246867756794, id='5.5-zhu-ding-month-yield'),
        pytest.param(61.86, 63.0, 0.981904761904762, id='5.5-zhu-er-month-yield'),
        pytest.param(669.59, 692.55, 0.9668471590498882, id='5.5-2050-month-yield'),
    ],
)
def test_yield_rate_uses_real_5_5_cumulative_output(
    chan_liang_ton: float,
    tou_liao_liang_ton: float,
    expected_rate: float,
) -> None:
    assert yield_rate(chan_liang_ton, tou_liao_liang_ton) == pytest.approx(expected_rate)


@pytest.mark.parametrize(
    ('fei_liao_liang_ton', 'tou_liao_liang_ton', 'expected_rate'),
    [
        pytest.param(17.46, 331.65, 0.05264586160108549, id='5.5-zhu-ding-daily-scrap'),
        pytest.param(0.82, 25.0, 0.0328, id='5.5-zhu-er-daily-scrap'),
        pytest.param(5.61, 90.74, 0.061824994489751, id='5.5-2050-daily-scrap'),
    ],
)
def test_scrap_rate_uses_real_5_5_daily_scrap(
    fei_liao_liang_ton: float,
    tou_liao_liang_ton: float,
    expected_rate: float,
) -> None:
    assert scrap_rate(fei_liao_liang_ton, tou_liao_liang_ton) == pytest.approx(expected_rate)


@pytest.mark.parametrize(
    ('ban_ci_chan_liang_ton', 'expected_ton'),
    [
        pytest.param([11.7, 12.45, 6.5], 30.65, id='5.5-zhu-er-3-machine-shifts'),
        pytest.param([48.0, 4.17, 24.32], 76.49, id='5.5-zhu-er-6-machine-shifts'),
        pytest.param([2.2, 9.91, 10.0], 22.11, id='5.5-zhu-san-2-machine-shifts'),
    ],
)
def test_shift_output_sums_real_5_5_shift_columns(
    ban_ci_chan_liang_ton: list[float],
    expected_ton: float,
) -> None:
    assert shift_output(ban_ci_chan_liang_ton) == pytest.approx(expected_ton)


@pytest.mark.parametrize(
    ('ri_chan_liang_ton', 'expected_ton'),
    [
        pytest.param([24.18, 36.2], 60.38, id='5.5-zhu-zha-branch'),
        pytest.param([224.54, 31.08, 85.13], 340.75, id='5.5-rolling-machines'),
        pytest.param([45.286, 75.96, 196.08, 39.58], 356.906, id='5.5-finishing-and-stretching'),
    ],
)
def test_daily_cumulative_output_sums_real_5_5_daily_rows(
    ri_chan_liang_ton: list[float],
    expected_ton: float,
) -> None:
    assert daily_cumulative_output(ri_chan_liang_ton) == pytest.approx(expected_ton)


@pytest.mark.parametrize(
    ('yue_nei_ri_chan_liang_ton', 'expected_ton'),
    [
        pytest.param([61.86, 189.21], 251.07, id='5.5-zhu-zha-month'),
        pytest.param([1037.31, 203.02, 669.59], 1909.92, id='5.5-rolling-month'),
        pytest.param([304.506, 387.87, 801.8, 194.2], 1688.376, id='5.5-finishing-month'),
    ],
)
def test_monthly_cumulative_output_sums_real_5_5_month_rows(
    yue_nei_ri_chan_liang_ton: list[float],
    expected_ton: float,
) -> None:
    assert monthly_cumulative_output(yue_nei_ri_chan_liang_ton) == pytest.approx(expected_ton)


@pytest.mark.parametrize(
    ('hao_dian_liang_kwh', 'chan_liang_ton', 'expected_kwh_per_ton'),
    [
        pytest.param(1920.0, 24.18, 79.40446650124069, id='5.5-zhu-er-electricity'),
        pytest.param(3430.0, 36.2, 94.7513812154696, id='5.5-zhu-san-electricity'),
        pytest.param(10500.0, 224.54, 46.762269528814464, id='5.5-1650-electricity'),
    ],
)
def test_unit_energy_consumption_uses_real_5_5_electricity(
    hao_dian_liang_kwh: float,
    chan_liang_ton: float,
    expected_kwh_per_ton: float,
) -> None:
    assert unit_energy_consumption(hao_dian_liang_kwh, chan_liang_ton) == pytest.approx(expected_kwh_per_ton)


@pytest.mark.parametrize(
    ('jian_dian_kwh', 'feng_dian_kwh', 'ping_dian_kwh', 'gu_dian_kwh', 'expected_total_kwh'),
    [
        pytest.param(8339.0, 94519.0, 4450.0, 0.0, 107308.0, id='5.5-park-new-factory-office'),
        pytest.param(7950.0, 1920.0, 3430.0, 300.0, 13600.0, id='5.5-workshop-electricity-sample'),
        pytest.param(3120.0, 400.0, 720.0, 0.0, 4240.0, id='5.5-office-building-sample'),
    ],
)
def test_peak_valley_split_returns_total_and_ratios_from_5_5_kwh_values(
    jian_dian_kwh: float,
    feng_dian_kwh: float,
    ping_dian_kwh: float,
    gu_dian_kwh: float,
    expected_total_kwh: float,
) -> None:
    split = peak_valley_split(jian_dian_kwh, feng_dian_kwh, ping_dian_kwh, gu_dian_kwh)

    assert split['total_kwh'] == pytest.approx(expected_total_kwh)
    assert split['feng_ratio'] == pytest.approx(feng_dian_kwh / expected_total_kwh)
    assert split['gu_ratio'] == pytest.approx(0.0 if expected_total_kwh == 0 else gu_dian_kwh / expected_total_kwh)


@pytest.mark.parametrize(
    ('che_jian_neng_hao_kwh', 'expected_total_kwh'),
    [
        pytest.param({'铸锭': 7950.0, '铸二': 1920.0, '铸三': 3430.0}, 13300.0, id='5.5-casting-electricity'),
        pytest.param({'1650': 10500.0, '1850': 5600.0, '2050': 24100.0}, 40200.0, id='5.5-rolling-electricity'),
        pytest.param({'回收': 3330.0, '大修+办公楼': 400.0, '办公楼+宿舍+餐厅+东门岗': 720.0}, 4450.0, id='5.5-office-electricity'),
    ],
)
def test_cross_workshop_aggregate_sums_real_5_5_workshop_energy(
    che_jian_neng_hao_kwh: dict[str, float],
    expected_total_kwh: float,
) -> None:
    aggregate = cross_workshop_aggregate(che_jian_neng_hao_kwh)

    assert aggregate['total_kwh'] == pytest.approx(expected_total_kwh)
    assert aggregate['workshop_count'] == len(che_jian_neng_hao_kwh)
    assert aggregate['max_workshop_kwh'] == pytest.approx(max(che_jian_neng_hao_kwh.values()))


@pytest.mark.parametrize(
    ('bu_he_ge_juan_count', 'he_ji_juan_count', 'expected_rate'),
    [
        pytest.param(1, 4, 0.25, id='5.5-contract-quality-hole'),
        pytest.param(3, 3, 1.0, id='5.5-contract-quality-sticky-edge-small-coil'),
        pytest.param(1, 5, 0.2, id='5.5-contract-quality-narrow-width'),
    ],
)
def test_defect_rate_uses_real_5_5_contract_quality_counts(
    bu_he_ge_juan_count: int,
    he_ji_juan_count: int,
    expected_rate: float,
) -> None:
    assert defect_rate(bu_he_ge_juan_count, he_ji_juan_count) == pytest.approx(expected_rate)


@pytest.mark.parametrize(
    ('que_xian_counts', 'qian_n_ming_count', 'expected_first_name', 'expected_first_count'),
    [
        pytest.param({'粘板缺铝小卷': 3, '小卷': 2, '硬铝': 1, '孔洞': 1}, 2, '粘板缺铝小卷', 3, id='5.5-top-two'),
        pytest.param({'排气热边': 3, '小卷': 2, '缺边': 1}, 1, '排气热边', 3, id='5.5-top-one'),
        pytest.param({'小卷': 2, '硬铝': 1, '窄尺': 1, '缺边': 1}, 3, '小卷', 2, id='5.5-top-three'),
    ],
)
def test_pareto_top_n_orders_real_5_5_defect_notes(
    que_xian_counts: dict[str, int],
    qian_n_ming_count: int,
    expected_first_name: str,
    expected_first_count: int,
) -> None:
    pareto = pareto_top_n(que_xian_counts, qian_n_ming_count)

    assert pareto[0]['name'] == expected_first_name
    assert pareto[0]['count'] == expected_first_count
    assert pareto[-1]['cumulative_ratio'] <= 1.0


@pytest.mark.parametrize(
    ('chu_zhi_juan_count', 'expected_total_count', 'expected_key'),
    [
        pytest.param({'返修': 3, '让步接收': 1}, 4, '返修', id='5.5-quality-disposition-sample-a'),
        pytest.param({'报废': 1, '返修': 2, '待判': 1}, 4, '返修', id='5.5-quality-disposition-sample-b'),
        pytest.param({'待判': 3, '报废': 1, '让步接收': 1}, 5, '待判', id='5.5-quality-disposition-sample-c'),
    ],
)
def test_disposition_breakdown_returns_total_and_ratio(
    chu_zhi_juan_count: dict[str, int],
    expected_total_count: int,
    expected_key: str,
) -> None:
    breakdown = disposition_breakdown(chu_zhi_juan_count)

    assert breakdown['total_count'] == expected_total_count
    assert breakdown['items'][expected_key]['count'] == chu_zhi_juan_count[expected_key]
    assert breakdown['items'][expected_key]['ratio'] == pytest.approx(chu_zhi_juan_count[expected_key] / expected_total_count)


@pytest.mark.parametrize(
    ('shi_dao_ren_shu_count', 'ying_dao_ren_shu_count', 'expected_rate'),
    [
        pytest.param(48, 50, 0.96, id='attendance-template-full-shift'),
        pytest.param(36, 40, 0.9, id='attendance-template-partial-shift'),
        pytest.param(0, 12, 0.0, id='attendance-template-empty-shift'),
    ],
)
def test_attendance_rate_uses_schedule_and_clock_counts(
    shi_dao_ren_shu_count: int,
    ying_dao_ren_shu_count: int,
    expected_rate: float,
) -> None:
    assert attendance_rate(shi_dao_ren_shu_count, ying_dao_ren_shu_count) == pytest.approx(expected_rate)


@pytest.mark.parametrize(
    ('jia_ban_fen_zhong_minute', 'expected_hours'),
    [
        pytest.param(90, 1.5, id='attendance-template-90-minutes'),
        pytest.param(0, 0.0, id='attendance-template-zero'),
        pytest.param(375, 6.25, id='attendance-template-375-minutes'),
    ],
)
def test_overtime_hours_converts_attendance_minutes(
    jia_ban_fen_zhong_minute: int,
    expected_hours: float,
) -> None:
    assert overtime_hours(jia_ban_fen_zhong_minute) == pytest.approx(expected_hours)


@pytest.mark.parametrize(
    ('bu_ka_ci_shu_count', 'da_ka_ci_shu_count', 'expected_rate'),
    [
        pytest.param(2, 100, 0.02, id='attendance-template-low-makeup'),
        pytest.param(0, 84, 0.0, id='attendance-template-no-makeup'),
        pytest.param(5, 80, 0.0625, id='attendance-template-five-makeup'),
    ],
)
def test_makeup_card_rate_uses_makeup_count_over_clock_count(
    bu_ka_ci_shu_count: int,
    da_ka_ci_shu_count: int,
    expected_rate: float,
) -> None:
    assert makeup_card_rate(bu_ka_ci_shu_count, da_ka_ci_shu_count) == pytest.approx(expected_rate)


# --- A2 新增口径测试（红阶段） ---

from app.domain.calculators.production_calculators import (
    reporting_rate,
    day_over_day_change,
    month_average_daily_output,
)
from app.domain.calculators.production_calculators import contract_fulfillment_rate


@pytest.mark.parametrize(
    ('reported_count', 'expected_count', 'expected_rate'),
    [
        pytest.param(18, 20, 0.9, id='5.5-normal-shift-reporting'),
        pytest.param(20, 20, 1.0, id='5.5-full-reporting'),
        pytest.param(0, 20, 0.0, id='5.5-no-reporting'),
        pytest.param(15, 0, 0.0, id='5.5-zero-expected-guard'),
    ],
)
def test_reporting_rate_calculates_shift_coverage(
    reported_count: int,
    expected_count: int,
    expected_rate: float,
) -> None:
    assert reporting_rate(reported_count, expected_count) == pytest.approx(expected_rate)


@pytest.mark.parametrize(
    ('today_output', 'yesterday_output', 'expected_change'),
    [
        pytest.param(356.9, 340.75, (356.9 - 340.75) / 340.75, id='5.5-finishing-dod-up'),
        pytest.param(60.38, 76.49, (60.38 - 76.49) / 76.49, id='5.5-casting-dod-down'),
        pytest.param(100.0, 100.0, 0.0, id='5.5-no-change'),
        pytest.param(50.0, 0.0, 0.0, id='5.5-zero-yesterday-guard'),
    ],
)
def test_day_over_day_change_computes_ratio(
    today_output: float,
    yesterday_output: float,
    expected_change: float,
) -> None:
    assert day_over_day_change(today_output, yesterday_output) == pytest.approx(expected_change)


@pytest.mark.parametrize(
    ('monthly_total', 'active_days', 'expected_avg'),
    [
        pytest.param(1909.92, 16, 1909.92 / 16, id='5.5-rolling-month-avg'),
        pytest.param(251.07, 8, 251.07 / 8, id='5.5-casting-month-avg'),
        pytest.param(1688.376, 14, 1688.376 / 14, id='5.5-finishing-month-avg'),
        pytest.param(500.0, 0, 0.0, id='5.5-zero-days-guard'),
    ],
)
def test_month_average_daily_output_divides_by_active_days(
    monthly_total: float,
    active_days: int,
    expected_avg: float,
) -> None:
    assert month_average_daily_output(monthly_total, active_days) == pytest.approx(expected_avg)


@pytest.mark.parametrize(
    ('delivered_tons', 'contract_tons', 'expected_rate'),
    [
        pytest.param(850.0, 1000.0, 0.85, id='5.5-contract-partial-delivery'),
        pytest.param(1000.0, 1000.0, 1.0, id='5.5-contract-full-delivery'),
        pytest.param(1200.0, 1000.0, 1.2, id='5.5-contract-over-delivery'),
        pytest.param(0.0, 0.0, 0.0, id='5.5-zero-contract-guard'),
    ],
)
def test_contract_fulfillment_rate_computes_delivery_ratio(
    delivered_tons: float,
    contract_tons: float,
    expected_rate: float,
) -> None:
    assert contract_fulfillment_rate(delivered_tons, contract_tons) == pytest.approx(expected_rate)
