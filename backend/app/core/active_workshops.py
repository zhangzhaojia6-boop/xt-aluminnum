from __future__ import annotations

from typing import Any


ACTIVE_PRODUCTION_WORKSHOP_CODES: tuple[str, ...] = (
    'ZD',
    'ZR2',
    'ZR3',
    'RZ',
    'CH',
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
    '淬火车间',
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
ACTIVE_PRODUCTION_WORKSHOP_NAME_SET = set(ACTIVE_PRODUCTION_WORKSHOP_NAMES)

WORKSHOP_NAME_ALIASES: dict[str, str] = {
    '铸锭分厂': '铸锭',
    '铸锭车间': '铸锭',
    '铸锭': '铸锭',
    '铸轧二': '铸二',
    '铸轧二车间': '铸二',
    '铸二车间': '铸二',
    '铸二': '铸二',
    '铸轧三': '铸三',
    '铸轧三车间': '铸三',
    '铸三车间': '铸三',
    '铸三': '铸三',
    '热轧2050': '热轧',
    '热轧2050车间': '热轧',
    '热轧车间': '热轧',
    '热轧': '热轧',
    '淬火': '淬火车间',
    '淬火车间': '淬火车间',
    '园区淬火': '淬火车间',
    '园区淬火车间': '淬火车间',
    '精整车间': '精整',
    '冷轧精整车间': '精整',
    '园区精整': '园区剪切',
    '精整': '精整',
    '拉矫车间': '拉矫',
    '拉矫': '拉矫',
    '剪切车间': '园区剪切',
    '园区剪切车间': '园区剪切',
    '园区剪切': '园区剪切',
    '新厂在线退火': '新厂在线',
    '新厂在线车间': '新厂在线',
    '新厂在线': '新厂在线',
    '园区在线退火': '园区在线',
    '园区在线车间': '园区在线',
    '园区在线': '园区在线',
    '1650冷轧': '冷轧1650',
    '1650冷轧车间': '冷轧1650',
    '1650车间': '冷轧1650',
    '冷轧1650': '冷轧1650',
    '冷轧1650车间': '冷轧1650',
    '1850冷轧': '冷轧1850',
    '1850冷轧车间': '冷轧1850',
    '1850车间': '冷轧1850',
    '冷轧1850': '冷轧1850',
    '冷轧1850车间': '冷轧1850',
    '2050冷轧': '冷轧2050',
    '2050冷轧车间': '冷轧2050',
    '2050车间': '冷轧2050',
    '冷轧2050': '冷轧2050',
    '冷轧2050车间': '冷轧2050',
}

NO_TERMINAL_WORKSHOP_NAMES = {'铸锭', '铸二', '铸三', '热轧', '淬火车间'}


def is_active_production_workshop_code(code: str | None) -> bool:
    return str(code or '').strip().upper() in ACTIVE_PRODUCTION_WORKSHOP_CODE_SET


def normalize_workshop_name(value: Any) -> str:
    name = str(value or '').strip()
    if not name:
        return ''
    return WORKSHOP_NAME_ALIASES.get(name, name)


def workshop_name_query_tokens(value: Any) -> set[str]:
    raw = str(value or '').strip()
    canonical = normalize_workshop_name(raw)
    tokens = {token for token in (raw, canonical) if token}
    tokens.update(alias for alias, name in WORKSHOP_NAME_ALIASES.items() if name == canonical)
    return tokens


def is_active_production_workshop_name(name: str | None) -> bool:
    return normalize_workshop_name(name) in ACTIVE_PRODUCTION_WORKSHOP_NAME_SET


def get_workshop_data_source_policy(value: Any) -> dict[str, Any]:
    name = normalize_workshop_name(value)
    return {
        'workshop_name': name,
        'has_terminal': name not in NO_TERMINAL_WORKSHOP_NAMES,
        'primary_source': 'mes',
        'supplement_window_start': '09:30' if name in NO_TERMINAL_WORKSHOP_NAMES else None,
    }


def filter_active_production_workshops(workshops: list[Any]) -> list[Any]:
    production_workshops: list[Any] = []
    for workshop in workshops:
        code = str(getattr(workshop, 'code', '') or '').strip().upper()
        name = getattr(workshop, 'name', None)
        if is_active_production_workshop_code(code) or is_active_production_workshop_name(name):
            production_workshops.append(workshop)
    return production_workshops
