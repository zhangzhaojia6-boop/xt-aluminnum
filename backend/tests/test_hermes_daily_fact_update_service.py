from __future__ import annotations

import pytest

from app.services.hermes_daily_fact_update_service import (
    extract_daily_fact_update_candidates,
)


def test_structured_fact_updates_become_candidates() -> None:
    candidates = extract_daily_fact_update_candidates(
        {
            "trace_id": "trace-root",
            "recognized_text": "6月19日高压电 133201 度",
            "payload": {
                "trace_id": "trace-payload",
                "fact_updates": {
                    "total_electricity_kwh": {
                        "value": 133201,
                        "unit": "度",
                        "reason": "能源负责人确认",
                    }
                },
            },
        }
    )

    assert candidates == [
        {
            "field": "total_electricity_kwh",
            "value": 133201,
            "unit": "度",
            "confidence": 0.95,
            "source": "dingtalk_supplement",
            "trace_id": "trace-payload",
            "raw_text": "6月19日高压电 133201 度",
            "reason": "能源负责人确认",
        }
    ]


@pytest.mark.parametrize(
    ("text", "field", "value", "unit"),
    [
        ("今日总产量371吨", "total_output_daily", 371, "吨"),
        ("成品入库 365.2 t", "finished_inbound_daily", 365.2, "吨"),
        ("昨日用电 18420 度", "total_electricity_kwh", 18420, "度"),
        ("在制合计1136吨", "wip_total", 1136, "吨"),
        ("成品率98.4%", "daily_yield_rate", 98.4, "%"),
    ],
)
def test_plain_chinese_examples_produce_expected_candidates(
    text: str,
    field: str,
    value: int | float,
    unit: str,
) -> None:
    candidates = extract_daily_fact_update_candidates(
        {"id": "evidence-1", "recognized_text": text}
    )

    assert len(candidates) == 1
    assert candidates[0]["field"] == field
    assert candidates[0]["value"] == value
    assert candidates[0]["unit"] == unit
    assert candidates[0]["source"] == "dingtalk_supplement"
    assert candidates[0]["trace_id"] == "evidence-1"
    assert candidates[0]["raw_text"] == text


def test_unknown_text_returns_empty_candidates() -> None:
    assert extract_daily_fact_update_candidates({"recognized_text": "辛苦了，收到"}) == []


@pytest.mark.parametrize(
    "evidence",
    [
        {},
        {"payload": "not-a-dict", "recognized_text": "今日总产量371吨"},
        {"payload": "not-a-dict", "recognized_text": object()},
        {"payload": {"fact_updates": "bad"}, "text": "今日总产量371吨"},
    ],
)
def test_malformed_payload_does_not_throw_and_returns_empty_candidates(
    evidence: object,
) -> None:
    assert extract_daily_fact_update_candidates(evidence) == []  # type: ignore[arg-type]
