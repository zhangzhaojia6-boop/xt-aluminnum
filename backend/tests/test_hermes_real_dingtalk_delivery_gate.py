from __future__ import annotations

from app.services.hermes_20_question_acceptance import (
    AcceptanceTurnSnapshot,
    build_20_question_catalog,
    evaluate_question_snapshot,
)


def _snapshot(dispatch: dict) -> AcceptanceTurnSnapshot:
    return AcceptanceTurnSnapshot(
        question_id=1,
        trace_id="trace-delivery",
        status="answered",
        answer="鑫泰铝业智能大脑回答。来源：钉钉群聊天内容。状态：confirmed。追踪编号：trace-delivery。",
        recognition={
            "domain": "production",
            "metric_keys": ["total_output_daily"],
            "business_date": "2026-06-27",
            "needs_clarification": False,
        },
        evidence={
            "primary_source": "dingtalk_group_chat",
            "candidate_sources": ["dingtalk_group_chat", "mes_readonly"],
            "missing_sources": [],
            "conflicts": [],
            "trace": {
                "source_order": ["dingtalk_group_chat", "mes_readonly"],
                "source_status": {"mes_readonly": {"status": "ok"}},
            },
        },
        dispatch=dispatch,
        source_health={},
    )


def test_delivery_gate_accepts_sent_external_log() -> None:
    result = evaluate_question_snapshot(
        build_20_question_catalog()[0],
        _snapshot({"status": "sent", "log_status": "sent", "detail": "ok"}),
    )

    assert result.delivery_passed is True


def test_delivery_gate_rejects_dry_run_for_real_acceptance() -> None:
    result = evaluate_question_snapshot(
        build_20_question_catalog()[0],
        _snapshot({"status": "dry_run", "log_status": "dry_run", "detail": "dry-run only, message not sent"}),
    )

    assert result.delivery_passed is False
    assert result.delivery_environment_failure is False


def test_delivery_gate_classifies_test_group_permission_as_environment_failure() -> None:
    result = evaluate_question_snapshot(
        build_20_question_catalog()[0],
        _snapshot({"status": "retrying", "log_status": "retrying", "detail": "test group permission denied"}),
    )

    assert result.delivery_passed is False
    assert result.delivery_environment_failure is True


def test_delivery_gate_classifies_code_exception_as_non_environment_failure() -> None:
    result = evaluate_question_snapshot(
        build_20_question_catalog()[0],
        _snapshot({"status": "retrying", "log_status": "retrying", "detail": "AttributeError: object has no attribute send"}),
    )

    assert result.delivery_passed is False
    assert result.delivery_environment_failure is False
