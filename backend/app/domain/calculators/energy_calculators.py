from __future__ import annotations


def unit_energy_consumption(hao_dian_liang_kwh: float, chan_liang_ton: float) -> float:
    """单位能耗口径：耗电量(kWh) / 产量(t)；来源见 docs/domain/xintai-real-fields.md「能耗」小节。"""
    if chan_liang_ton == 0:
        return 0.0
    return hao_dian_liang_kwh / chan_liang_ton


def peak_valley_split(
    jian_dian_kwh: float,
    feng_dian_kwh: float,
    ping_dian_kwh: float,
    gu_dian_kwh: float,
) -> dict[str, float]:
    """峰谷分摊口径：尖/峰/平/谷电量求和并计算占比；来源见 docs/domain/xintai-real-fields.md「能耗」小节。"""
    total_kwh = jian_dian_kwh + feng_dian_kwh + ping_dian_kwh + gu_dian_kwh
    if total_kwh == 0:
        return {
            'total_kwh': 0.0,
            'jian_ratio': 0.0,
            'feng_ratio': 0.0,
            'ping_ratio': 0.0,
            'gu_ratio': 0.0,
        }
    return {
        'total_kwh': total_kwh,
        'jian_ratio': jian_dian_kwh / total_kwh,
        'feng_ratio': feng_dian_kwh / total_kwh,
        'ping_ratio': ping_dian_kwh / total_kwh,
        'gu_ratio': gu_dian_kwh / total_kwh,
    }


def cross_workshop_aggregate(che_jian_neng_hao_kwh: dict[str, float]) -> dict[str, float | int]:
    """跨车间汇总口径：各车间电量求和并保留车间数与最大单车间值；来源见 docs/domain/xintai-real-fields.md「能耗」小节。"""
    values = [float(value or 0.0) for value in che_jian_neng_hao_kwh.values()]
    return {
        'total_kwh': sum(values),
        'workshop_count': len(che_jian_neng_hao_kwh),
        'max_workshop_kwh': max(values) if values else 0.0,
    }
