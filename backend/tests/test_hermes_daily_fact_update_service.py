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


def test_structured_fact_updates_preserve_verified_source_ref() -> None:
    source_ref = {
        "parser": "plan_contract_message_v1",
        "business_date": "2026-07-11",
        "content_sha256": "a" * 64,
        "matched_segments": {
            "remaining_contract": {
                "text": "总余合同量2765吨",
                "start": 64,
                "end": 75,
            }
        },
        "components": {
            "2050_input": 463,
            "1850_input": 0,
            "external_processing": 62,
            "medium_plate": 0,
        },
    }

    candidates = extract_daily_fact_update_candidates(
        {
            "trace_id": "verified-contract-trace",
            "payload": {
                "fact_updates": {
                    "daily_input_weight": {
                        "value": 525,
                        "unit": "吨",
                        "confidence": 0.99,
                        "source_ref": source_ref,
                    }
                }
            },
        }
    )

    assert candidates[0]["source_ref"] == source_ref


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


@pytest.mark.parametrize(
    "text",
    [
        "今日总产量371吨，包装产量360吨",
        "今日总产量371吨；包装360吨",
        "今日总产量371吨，较昨日350吨增长",
    ],
)
def test_plain_text_accepts_daily_output_inside_mixed_messages(text: str) -> None:
    candidates = extract_daily_fact_update_candidates({"recognized_text": text})

    assert len(candidates) == 1
    assert candidates[0]["field"] == "total_output_daily"
    assert candidates[0]["value"] == 371
    assert candidates[0]["unit"] == "吨"


def test_payload_attachment_text_produces_candidates_without_top_level_text() -> None:
    candidates = extract_daily_fact_update_candidates(
        {
            "id": "evidence-file-1",
            "payload": {
                "file_name": "6月19日日报.xlsx",
                "attachments": [
                    {
                        "parsed_text": (
                            "6月19日生产日报\n"
                            "车间总产量日合计371吨。\n"
                            "全厂高压总用电量18420度。"
                        )
                    }
                ],
            },
        }
    )

    assert [(item["field"], item["value"], item["unit"]) for item in candidates] == [
        ("total_output_daily", 371, "吨"),
        ("total_electricity_kwh", 18420, "度"),
    ]
    assert candidates[0]["trace_id"] == "evidence-file-1"
    assert "6月19日生产日报" in candidates[0]["raw_text"]


def test_unknown_text_returns_empty_candidates() -> None:
    assert extract_daily_fact_update_candidates({"recognized_text": "辛苦了，收到"}) == []


def test_plan_contract_message_produces_component_sum_and_remaining_contract_candidates() -> None:
    text = (
        "投料量：2050投料463吨 1850投料0吨 外加工62吨 中厚板0吨 "
        "当天合同443吨 热轧436吨 总余合同量2765吨"
    )

    candidates = extract_daily_fact_update_candidates(
        {"trace_id": "plan-contract-trace", "recognized_text": text}
    )

    assert [(item["field"], item["value"], item["unit"]) for item in candidates] == [
        ("daily_input_weight", 525, "吨"),
        ("remaining_contract_weight", 2765, "吨"),
    ]
    assert all(item["trace_id"] == "plan-contract-trace" for item in candidates)
    assert all(item["source_ref"]["parser"] == "plan_contract_message_v1" for item in candidates)


def test_incomplete_plan_contract_message_is_not_partially_guessed() -> None:
    text = "投料量：2050投料463吨 1850投料0吨 外加工62吨 总余合同量2765吨"

    assert extract_daily_fact_update_candidates({"recognized_text": text}) == []


@pytest.mark.parametrize(
    "text",
    [
        "本月累计产量371吨",
        "昨日总产量371吨",
        "今日包装产量371吨",
    ],
)
def test_plain_text_rejects_non_daily_final_output_markers(text: str) -> None:
    assert extract_daily_fact_update_candidates({"recognized_text": text}) == []


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
