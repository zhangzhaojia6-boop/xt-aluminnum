from datetime import date

from app.services.hermes_root_owner_evidence_service import (
    EvidenceCandidate,
    choose_primary_evidence,
    collect_root_owner_evidence,
)
from app.services.hermes_root_owner_message_service import RootOwnerMessagePlan


def _message_plan(domain: str = "production") -> RootOwnerMessagePlan:
    return RootOwnerMessagePlan(
        raw_text="今天产量咋样",
        normalized_text="今天产量咋样",
        business_date=date(2026, 6, 27),
        domain=domain,
        intent="production_summary",
        metric_keys=("total_output_daily",),
        confidence=0.8,
        needs_clarification=False,
        clarification_question=None,
        recognition_reason="test",
    )


def test_dingtalk_group_content_wins_over_mes_when_conflicting() -> None:
    candidates = [
        EvidenceCandidate(
            source_key="mes_readonly",
            source_type="external_readonly",
            domain="production",
            priority=20,
            status="ok",
            value={"total_output_daily": 100.0},
            summary="MES 只读库显示 100 吨",
            trace_ref={"query_key": "workshop_process_records"},
        ),
        EvidenceCandidate(
            source_key="dingtalk_group_chat",
            source_type="dingtalk_group_content",
            domain="production",
            priority=10,
            status="ok",
            value={"total_output_daily": 118.0},
            summary="负责人群里确认 118 吨",
            trace_ref={"trace_id": "trace-ding-001"},
        ),
    ]

    decision = choose_primary_evidence(candidates, domain="production")

    assert decision.primary.source_key == "dingtalk_group_chat"
    assert decision.primary.value["total_output_daily"] == 118.0
    assert decision.conflicts[0]["lower_source"] == "mes_readonly"
    assert decision.conflicts[0]["chosen_source"] == "dingtalk_group_chat"


def test_mes_wins_over_data_hub_projection_in_production_domain() -> None:
    candidates = [
        EvidenceCandidate(
            source_key="data_hub_projection",
            source_type="data_hub",
            domain="production",
            priority=40,
            status="ok",
            value={"total_output_daily": 99.0},
            summary="数据中枢投影 99 吨",
            trace_ref={},
        ),
        EvidenceCandidate(
            source_key="mes_readonly",
            source_type="external_readonly",
            domain="production",
            priority=20,
            status="ok",
            value={"total_output_daily": 100.0},
            summary="MES 只读库 100 吨",
            trace_ref={},
        ),
    ]

    decision = choose_primary_evidence(candidates, domain="production")

    assert decision.primary.source_key == "mes_readonly"
    assert decision.primary.value["total_output_daily"] == 100.0


def test_collect_records_missing_sources_explicitly() -> None:
    decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(),
        trace_id="trace-evidence-missing",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=None,
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary is None
    assert decision.missing_sources == ["dingtalk_group_content", "mes_readonly", "data_hub_projection"]
    assert decision.trace["trace_id"] == "trace-evidence-missing"
