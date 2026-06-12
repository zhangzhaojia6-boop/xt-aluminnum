from __future__ import annotations

from typing import Any


ACTIVE_PRODUCTION_WORKSHOP_CODES: tuple[str, ...] = (
    'ZD',
    'ZR2',
    'ZR3',
    'RZ',
    'JZ',
    'LJ',
    'JQ',
    'ZXTF-N',
    'ZXTF-P',
    'LZ1650',
    'LZ1850',
    'LZ2050',
)

ACTIVE_PRODUCTION_WORKSHOP_NAMES: tuple[str, ...] = (
    '铸锭',
    '铸二',
    '铸三',
    '热轧',
    '精整',
    '拉矫',
    '园区剪切',
    '新厂在线',
    '园区在线',
    '冷轧1650',
    '冷轧1850',
    '冷轧2050',
)

ACTIVE_PRODUCTION_WORKSHOP_CODE_SET = set(ACTIVE_PRODUCTION_WORKSHOP_CODES)


def is_active_production_workshop_code(code: str | None) -> bool:
    return str(code or '').strip().upper() in ACTIVE_PRODUCTION_WORKSHOP_CODE_SET


def filter_active_production_workshops(workshops: list[Any]) -> list[Any]:
    production_workshops: list[Any] = []
    for workshop in workshops:
        code = str(getattr(workshop, 'code', '') or '').strip().upper()
        if not code:
            production_workshops.append(workshop)
            continue
        if is_active_production_workshop_code(code):
            production_workshops.append(workshop)
    return production_workshops
