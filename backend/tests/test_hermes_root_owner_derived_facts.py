from __future__ import annotations

from datetime import date

import pytest

from app.services import hermes_root_owner_derived_facts as derived
from app.services.hermes_20_question_acceptance import answer_is_confirmed
from app.services.hermes_20_question_runner import _build_fact_answer
from app.services.hermes_root_owner_evidence_service import collect_root_owner_evidence
from app.services.hermes_root_owner_message_service import understand_root_owner_message
from app.services.hermes_root_owner_production_orchestrator import _build_natural_answer

BUSINESS_DATE = date(2026, 11, 7)


def _dingtalk_fact(value, evidence_id: int = 1946) -> dict:
    return {
        "value": value,
        "unit": "吨",
        "source_type": "dingtalk_supplement",
        "source_ref": {
            "source_key": "dingtalk_group_file",
            "evidence_id": evidence_id,
            "trace_id": f"msg-{evidence_id}",
            "business_date": "2026-11-07",
        },
    }


def _hub_payload() -> dict:
    return {
        "status": "blocked",
        "facts": {
            "total_output_daily": {"value": 282.65, "evidence_status": "confirmed", "source_type": "mes_packaging_output"},
            "wip_total": {"value": 1192.0, "evidence_status": "confirmed", "source_type": "mes_wip_total_snapshot"},
            "shipment_daily": {
                "value": 169.12,
                "evidence_status": "needs_evidence",
                "evidence_gaps": ["missing_trace_id"],
                "source_type": "mes_delivery_records",
            },
            "daily_input_weight": _dingtalk_fact(530, 1950),
            "daily_yield_rate": {**_dingtalk_fact(85.73), "unit": "%"},
        },
        "missing_fields": ["total_electricity_kwh", "cost_per_ton", "energy_1", "energy_2"],
        "conflicts": [],
        "fact_closure": {"status": "blocked"},
        "gap_plan": {
            "status": "needs_action",
            "item_count": 4,
            "summary": {"by_group": {"cost": 1, "energy": 3}},
            "items": [
                {"field": "total_electricity_kwh", "group": "energy", "next_step": "优先由电工扫码补录或提交钉钉能耗表。"},
                {"field": "cost_per_ton", "group": "cost", "next_step": "成本依赖电费气费，先补能耗。"},
            ],
        },
    }


def _turn(text: str, payload: dict | None = None, db=None, default: date = BUSINESS_DATE):
    plan = understand_root_owner_message(text, default_business_date=default)
    decision = collect_root_owner_evidence(
        db,
        message_plan=plan,
        trace_id="trace-1",
        dingtalk_reader=lambda **_kwargs: [],
        hub_reader=lambda **_kwargs: payload if payload is not None else _hub_payload(),
    )
    answer = _build_natural_answer(plan=plan, decision=decision)
    evidence = {
        "primary": None,
        "candidate_facts": [
            {
                "source_key": item.source_key,
                "source_type": item.source_type,
                "status": item.status,
                "value": item.value,
                "trace_ref": dict(item.trace_ref),
            }
            for item in decision.candidates
        ],
        "missing_sources": decision.missing_sources,
        "conflicts": list(decision.conflicts),
        "trace": decision.trace,
    }
    recognition = {"metric_keys": list(plan.metric_keys)}
    records = _build_fact_answer(question_id=1, turn_trace_id="trace-1", recognition=recognition, evidence=evidence)
    return decision, answer, records


def test_specialist_evidence_lists_every_adopted_dingtalk_number_as_a_confirmed_fact() -> None:
    decision, answer, records = _turn("哪些数字来自专项责任人钉钉证据？")

    assert decision.primary.source_key == "dingtalk_group_file"
    assert records[0]["status"] == "confirmed"
    assert answer_is_confirmed(records[0])
    assert "投料量 530 吨（证据 1950）" in answer
    assert "日成品率 85.73 %（证据 1946）" in answer
    assert "282.65" not in answer


def test_specialist_evidence_is_missing_when_nothing_was_adopted_from_dingtalk() -> None:
    payload = {**_hub_payload(), "facts": {"total_output_daily": {"value": 1, "source_type": "mes_packaging_output"}}}

    decision, _answer, records = _turn("哪些数字来自专项责任人钉钉证据？", payload)

    assert decision.primary is None
    assert records[0]["status"] == "missing"


def test_source_gap_question_names_groups_and_count_as_a_candidate() -> None:
    _decision, answer, records = _turn("哪些指标缺少正式来源？")

    assert records[0]["status"] == "candidate"
    assert records[0]["reason"] == "missing_formal_source_count:4"
    assert records[0]["action"] == "优先由电工扫码补录或提交钉钉能耗表。"
    assert "共 4 项" in answer
    assert "能源 3 项" in answer
    assert "成本 1 项" in answer


def test_least_trusted_question_ranks_missing_above_unread_values() -> None:
    _decision, answer, records = _turn("今天哪个关键数字最不可信？")

    assert records[0]["status"] == "candidate"
    assert "全厂高压总用电量（没有来源）" in answer
    assert "全厂总产量（" not in answer


def test_least_trusted_question_flags_a_key_number_with_read_gaps() -> None:
    payload = _hub_payload()
    payload["missing_fields"] = []
    payload["facts"]["total_electricity_kwh"] = {"value": 1, "source_type": "dingtalk_supplement"}
    payload["facts"]["wip_total"]["evidence_gaps"] = ["missing_trace_id"]

    _decision, answer, _records = _turn("今天哪个关键数字最不可信？", payload)

    assert "在制料总量（有值但缺读取证据）" in answer


def test_readiness_says_no_while_fields_are_missing_and_keeps_the_127_denominator() -> None:
    _decision, answer, records = _turn("今天日报能不能自动生成？还缺什么？")

    assert records[0]["status"] == "candidate"
    assert records[0]["value"]["can_auto_generate"] is False
    assert "不能自动生成" in answer
    assert "127 项里缺 4 项" in answer


def test_readiness_says_yes_only_when_closure_passes_and_nothing_is_missing() -> None:
    payload = {**_hub_payload(), "missing_fields": [], "fact_closure": {"status": "pass"}, "gap_plan": {}}

    _decision, answer, records = _turn("今天日报能不能自动生成？还缺什么？", payload)

    assert records[0]["value"]["can_auto_generate"] is True
    assert "可以自动生成" in answer


def test_annual_total_is_a_candidate_and_says_what_it_does_not_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        derived,
        "query_factory_packaging_output_by_date",
        lambda _db, start, end: {date(2026, 6, 1): 100.0, date(2026, 11, 7): 282.65},
    )

    _decision, answer, records = _turn("今年累计产量是多少？", db=object())

    assert records[0]["status"] == "candidate"
    assert records[0]["value"] == 382.65
    assert records[0]["reason"] == "annual_coverage_incomplete:2/311"
    assert "382.65 吨" in answer
    assert "不是完整年累计" in answer
    assert "2026-06-01" in answer


def test_annual_total_without_any_output_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(derived, "query_factory_packaging_output_by_date", lambda _db, start, end: {})

    decision, _answer, records = _turn("今年累计产量是多少？", db=object())

    assert decision.primary is None
    assert records[0]["status"] == "missing"


def test_missing_answer_names_the_metric_and_hides_internal_source_codes() -> None:
    payload = {**_hub_payload(), "facts": {}}

    _decision, answer, _records = _turn("今天成本折算元/吨是多少？", payload)

    assert "吨成本" in answer
    assert "data_hub_projection" not in answer
    assert "dingtalk_group_content" not in answer
    assert "数据中枢投影" in answer


def test_output_and_inbound_question_states_the_gap_and_why_they_differ() -> None:
    payload = _hub_payload()
    payload["facts"]["finished_inbound_daily"] = {"value": 261.72, "source_type": "mes_stock_records"}

    _decision, answer, _records = _turn("产量和入库为什么对不上？", payload)

    assert "相差 20.93 吨" in answer
    assert "包装" in answer


def test_wip_answer_says_when_the_number_was_captured() -> None:
    payload = _hub_payload()
    at = "2026-11-08T08:02:06.680710+08:00"
    payload["facts"]["wip_total"] = {
        "value": 1192.0,
        "unit": "吨",
        "source_type": "mes_wip_total_snapshot",
        "source_ref": {"business_window": f"{at}/{at}", "trace_id": "projection-read:mes_wip_total_snapshots:58:13"},
    }

    _decision, answer, _records = _turn("今天在制料是多少？", payload)

    assert "取自 11-08 08:02 抓取" in answer
