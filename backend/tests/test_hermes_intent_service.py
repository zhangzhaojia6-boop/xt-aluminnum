from __future__ import annotations

from app.services.hermes_intent_service import parse_hermes_intent


def test_parse_daily_report_intent_from_flexible_text() -> None:
    intent = parse_hermes_intent('6月19日按最终口径重新来一版', default_year=2026)

    assert intent['intent'] == 'daily_report'
    assert intent['business_date'] == '2026-06-19'
    assert intent['audience'] == 'root_owner'
    assert intent['mode'] == 'final'
    assert intent['requested_corrections'] == []


def test_parse_daily_report_intent_without_date_keeps_intent_and_requires_date_resolution() -> None:
    intent = parse_hermes_intent('按最终口径重新来一版', default_year=2026)

    assert intent['intent'] == 'daily_report'
    assert intent['business_date'] is None
    assert intent['audience'] == 'root_owner'
    assert intent['mode'] == 'final'
    assert intent['correction_policy'] == 'none'
    assert intent['requested_corrections'] == []


def test_parse_direct_root_owner_correction_intent() -> None:
    intent = parse_hermes_intent('6月19日车间总产量改成366吨，直接按这个发。', default_year=2026)

    assert intent['intent'] == 'daily_report'
    assert intent['business_date'] == '2026-06-19'
    assert intent['correction_policy'] == 'root_owner_direct'
    assert intent['requested_corrections'] == [
        {
            'field_name': 'total_output_daily',
            'value': 366.0,
            'unit': '吨',
            'reason': 'root_owner 自然语言修正',
            'requires_confirmation': False,
        }
    ]


def test_parse_ambiguous_correction_requires_confirmation() -> None:
    intent = parse_hermes_intent('6月19日车间总产量改成366吨', default_year=2026)

    assert intent['intent'] == 'daily_report'
    assert intent['correction_policy'] == 'root_owner_confirm'
    assert intent['requested_corrections'] == [
        {
            'field_name': 'total_output_daily',
            'value': 366.0,
            'unit': '吨',
            'reason': 'root_owner 自然语言修正',
            'requires_confirmation': True,
        }
    ]


def test_parse_direct_gas_correction_intent() -> None:
    intent = parse_hermes_intent('6月19日天然气改成50578方，直接按这个发', default_year=2026)

    assert intent['intent'] == 'daily_report'
    assert intent['correction_policy'] == 'root_owner_direct'
    assert intent['requested_corrections'] == [
        {
            'field_name': 'total_gas_m3',
            'value': 50578.0,
            'unit': 'm³',
            'reason': 'root_owner 自然语言修正',
            'requires_confirmation': False,
        }
    ]


def test_parse_unknown_chat_without_date_or_daily_report_intent() -> None:
    intent = parse_hermes_intent('今天辛苦了，先休息一下', default_year=2026)

    assert intent['intent'] == 'unknown'
    assert intent['business_date'] is None
    assert intent['raw_text'] == '今天辛苦了，先休息一下'
    assert intent['requested_corrections'] == []
