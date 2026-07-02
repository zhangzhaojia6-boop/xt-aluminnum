from __future__ import annotations

from app.services.hermes_20_question_acceptance import (
    AcceptanceTurnSnapshot,
    build_20_question_catalog,
    evaluate_acceptance_summary,
    evaluate_question_snapshot,
)


def _passing_snapshot(question_id: int, *, answer: str | None = None) -> AcceptanceTurnSnapshot:
    catalog = {item.question_id: item for item in build_20_question_catalog()}
    question = catalog[question_id]
    return AcceptanceTurnSnapshot(
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


def test_catalog_has_exactly_20_approved_questions() -> None:
    catalog = build_20_question_catalog()

    assert len(catalog) == 20
    assert catalog[0].question_id == 1
    assert catalog[0].question == "今天全厂总产量是多少？"
    assert catalog[14].metric_keys == ("dingtalk_specialist_evidence",)
    assert catalog[-1].question == "今天日报能不能自动生成？还缺什么？"


def test_evaluate_question_snapshot_passes_all_four_gates() -> None:
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
    for forbidden_term in ("Developer", "Engineer", "codex", "CODEX"):
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


def test_daily_report_gate_present_passes_source_health_prerequisite() -> None:
    question = build_20_question_catalog()[0]
    snapshot = _passing_snapshot(1)
    snapshot.required_source_health = ("daily_report_gate",)
    snapshot.source_health["daily_report_gate"] = {
        "source_key": "daily_report_gate",
        "status": "passed",
        "business_date": "2026-06-27",
        "output_skill_alignment": {"status": "passed"},
        "fact_closure": {"status": "pass"},
        "gap_plan": {"status": "ready"},
    }

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is True
    assert "source" not in result.failed_gate_names


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


def test_understanding_gate_rejects_wrong_domain_for_factory_overview() -> None:
    question = build_20_question_catalog()[19]
    snapshot = _passing_snapshot(20)
    snapshot.recognition["domain"] = "energy"

    result = evaluate_question_snapshot(question, snapshot)

    assert result.core_passed is False
    assert "domain_not_recognized" in result.failed_reasons
