from __future__ import annotations

import math
from datetime import date

import pytest

from app.services.hermes_20_question_acceptance import (
    AcceptanceTurnSnapshot,
    _unit_matches_field,
    answer_is_confirmed,
    build_20_question_catalog,
    evaluate_acceptance_summary,
    evaluate_answers,
    evaluate_question_snapshot,
    render_acceptance_report,
)
from app.services.hermes_root_owner_message_service import understand_root_owner_message


_CRITICAL_SOURCES = {
    "total_output_daily": "mes_readonly",
    "finished_inbound_daily": "mes_readonly",
    "wip_total": "mes_readonly",
    "total_electricity_kwh": "dingtalk_group_content",
    "daily_yield_rate": "dingtalk_group_content",
}
_CRITICAL_FACT_METADATA = {
    "total_output_daily": ("mes_packaging_output", "mes_workshop_process_records", "吨"),
    "finished_inbound_daily": ("mes_stock_records", "mes_stock_records", "吨"),
    "wip_total": ("mes_wip_total_snapshot", "mes_wip_total_snapshots", "吨"),
    "total_electricity_kwh": ("dingtalk_supplement", None, "kWh"),
    "daily_yield_rate": ("dingtalk_supplement", None, "%"),
}
_ORIGINAL_APPROVED_QUESTIONS = (
    "今天全厂总产量是多少？",
    "今天各车间产量分别是多少？",
    "今天成品入库多少？",
    "今天投料量是多少？",
    "今天高压总用电量是多少？",
    "今天全厂用气量是多少？",
    "今天吨电耗是多少？分母是什么？",
    "今天成品率是多少？分子分母是什么？",
    "今天成本折算元/吨是多少？",
    "今天在制料是多少？",
    "现在总余合同量是多少？",
    "本月累计产量是多少？",
    "今年累计产量是多少？",
    "今天有哪些异常说明？",
    "哪些数字来自专项责任人钉钉证据？",
    "今天哪个关键数字最不可信？",
    "产量和入库为什么对不上？",
    "电耗升高可能由什么造成？",
    "哪些指标缺少正式来源？",
    "今天日报能不能自动生成？还缺什么？",
)
_REQUIRED_NATURAL_UTTERANCES = {
    "昨天一共出了多少？",
    "那入库呢？",
    "电用了多少度，和群文件对得上吗",
    "成品率咋这么高，帮我查下是不是口径错了",
    "接着上一个问题，把证据编号给我",
}


def _fact_records(question_id: int) -> list[dict[str, object]]:
    question = {item.question_id: item for item in build_20_question_catalog()}[question_id]
    records: list[dict[str, object]] = []
    for field in question.metric_keys:
        if field in _CRITICAL_SOURCES:
            source_type, source_ref, unit = _CRITICAL_FACT_METADATA[field]
            trace_id = f"source-trace-q{question_id}-{field}"
            if source_ref is not None:
                trace_id = f"projection-read:{source_ref}:{question_id}:1"
                source_reference = {
                    "source_ref": source_ref,
                    "business_date": "2026-06-27",
                    "business_window": "2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00",
                    "unit": unit,
                    "metric_contract_version": "2026-07-11",
                    "row_count": 1,
                    "latest_row_id": question_id,
                    "trace_id": trace_id,
                }
                if field == "total_output_daily":
                    source_reference["source_table"] = "MES_ProductProcessRecord"
                elif field == "finished_inbound_daily":
                    source_reference["source_table"] = "WMS_InStockDetail"
            else:
                source_reference = {
                    "source_key": _CRITICAL_SOURCES[field],
                    "business_date": "2026-06-27",
                    "evidence_id": question_id,
                    "trace_id": trace_id,
                }
            records.append(
                {
                    "question_id": question_id,
                    "field": field,
                    "status": "confirmed",
                    "value": 1,
                    "source": _CRITICAL_SOURCES[field],
                    "source_key": _CRITICAL_SOURCES[field],
                    "source_type": source_type,
                    "source_ref": source_reference,
                    "trace_id": trace_id,
                    "business_date": "2026-06-27",
                    "business_window": "2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00",
                    "unit": unit,
                    "metric_contract_version": "2026-07-11",
                }
            )
        else:
            records.append(
                {
                    "question_id": question_id,
                    "field": field,
                    "status": "missing",
                    "value": None,
                    "source": None,
                    "trace_id": None,
                    "business_date": "2026-06-27",
                    "reason": f"{field} 的当日正式来源没有返回对应字段",
                    "action": f"请对应责任人补录 {field} 的当日来源证据",
                }
            )
    return records


def _passing_snapshot(question_id: int, *, answer: str | None = None) -> AcceptanceTurnSnapshot:
    catalog = {item.question_id: item for item in build_20_question_catalog()}
    question = catalog[question_id]
    snapshot = AcceptanceTurnSnapshot(
        question_id=question.question_id,
        trace_id=f"trace-q{question_id}",
        status="answered",
        answer=answer
        or "鑫泰铝业智能大脑回答：结论已确认。来源：钉钉群聊天内容、MES/WMS 只读链路。状态：confirmed。追踪编号：trace-q。",
        recognition={
            "domain": question.domain,
            "metric_keys": list(question.metric_keys),
            "business_date": "2026-06-27",
            "needs_clarification": False,
        },
        evidence={
            "primary_source": "dingtalk_group_chat",
            "candidate_sources": ["dingtalk_group_chat", "mes_readonly", "data_hub_projection"],
            "missing_sources": [],
            "conflicts": [],
            "trace": {
                "source_order": ["dingtalk_group_chat", "mes_readonly", "data_hub_projection"],
                "source_status": {
                    "dingtalk_group_content": {"status": "ok"},
                    "mes_readonly": {"status": "ok"},
                    "data_hub_projection": {"status": "ok"},
                },
            },
        },
        dispatch={
            "status": "sent",
            "detail": "ok",
            "outbox_message_id": 100 + question_id,
            "log_status": "sent",
            "channel_type": "dingtalk_group",
        },
        source_health={
            "energy_readonly": {
                "source_key": "energy_readonly",
                "domain": "energy",
                "status": "disabled",
                "readonly": True,
                "last_success_at": None,
                "failure_reason": "source_not_configured",
            }
        },
        required_source_health=(),
    )
    snapshot.fact_answer = _fact_records(question_id)
    return snapshot


def _valid_answers() -> list[dict[str, object]]:
    return [record for question in build_20_question_catalog() for record in _fact_records(question.question_id)]


def _critical_record(answers: list[dict[str, object]], field: str) -> dict[str, object]:
    return next(record for record in answers if record.get("field") == field)


def _evaluate_answers(answers: list[dict[str, object]]) -> dict[str, object]:
    return evaluate_answers(answers)


def test_catalog_has_exactly_20_approved_questions() -> None:
    catalog = build_20_question_catalog()

    assert len(catalog) == 20
    assert catalog[0].question_id == 1
    assert tuple(item.question for item in catalog) == _ORIGINAL_APPROVED_QUESTIONS
    execution_utterances = {
        utterance
        for item in catalog
        for utterance in item.execution_utterances
    }
    assert _REQUIRED_NATURAL_UTTERANCES.issubset(execution_utterances)
    trust_questions = [item for item in catalog if item.question == "今天哪个关键数字最不可信？"]
    assert len(trust_questions) == 1
    assert trust_questions[0].metric_keys == ("source_status",)
    assert trust_questions[0].domain == "anomaly"
    electricity_anomaly_questions = [
        item for item in catalog if item.question == "电耗升高可能由什么造成？"
    ]
    assert len(electricity_anomaly_questions) == 1
    assert electricity_anomaly_questions[0].metric_keys == (
        "electricity_per_ton",
        "anomaly_explanation_daily",
    )
    assert electricity_anomaly_questions[0].domain == "energy"
    follow_up = next(
        item
        for item in catalog
        if "接着上一个问题，把证据编号给我" in item.follow_up_utterances
    )
    assert follow_up == electricity_anomaly_questions[0]
    assert follow_up.requires_dingtalk is True
    metric_coverage = {metric for item in catalog for metric in item.metric_keys}
    assert {
        "total_output_daily",
        "workshop_output_daily",
        "finished_inbound_daily",
        "daily_input_weight",
        "total_electricity_kwh",
        "total_gas_m3",
        "electricity_per_ton",
        "daily_yield_rate",
        "cost_per_ton",
        "wip_total",
        "remaining_contract_weight",
        "monthly_total_output",
        "annual_total_output",
        "anomaly_explanation_daily",
        "dingtalk_specialist_evidence",
        "source_status",
        "daily_report_readiness",
    }.issubset(metric_coverage)
    assert catalog[-1].question == "今天日报能不能自动生成？还缺什么？"


def test_twenty_missing_answers_fail_fact_acceptance() -> None:
    answers = []
    for question in build_20_question_catalog():
        for field in question.metric_keys:
            answers.append(
                {
                    "question_id": question.question_id,
                    "field": field,
                    "status": "missing",
                    "value": None,
                    "source": None,
                    "trace_id": None,
                    "business_date": "2026-06-27",
                    "reason": f"{field} 的当前业务日来源没有返回值",
                    "action": f"请对应责任人补录 {field} 的当前业务日证据",
                }
            )

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert result["confirmed_count"] == 0
    assert result["critical_coverage"] == {field: False for field in _CRITICAL_SOURCES}


@pytest.mark.parametrize("field", sorted(_CRITICAL_SOURCES))
@pytest.mark.parametrize(
    ("key", "bad_value", "reason_part"),
    (
        ("value", None, "value"),
        ("source_key", None, "source"),
        ("trace_id", None, "trace"),
        ("business_date", None, "business"),
        ("source_key", "rag", "source"),
        ("source_key", "output_skill", "source"),
        ("source_key", "historical_report", "source"),
        ("source_key", "computed", "source"),
        ("value", math.nan, "finite"),
        ("value", math.inf, "finite"),
        ("value", "NaN", "finite"),
        ("value", "Infinity", "finite"),
        ("value", "not-a-number", "finite"),
    ),
)
def test_each_critical_field_rejects_missing_or_fake_fact_parts(
    field: str,
    key: str,
    bad_value: object,
    reason_part: str,
) -> None:
    answers = _valid_answers()
    for record in (item for item in answers if item.get("field") == field):
        record[key] = bad_value
        if key == "business_date":
            record["business_window"] = None

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert result["critical_coverage"][field] is False
    assert any(
        failure.get("field") == field and reason_part in str(failure.get("reason"))
        for failure in result["failures"]
    )


def test_zero_is_a_valid_confirmed_fact_value() -> None:
    answers = _valid_answers()
    _critical_record(answers, "total_electricity_kwh")["value"] = 0

    result = _evaluate_answers(answers)

    assert result["passed"] is True
    assert result["critical_coverage"]["total_electricity_kwh"] is True


@pytest.mark.parametrize(
    ("key", "reason_part"),
    (
        ("status", "critical_field_not_confirmed"),
        ("value", "value"),
        ("source_key", "source_key"),
        ("source_type", "source_type"),
        ("source_ref", "source_ref"),
        ("business_date", "business_date"),
        ("business_window", "business_window"),
        ("unit", "unit"),
        ("metric_contract_version", "metric_contract_version"),
        ("trace_id", "trace_id"),
    ),
)
def test_total_output_confirmed_fact_requires_each_structured_property(
    key: str,
    reason_part: str,
) -> None:
    answers = _valid_answers()
    record = _critical_record(answers, "total_output_daily")
    record[key] = None

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert result["critical_coverage"]["total_output_daily"] is False
    assert any(
        failure.get("field") == "total_output_daily"
        and reason_part in str(failure.get("reason"))
        for failure in result["failures"]
    )


@pytest.mark.parametrize(
    ("key", "bad_value", "reason_part"),
    (
        ("source_type", "data_hub_projection", "source_type"),
        ("source_ref", {"source_ref": "wrong_table"}, "source_ref"),
        ("business_date", "not-a-date", "business_date"),
        (
            "business_window",
            "2026-06-26T07:50:00+08:00/2026-06-27T07:50:00+08:00",
            "business_window",
        ),
        ("unit", "kWh", "unit"),
        ("metric_contract_version", "2026-01-01", "metric_contract_version"),
    ),
)
def test_total_output_confirmed_fact_rejects_wrong_contract_metadata(
    key: str,
    bad_value: object,
    reason_part: str,
) -> None:
    answers = _valid_answers()
    _critical_record(answers, "total_output_daily")[key] = bad_value

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert any(
        failure.get("field") == "total_output_daily"
        and reason_part in str(failure.get("reason"))
        for failure in result["failures"]
    )


def test_daily_yield_rejects_data_hub_projection_as_confirmed_source() -> None:
    answers = _valid_answers()
    record = _critical_record(answers, "daily_yield_rate")
    record["source_key"] = "data_hub_projection"
    record["source"] = "data_hub_projection"
    record["source_type"] = "data_hub_projection"

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert result["critical_coverage"]["daily_yield_rate"] is False
    assert any(
        failure.get("field") == "daily_yield_rate"
        and "source_type" in str(failure.get("reason"))
        for failure in result["failures"]
    )


def test_daily_yield_rejects_computed_source_type_even_if_contract_lists_it() -> None:
    answers = _valid_answers()
    record = _critical_record(answers, "daily_yield_rate")
    record["source_type"] = "computed_same_basis"

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert result["critical_coverage"]["daily_yield_rate"] is False


@pytest.mark.parametrize(
    ("key", "bad_value", "reason_part"),
    (
        ("source_key", "invented_anything", "source_key"),
        ("source_ref", {"source_ref": "totally_fake_ref"}, "source_ref"),
        ("source_key", "dingtalk_group_content", "source_key"),
    ),
)
def test_total_output_rejects_fake_or_cross_paired_source_identity(
    key: str,
    bad_value: object,
    reason_part: str,
) -> None:
    answers = _valid_answers()
    _critical_record(answers, "total_output_daily")[key] = bad_value

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert any(
        failure.get("field") == "total_output_daily"
        and reason_part in str(failure.get("reason"))
        for failure in result["failures"]
    )


def test_total_output_rejects_source_ref_metadata_that_disagrees_with_primary_fact() -> None:
    answers = _valid_answers()
    record = _critical_record(answers, "total_output_daily")
    record["source_ref"] = {
        **record["source_ref"],
        "business_window": "2026-06-26T07:50:00+08:00/2026-06-27T07:50:00+08:00",
    }

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert any(
        failure.get("field") == "total_output_daily"
        and "business_window" in str(failure.get("reason"))
        for failure in result["failures"]
    )


@pytest.mark.parametrize("value", (math.nan, math.inf, "NaN", "Infinity"))
def test_any_confirmed_fact_rejects_non_finite_value(value: object) -> None:
    assert answer_is_confirmed(
        {
            "field": "workshop_output_daily",
            "status": "confirmed",
            "value": value,
            "source": "mes_readonly",
            "trace_id": "source-trace-workshop",
            "business_date": "2026-06-27",
        }
    ) is False


@pytest.mark.parametrize("value", ("   ", [], {}))
def test_any_confirmed_fact_rejects_empty_value(value: object) -> None:
    assert answer_is_confirmed(
        {
            "field": "dingtalk_specialist_evidence",
            "status": "confirmed",
            "value": value,
            "source": "dingtalk_group_chat",
            "trace_id": "source-trace-evidence",
            "business_date": "2026-06-27",
        }
    ) is False


def test_confirmed_fact_rejects_unit_that_breaks_field_contract() -> None:
    answers = _valid_answers()
    _critical_record(answers, "total_electricity_kwh")["unit"] = "吨"

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert any("unit" in failure["reason"] for failure in result["failures"])


def test_noncritical_confirmed_fact_also_rejects_wrong_known_unit() -> None:
    assert answer_is_confirmed(
        {
            "field": "total_gas_m3",
            "status": "confirmed",
            "value": 1250,
            "source": "dingtalk_group_chat",
            "trace_id": "source-trace-gas",
            "business_date": "2026-06-27",
            "unit": "吨",
        }
    ) is False


@pytest.mark.parametrize("unit", ("kWh/吨", "kWh/t", "度/吨", "千瓦时/吨"))
def test_electricity_per_ton_accepts_only_explicit_per_ton_units(unit: str) -> None:
    assert _unit_matches_field("electricity_per_ton", unit) is True


def test_electricity_per_ton_rejects_plain_degree_unit() -> None:
    assert _unit_matches_field("electricity_per_ton", "度") is False


def test_electricity_per_ton_rejects_invented_source_contract() -> None:
    assert answer_is_confirmed(
        {
            "field": "electricity_per_ton",
            "status": "confirmed",
            "value": 328.5,
            "source_key": "mes_readonly",
            "source_type": "mes_energy_per_ton",
            "source_ref": {"source_ref": "mes_energy_summary"},
            "business_date": "2026-06-27",
            "business_window": "2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00",
            "unit": "kWh/吨",
            "metric_contract_version": "2026-07-11",
            "trace_id": "energy-per-ton-source-trace",
        }
    ) is False


@pytest.mark.parametrize("unit", ("kWh/吨", "度/吨"))
def test_electricity_per_ton_accepts_anchored_basis_fact(unit: str) -> None:
    trace_id = "dingtalk-energy-per-ton-31"
    assert answer_is_confirmed(
        {
            "field": "electricity_per_ton",
            "status": "confirmed",
            "value": 328.5,
            "source_key": "dingtalk_group_content",
            "source_type": "dingtalk_supplement",
            "source_ref": {
                "source_key": "dingtalk_group_content",
                "evidence_id": 31,
                "trace_id": trace_id,
                "business_date": "2026-06-27",
                "numerator_field": "total_electricity_kwh",
                "numerator_evidence_id": 31,
                "denominator_field": "total_output_daily",
                "denominator_evidence_id": 32,
            },
            "business_date": "2026-06-27",
            "business_window": "2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00",
            "unit": unit,
            "metric_contract_version": "2026-07-11",
            "trace_id": trace_id,
        }
    ) is True


@pytest.mark.parametrize("missing_key", ("reason", "action"))
def test_noncritical_missing_answer_requires_specific_reason_and_action(missing_key: str) -> None:
    answers = _valid_answers()
    record = next(item for item in answers if item["field"] == "workshop_output_daily")
    record[missing_key] = ""

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert any(
        failure.get("question_id") == 2 and missing_key in failure["reason"]
        for failure in result["failures"]
    )


@pytest.mark.parametrize("missing_key", ("reason", "action"))
def test_noncritical_conflict_answer_requires_specific_reason_and_action(missing_key: str) -> None:
    answers = _valid_answers()
    record = next(item for item in answers if item["field"] == "workshop_output_daily")
    record["status"] = "conflict"
    record["reason"] = "MES 与钉钉的车间产量不一致"
    record["action"] = "请生产负责人按来源 trace 复核差异字段"
    record[missing_key] = ""

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert any(
        failure.get("question_id") == 2 and missing_key in failure["reason"]
        for failure in result["failures"]
    )


def test_fact_evaluator_requires_complete_twenty_question_coverage() -> None:
    answers = [record for record in _valid_answers() if record["question_id"] != 20]

    result = _evaluate_answers(answers)

    assert result["passed"] is False
    assert any(failure["reason"] == "question_coverage_incomplete" for failure in result["failures"])


def test_snapshot_fact_gate_ignores_extra_recognized_candidates_but_checks_requested_field() -> None:
    question = build_20_question_catalog()[1]
    snapshot = _passing_snapshot(2)
    snapshot.fact_answer.extend(
        [
            {
                "question_id": 2,
                "field": "total_output_daily",
                "status": "missing",
                "value": None,
                "source": None,
                "trace_id": None,
                "business_date": "2026-06-27",
                "reason": "primary_fact_missing_field:total_output_daily",
                "action": None,
            },
            {
                "question_id": 2,
                "field": "daily_input_weight",
                "status": "missing",
                "value": None,
                "source": None,
                "trace_id": None,
                "business_date": "2026-06-27",
                "reason": "primary_fact_missing_field:daily_input_weight",
                "action": None,
            },
        ]
    )

    result = evaluate_question_snapshot(question, snapshot)

    assert "fact" not in result.failed_gate_names


def test_multi_field_conflict_question_checks_each_record_without_requiring_confirmation() -> None:
    question = build_20_question_catalog()[16]
    snapshot = _passing_snapshot(17)
    snapshot.fact_answer = [
        {
            "question_id": 17,
            "field": field,
            "status": "conflict",
            "value": value,
            "source": "mes_readonly",
            "trace_id": f"trace-{field}",
            "business_date": "2026-06-27",
            "reason": f"{field} 与另一个来源的同口径值不一致",
            "action": f"请生产负责人按 trace 复核 {field} 的来源差异",
        }
        for field, value in (("total_output_daily", 118.0), ("finished_inbound_daily", 110.0))
    ]

    result = evaluate_question_snapshot(question, snapshot)

    assert "fact" not in result.failed_gate_names


def test_follow_up_catalog_question_passes_real_recognition_payload_gate() -> None:
    matches = [
        item
        for item in build_20_question_catalog()
        if "接着上一个问题，把证据编号给我" in item.follow_up_utterances
    ]
    assert matches
    question = matches[0]
    plan = understand_root_owner_message(
        question.follow_up_utterances[0],
        default_business_date=date(2026, 6, 27),
        previous_domain=question.domain,
        previous_metric_keys=question.metric_keys,
        previous_business_date=date(2026, 6, 27),
    )
    snapshot = _passing_snapshot(question.question_id)
    snapshot.recognition = {
        "domain": plan.domain,
        "metric_keys": list(plan.metric_keys),
        "business_date": plan.business_date.isoformat(),
        "needs_clarification": plan.needs_clarification,
        "recognition_reason": plan.recognition_reason,
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert plan.needs_clarification is False
    assert plan.intent == "evidence_follow_up"
    assert "context_follow_up" in plan.recognition_reason
    assert "understanding" not in result.failed_gate_names


def test_evaluate_question_snapshot_passes_all_five_gates() -> None:
    result = evaluate_question_snapshot(build_20_question_catalog()[0], _passing_snapshot(1))

    assert result.core_passed is True
    assert result.delivery_passed is True
    assert result.status == "confirmed"
    assert [gate.name for gate in result.gates if not gate.passed] == []


def test_answer_gate_rejects_internal_identity_and_trace_id_copy() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(
        1,
        answer="Factory Brain answered with trace_id: abc. 来源：MES。状态：confirmed。",
    )

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "answer" in result.failed_gate_names
    assert "public_identity_or_language_failed" in result.failed_reasons


def test_answer_gate_rejects_answer_that_is_not_really_chinese() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(
        1,
        answer=(
            "鑫泰铝业智能大脑 answer confirmed. "
            "来源: MES/WMS readonly. 状态: confirmed. 追踪编号: trace-q."
        ),
    )

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "answer" in result.failed_gate_names
    assert "public_identity_or_language_failed" in result.failed_reasons


def test_answer_gate_rejects_public_identity_terms_regardless_of_case() -> None:
    question = build_20_question_catalog()[0]
    for forbidden_term in (
        "Developer",
        "Engineer",
        "codex",
        "CODEX",
        "开发者",
        "研发助手",
        "工程师",
    ):
        snapshot = _passing_snapshot(
            1,
            answer=(
                f"鑫泰铝业智能大脑回答：结论已确认。{forbidden_term} 已处理。"
                "来源：MES/WMS 只读链路。状态：confirmed。追踪编号：trace-q。"
            ),
        )

        result = evaluate_question_snapshot(question, snapshot)

        assert result.core_passed is False, forbidden_term
        assert "answer" in result.failed_gate_names
        assert "public_identity_or_language_failed" in result.failed_reasons


def test_source_gate_rejects_rag_as_current_fact_source() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.evidence["primary_source"] = "rag"
    snapshot.evidence["trace"]["source_order"] = ["rag"]

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "rag_used_as_current_fact_source" in result.failed_reasons


def test_source_gate_rejects_source_status_with_only_rag() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.evidence["primary_source"] = ""
    snapshot.evidence["trace"]["source_order"] = []
    snapshot.evidence["trace"]["source_status"] = {"rag": {"status": "ok"}}

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "source" in result.failed_gate_names
    assert "rag_used_as_current_fact_source" in result.failed_reasons


def test_source_gate_accepts_energy_readonly_disabled_as_known_missing_state() -> None:
    question = build_20_question_catalog()[4]
    snapshot = _passing_snapshot(5)
    snapshot.evidence["trace"]["source_status"]["energy_readonly"] = {
        "status": "disabled",
        "reason": "source_not_configured",
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is True
    assert result.status in {"confirmed", "candidate"}


def test_delivery_gate_allows_environment_failure_but_not_core_failure() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.dispatch = {
        "status": "retrying",
        "detail": "DingTalk API rate limit",
        "outbox_message_id": 101,
        "log_status": "retrying",
        "channel_type": "dingtalk_group",
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is True
    assert result.delivery_passed is False
    assert result.delivery_environment_failure is True


def test_summary_requires_20_core_passes_and_allows_two_environment_delivery_failures() -> None:
    catalog = build_20_question_catalog()
    snapshots = [_passing_snapshot(item.question_id) for item in catalog]
    for snapshot in snapshots[:2]:
        snapshot.dispatch["status"] = "retrying"
        snapshot.dispatch["detail"] = "DingTalk test group permission denied"
        snapshot.dispatch["log_status"] = "retrying"

    summary = evaluate_acceptance_summary(snapshots)

    assert summary.core_passed is True
    assert summary.delivery_passed is True
    assert summary.core_pass_count == 20
    assert summary.delivery_success_count == 18
    assert summary.environment_failure_count == 2


def test_summary_delivery_fails_when_one_core_question_fails_even_if_all_were_sent() -> None:
    catalog = build_20_question_catalog()
    snapshots = [_passing_snapshot(item.question_id) for item in catalog]
    snapshots[-1].recognition["metric_keys"] = ["wrong_metric"]

    summary = evaluate_acceptance_summary(snapshots)

    assert summary.core_passed is False
    assert summary.delivery_passed is False
    assert summary.core_pass_count == 19
    assert summary.delivery_success_count == 20


def test_summary_requires_20_distinct_question_ids() -> None:
    snapshots = [_passing_snapshot(1) for _ in range(20)]

    summary = evaluate_acceptance_summary(snapshots)

    assert summary.core_passed is False
    assert summary.delivery_passed is False


def test_source_gate_accepts_canonical_dingtalk_group_content_status() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.evidence["primary_source"] = "dingtalk_group_content"
    snapshot.evidence["trace"]["source_order"] = ["mes_readonly", "data_hub_projection"]

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is True


def test_required_source_name_without_healthy_real_evidence_fails() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.evidence["primary_source"] = "data_hub_projection"
    snapshot.evidence["candidate_sources"] = ["data_hub_projection"]
    snapshot.evidence["trace"]["source_status"]["dingtalk_group_content"] = {
        "status": "failed",
        "reason": "source_failed",
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "source" in result.failed_gate_names
    assert "dingtalk_source_not_usable" in result.failed_reasons


def test_required_mes_source_needs_healthy_candidate_evidence() -> None:
    question = build_20_question_catalog()[1]
    snapshot = _passing_snapshot(2)
    snapshot.evidence["primary_source"] = "data_hub_projection"
    snapshot.evidence["candidate_sources"] = ["data_hub_projection"]
    snapshot.evidence["trace"]["source_status"]["mes_readonly"] = {
        "status": "failed",
        "reason": "source_failed",
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "source" in result.failed_gate_names
    assert "mes_readonly_source_not_usable" in result.failed_reasons


def test_dingtalk_supporting_only_does_not_confirm_critical_value() -> None:
    question = build_20_question_catalog()[4]
    snapshot = _passing_snapshot(5)
    snapshot.evidence["primary_source"] = "data_hub_projection"
    snapshot.evidence["candidate_sources"] = ["data_hub_projection"]
    snapshot.evidence["trace"]["source_status"]["dingtalk_group_content"] = {
        "status": "supporting_only",
        "supporting_count": 1,
    }
    snapshot.evidence["trace"]["supporting_evidence"] = [
        {"source_key": "dingtalk_group_file", "status": "supporting_only"}
    ]
    snapshot.fact_answer = [
        {
            "question_id": 5,
            "field": "total_electricity_kwh",
            "status": "missing",
            "value": None,
            "source": None,
            "trace_id": None,
            "business_date": "2026-06-27",
            "reason": "群文件只有辅助说明，没有 total_electricity_kwh 数值",
            "action": "请电工补录当日总电量表计值和来源证据",
        }
    ]

    result = evaluate_question_snapshot(question, snapshot)

    assert "source" not in result.failed_gate_names
    assert "fact" in result.failed_gate_names
    assert result.core_passed is False


def test_daily_report_gate_present_passes_source_health_prerequisite() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.required_source_health = ("daily_report_gate",)
    snapshot.source_health["daily_report_gate"] = {
        "source_key": "daily_report_gate",
        "status": "passed",
        "business_date": "2026-06-27",
        "output_skill_alignment": {"status": "passed", "reference_mode": "compare"},
        "fact_closure": {"status": "pass"},
        "gap_plan": {"status": "ready"},
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is True
    assert "source" not in result.failed_gate_names


@pytest.mark.parametrize("reference_mode", ("adopt", "reference_only"))
def test_daily_report_gate_rejects_non_compare_reference_modes(reference_mode: str) -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.required_source_health = ("daily_report_gate",)
    snapshot.source_health["daily_report_gate"] = {
        "source_key": "daily_report_gate",
        "status": "passed",
        "business_date": "2026-06-27",
        "output_skill_alignment": {"status": "passed", "reference_mode": reference_mode},
        "fact_closure": {"status": "pass"},
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "daily_report_gate_not_compare_only" in result.failed_reasons


def test_daily_report_gate_missing_fails_only_when_required() -> None:
    question = build_20_question_catalog()[0]
    optional_snapshot = _passing_snapshot(1)
    required_snapshot = _passing_snapshot(1)
    required_snapshot.required_source_health = ("daily_report_gate",)

    optional_result = evaluate_question_snapshot(question, optional_snapshot)
    required_result = evaluate_question_snapshot(question, required_snapshot)

    assert optional_result.core_passed is True
    assert required_result.core_passed is False
    assert "source" in required_result.failed_gate_names
    assert "daily_report_gate_required_but_missing" in required_result.failed_reasons


def test_unfamiliar_dingtalk_wording_becomes_action_not_hard_parse_failure() -> None:
    question = build_20_question_catalog()[14]
    snapshot = _passing_snapshot(15)
    snapshot.status = "clarifying"
    snapshot.answer = (
        "鑫泰铝业智能大脑已把这条钉钉原话记录成待补证据动作。"
        "来源：钉钉群聊天内容。状态：candidate。追踪编号：trace-q15。"
    )
    snapshot.recognition["needs_clarification"] = True
    snapshot.recognition["recognition_reason"] = "unfamiliar_dingtalk_wording"
    snapshot.evidence["actions"] = [
        {
            "type": "follow_up",
            "reason": "unfamiliar_dingtalk_wording",
            "next_step": "请专项责任人补充标准字段或截图。",
        }
    ]
    snapshot.evidence["missing_sources"] = ["dingtalk_field_mapping"]

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is True
    assert "understanding" not in result.failed_gate_names
    assert result.status == "missing"


def test_unfamiliar_dingtalk_wording_with_type_only_action_still_fails_understanding_gate() -> None:
    question = build_20_question_catalog()[14]
    snapshot = _passing_snapshot(15)
    snapshot.status = "clarifying"
    snapshot.recognition["needs_clarification"] = True
    snapshot.recognition["recognition_reason"] = "unfamiliar_dingtalk_wording"
    snapshot.evidence["actions"] = [{"type": "follow_up"}]

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "understanding" in result.failed_gate_names
    assert "needs_clarification" in result.failed_reasons


def test_unfamiliar_dingtalk_wording_with_action_text_can_pass_understanding_gate() -> None:
    question = build_20_question_catalog()[14]
    snapshot = _passing_snapshot(15)
    snapshot.status = "clarifying"
    snapshot.answer = (
        "鑫泰铝业智能大脑已把这条钉钉原话记录成待补证据动作。"
        "来源：钉钉群聊天内容。状态：candidate。追踪编号：trace-q15。"
    )
    snapshot.recognition["needs_clarification"] = True
    snapshot.recognition["recognition_reason"] = "unfamiliar_dingtalk_wording"
    snapshot.evidence["actions"] = [{"action": "请补充原始钉钉消息截图"}]
    snapshot.evidence["missing_sources"] = ["dingtalk_field_mapping"]

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is True
    assert "understanding" not in result.failed_gate_names


def test_understanding_gate_rejects_wrong_domain_for_factory_overview() -> None:
    question = build_20_question_catalog()[19]
    snapshot = _passing_snapshot(20)
    snapshot.recognition["domain"] = "energy"

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "domain_not_recognized" in result.failed_reasons


def test_report_displays_fact_gate() -> None:
    snapshots = [_passing_snapshot(item.question_id) for item in build_20_question_catalog()]

    report = render_acceptance_report(evaluate_acceptance_summary(snapshots))

    assert "| 问题 | 理解 | 来源 | 事实 | 回答 | 钉钉 | 状态 |" in report
