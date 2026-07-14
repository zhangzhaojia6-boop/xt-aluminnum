from __future__ import annotations

from typing import Any


def _text(*values: Any) -> str:
    return ' '.join(str(value or '') for value in values)


def resolve_mes_process_workshop_bucket(
    workshop_name: Any,
    process_name: Any = None,
    device_name: Any = None,
) -> str | None:
    """Map external MES process rows into the system's canonical workshop buckets."""
    workshop = str(workshop_name or '').strip()
    process = str(process_name or '').strip()
    device = str(device_name or '').strip()
    text = _text(workshop, process, device)

    if any(token in text for token in ('1650', '1850', '2050')):
        if '1650' in text:
            return '冷轧1650'
        if '1850' in text:
            return '冷轧1850'
        if '2050' in text:
            return '冷轧2050'

    if '园区精整' in workshop or '园区剪切' in workshop or workshop == '剪切车间':
        return '园区剪切'
    if workshop in {'精整', '精整车间', '冷轧精整车间'}:
        return '精整'
    if '拉矫' in workshop:
        return '拉矫'
    if '园区在线' in workshop or '园区退火' in text:
        return '园区在线'
    if '新厂在线' in workshop or (('北线' in text or '南线' in text) and '园区' not in text):
        return '新厂在线'
    if '淬火' in workshop:
        return '淬火车间'
    if '热轧' in workshop:
        return '热轧'
    if any(token in workshop for token in ('铸二', '铸轧二', '铸轧2')):
        return '铸二'
    if any(token in workshop for token in ('铸三', '铸轧三', '铸轧3')):
        return '铸三'
    if any(token in text for token in ('铸锭', '铸造', '熔铸', '熔炼')):
        return '铸锭'
    if '彩涂' in text:
        return '彩涂'
    if '剪切' in workshop:
        return '园区剪切'
    return None
