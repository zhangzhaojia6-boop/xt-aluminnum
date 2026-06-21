from __future__ import annotations

from datetime import date
from importlib import import_module
from typing import Any


BUSINESS_DATE = date(2026, 6, 21)


def _service():
    return import_module('app.services.hermes_day1_report_service')


def _values() -> dict[str, Any]:
    prefixes = (
        'cast_roll',
        'foundry',
        'hot_roll',
        'cold_1650',
        'cold_1850',
        'cold_2050',
        'online_anneal',
        'straightening',
        'finishing',
        'shearing',
        'coating',
        'recovery',
    )
    values: dict[str, Any] = {}
    for index, prefix in enumerate(prefixes, start=1):
        values[f'{prefix}_daily'] = index * 10
        values[f'{prefix}_month'] = index * 100
        values[f'{prefix}_electricity_per_ton_daily'] = index + 0.1
        values[f'{prefix}_electricity_per_ton_month'] = index + 0.2
    values['hot_roll_gas_per_ton_daily'] = 29.8
    values['hot_roll_gas_per_ton_month'] = 26.7
    return values


def _sources(
    *,
    status: str = 'ready',
    text: str | None = '6月21日，车间总产量日合计366吨。',
    field_match_rate: float | None = 98.5,
    audit_match_rate: float | None = 0.99,
) -> dict[str, Any]:
    values = _values()
    alignment = {} if field_match_rate is None else {'field_match_rate': field_match_rate}
    return {
        'trace_id': 'trace-day1-message-001',
        'template_daily_report': {
            'status': status,
            'text': text,
            'missing_fields': [] if status == 'ready' else ['total_output_daily'],
            'conflicts': [],
            'facts': {
                'values': values,
                'sources': {key: {'source_type': '数据中枢 facts'} for key in values},
            },
        },
        'audit_run': {
            'status': 'completed',
            'match_rate': audit_match_rate,
            'source_status': {'mes': 'ok', 'hub': 'ok'},
            'source_errors': {},
            'diffs': {},
            'suggested_actions': [],
        },
        'output_skill_alignment': alignment,
        'dingtalk_evidence': [],
        'dingtalk_messages': [],
        'rag': {'answer': None, 'citations': []},
        'historical_reports': [],
    }


def test_dingtalk_first_message_contains_date_status_match_judgment_and_trace_id() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(field_match_rate=96.5),
    )

    first = result['dingtalk_messages'][0]
    assert '6月21日' in first
    assert '状态：已对齐' in first
    assert '字段匹配率：96.5%' in first
    assert 'Hermes判断' in first
    assert 'trace-day1-message-001' in first


def test_dingtalk_review_label_is_used_when_match_rate_low_or_report_blocked() -> None:
    service = _service()

    low_match = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(field_match_rate=94.9),
    )
    blocked = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(status='blocked', text=None, field_match_rate=100.0),
    )

    assert '状态：需复核' in low_match['dingtalk_messages'][0]
    assert '状态：已对齐' not in low_match['dingtalk_messages'][0]
    assert '状态：需复核' in blocked['dingtalk_messages'][0]
    assert '状态：已对齐' not in blocked['dingtalk_messages'][0]


def test_dingtalk_field_match_rate_falls_back_to_audit_match_rate_percent() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(field_match_rate=None, audit_match_rate=0.975),
    )

    assert '字段匹配率：97.5%' in result['dingtalk_messages'][0]
    assert '状态：已对齐' in result['dingtalk_messages'][0]


def test_dingtalk_missing_field_match_rate_displays_placeholder() -> None:
    service = _service()

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(field_match_rate=None, audit_match_rate=None),
    )

    assert '字段匹配率：暂无' in result['dingtalk_messages'][0]
    assert '状态：需复核' in result['dingtalk_messages'][0]


def test_long_dingtalk_output_splits_cleanly_without_engineering_artifacts() -> None:
    service = _service()
    long_formal_text = '\n\n'.join(
        f'正式日报长段落{index}：' + '生产数据核验完成，字段来源清楚。' * 18
        for index in range(18)
    )

    result = service.build_day1_three_part_report(
        business_date=BUSINESS_DATE,
        sources=_sources(text=long_formal_text, field_match_rate=98.0),
    )

    messages = result['dingtalk_messages']
    assert len(messages) > 1
    assert all(message.startswith(f'[{index}/{len(messages)}]') for index, message in enumerate(messages, start=1))
    assert all(len(message) <= 3500 for message in messages)
    answer = result['dingtalk_answer']
    for artifact in ('None', 'null', '[]'):
        assert artifact not in answer
    for title in ('【铸轧分厂】', '【2050车间】', '【回收车间】'):
        containing = [message for message in messages if title in message]
        assert len(containing) == 1
        assert 'Hermes判断' in containing[0]
