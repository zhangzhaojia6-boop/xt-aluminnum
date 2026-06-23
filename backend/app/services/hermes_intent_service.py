from __future__ import annotations

from datetime import date
import re
from typing import Any


CorrectionPattern = tuple[str, re.Pattern[str], str]


FIELD_PATTERNS: tuple[CorrectionPattern, ...] = (
    (
        'total_output_daily',
        re.compile(r'(?:车间总产量|总产量|产量日合计)\s*(?:改成|改为|按|用)\s*(?P<value>\d+(?:\.\d+)?)\s*吨'),
        '吨',
    ),
    (
        'total_gas_m3',
        re.compile(r'(?:天然气|用气|总气量|共计)\s*(?:改成|改为|按|用)\s*(?P<value>\d+(?:\.\d+)?)\s*(?:m³|方|立方)'),
        'm³',
    ),
    (
        'total_electricity_kwh',
        re.compile(r'(?:用电|总用电|全厂高压总用电量)\s*(?:改成|改为|按|用)\s*(?P<value>\d+(?:\.\d+)?)\s*(?:度|kwh|KWH)'),
        '度',
    ),
)
DIRECT_MARKERS = ('直接', '不用确认', '免确认', '按这个发')
DAILY_REPORT_MARKERS = ('日报', '来一版', '按这个发', '最终口径')


def parse_hermes_intent(text: str, *, default_year: int) -> dict[str, Any]:
    clean = str(text or '').strip()
    business_date = _extract_business_date(clean, default_year=default_year)
    requested_corrections = _extract_corrections(clean)
    is_direct = any(marker in clean for marker in DIRECT_MARKERS)
    has_daily_report_signal = (
        any(marker in clean for marker in DAILY_REPORT_MARKERS)
        or bool(requested_corrections)
    )

    if not has_daily_report_signal:
        return {
            'intent': 'unknown',
            'business_date': business_date.isoformat() if business_date else None,
            'raw_text': clean,
            'requested_corrections': requested_corrections,
        }

    for item in requested_corrections:
        item['requires_confirmation'] = not is_direct

    correction_policy = 'none'
    if requested_corrections:
        correction_policy = 'root_owner_direct' if is_direct else 'root_owner_confirm'

    return {
        'intent': 'daily_report',
        'business_date': business_date.isoformat() if business_date else None,
        'audience': 'root_owner',
        'mode': 'final',
        'evidence_policy': 'include_dingtalk_supplement',
        'correction_policy': correction_policy,
        'requested_corrections': requested_corrections,
        'raw_text': clean,
    }


def _extract_corrections(text: str) -> list[dict[str, Any]]:
    corrections: list[dict[str, Any]] = []
    for field_name, pattern, unit in FIELD_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        corrections.append(
            {
                'field_name': field_name,
                'value': float(match.group('value')),
                'unit': unit,
                'reason': 'root_owner 自然语言修正',
                'requires_confirmation': True,
            }
        )
    return corrections


def _extract_business_date(text: str, *, default_year: int) -> date | None:
    full_match = re.search(r'(?P<year>\d{4})[-._](?P<month>\d{1,2})[-._](?P<day>\d{1,2})', text)
    if full_match:
        return _build_date(
            year=int(full_match.group('year')),
            month=int(full_match.group('month')),
            day=int(full_match.group('day')),
        )

    chinese_match = re.search(r'(?P<month>\d{1,2})月(?P<day>\d{1,2})日', text)
    if chinese_match:
        return _build_date(
            year=default_year,
            month=int(chinese_match.group('month')),
            day=int(chinese_match.group('day')),
        )

    return None


def _build_date(*, year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
