from __future__ import annotations

from collections.abc import Iterable


def _sum_values(values: Iterable[float | int | None]) -> float:
    return float(sum(float(value or 0.0) for value in values))


def yield_rate(chan_liang_ton: float, tou_liao_liang_ton: float) -> float:
    """成品率口径：产量 / 投料量；来源见 docs/domain/xintai-real-fields.md「生产」小节。"""
    if tou_liao_liang_ton == 0:
        return 0.0
    return chan_liang_ton / tou_liao_liang_ton


def scrap_rate(fei_liao_liang_ton: float, tou_liao_liang_ton: float) -> float:
    """废料率口径：产生废料 / 投料量；来源见 docs/domain/xintai-real-fields.md「生产」小节。"""
    if tou_liao_liang_ton == 0:
        return 0.0
    return fei_liao_liang_ton / tou_liao_liang_ton


def shift_output(ban_ci_chan_liang_ton: Iterable[float | int | None]) -> float:
    """班次产量口径：大夜、白班、小夜等班次产量求和；来源见 docs/domain/xintai-real-fields.md「生产」小节。"""
    return _sum_values(ban_ci_chan_liang_ton)


def daily_cumulative_output(ri_chan_liang_ton: Iterable[float | int | None]) -> float:
    """日累计产量口径：同一业务日多车间/机台日产量求和；来源见 docs/domain/xintai-real-fields.md「生产」小节。"""
    return _sum_values(ri_chan_liang_ton)


def monthly_cumulative_output(yue_nei_ri_chan_liang_ton: Iterable[float | int | None]) -> float:
    """月累计产量口径：月内已确认产量求和；来源见 docs/domain/xintai-real-fields.md「生产」小节。"""
    return _sum_values(yue_nei_ri_chan_liang_ton)
