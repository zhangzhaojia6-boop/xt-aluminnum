from datetime import date

from app.services import hermes_root_owner_evidence_service as root_owner_evidence_service
from app.services.hermes_20_question_acceptance import confirmed_fact_failure_reason
from app.services.hermes_dingtalk_evidence_service import DingTalkEvidenceItem
from app.services.hermes_root_owner_evidence_service import (
    EvidenceCandidate,
    choose_primary_evidence,
    collect_root_owner_evidence,
)
from app.services.hermes_root_owner_message_service import RootOwnerMessagePlan


def _dingtalk_item(
    *,
    trace_id: str,
    value: float,
    adoptable: bool,
    source_key: str = "dingtalk_group_content",
) -> DingTalkEvidenceItem:
    return DingTalkEvidenceItem(
        evidence_id=1,
        trace_id=trace_id,
        business_date=date(2026, 6, 27),
        event_time=None,
        group_id="group-1",
        conversation_id="group-1",
        sender_id="sender-1",
        content_kind="file_text" if source_key == "dingtalk_group_file" else "message_text",
        text=f"总产量 {value} 吨",
        parse_status="text_captured",
        confirmation_status="confirmed" if adoptable else "machine_only",
        visible_to_hermes=True,
        adoptable_as_fact=adoptable,
        source_key=source_key,
        evidence_type="dingtalk_file" if source_key == "dingtalk_group_file" else "dingtalk_text",
        file_uri="dingtalk://file/1" if source_key == "dingtalk_group_file" else None,
        payload={
            "source": "dingtalk",
            "business_date": "2026-06-27",
            "trace_id": trace_id,
            "parse_status": "text_captured",
            "fact_updates": {"total_output_daily": {"value": value}},
        },
        created_at=None,
    )


def _message_plan(
    domain: str = "production",
    metric_keys: tuple[str, ...] = ("total_output_daily",),
) -> RootOwnerMessagePlan:
    return RootOwnerMessagePlan(
        raw_text="今天产量咋样",
        normalized_text="今天产量咋样",
        business_date=date(2026, 6, 27),
        domain=domain,
        intent="production_summary",
        metric_keys=metric_keys,
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
    assert decision.conflicts[0]["field"] == "total_output_daily"


def test_disjoint_candidate_fields_do_not_create_a_false_conflict() -> None:
    candidates = [
        EvidenceCandidate(
            source_key="dingtalk_group_chat",
            source_type="dingtalk_group_content",
            domain="production",
            priority=10,
            status="ok",
            value={"daily_input_weight": 560.0},
            summary="钉钉投料量",
            trace_ref={"trace_id": "ding-input-71"},
        ),
        EvidenceCandidate(
            source_key="data_hub_projection",
            source_type="data_hub",
            domain="production",
            priority=40,
            status="ok",
            value={"total_output_daily": 286.0},
            summary="数据中枢总产量",
            trace_ref={"trace_id": "hub-output-118"},
        ),
    ]

    decision = choose_primary_evidence(candidates, domain="production")

    assert decision.primary is candidates[0]
    assert decision.conflicts == ()


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


def test_source_priority_still_wins_when_lower_source_has_structured_fact_shape() -> None:
    candidates = [
        EvidenceCandidate(
            source_key="data_hub_projection",
            source_type="data_hub",
            domain="production",
            priority=40,
            status="ok",
            value={"total_output_daily": {"value": 99.0, "source_ref": {"row_count": 1}}},
            summary="数据中枢结构化事实",
            trace_ref={},
        ),
        EvidenceCandidate(
            source_key="dingtalk_group_content",
            source_type="dingtalk_group_content",
            domain="production",
            priority=10,
            status="ok",
            value={"total_output_daily": 100.0},
            summary="钉钉高优先级事实",
            trace_ref={},
        ),
    ]

    decision = choose_primary_evidence(candidates, domain="production")

    assert decision.primary.source_key == "dingtalk_group_content"


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


def test_collect_keeps_dingtalk_metadata_and_uncontracted_mes_as_supporting() -> None:
    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(),
        trace_id="trace-dingtalk-metadata",
        dingtalk_reader=lambda **_kwargs: [
            EvidenceCandidate(
                source_key="dingtalk_group_chat",
                source_type="dingtalk_group_content",
                domain="production",
                priority=10,
                status="ok",
                value={"items": [{"message_id": "msg-1", "sent_date": "2026-06-27"}]},
                summary="钉钉只有同日消息元数据",
                trace_ref={"message_id": "msg-1"},
            )
        ],
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary is None
    assert decision.candidates == ()
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "supporting_only"
    assert [item["source_key"] for item in decision.trace["supporting_evidence"]] == [
        "dingtalk_group_chat",
        "mes_readonly",
    ]


def test_collect_records_missing_and_failed_source_status_with_redacted_errors() -> None:
    def failing_hub_reader(**_kwargs):
        raise RuntimeError("hub failed with token=secret-token password=plain-pass")

    decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(),
        trace_id="trace-source-status",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=None,
        hub_reader=failing_hub_reader,
    )

    source_status = decision.trace["source_status"]

    assert decision.primary is None
    assert decision.missing_sources == ["dingtalk_group_content", "mes_readonly", "data_hub_projection"]
    assert source_status["dingtalk_group_content"]["status"] == "missing"
    assert source_status["mes_readonly"]["status"] == "missing"
    assert source_status["mes_readonly"]["query_keys"] == ["workshop_process_records"]
    assert source_status["data_hub_projection"]["status"] == "failed"
    assert "token=<redacted>" in source_status["data_hub_projection"]["error"]
    assert "password=<redacted>" in source_status["data_hub_projection"]["error"]
    assert "secret-token" not in source_status["data_hub_projection"]["error"]
    assert "plain-pass" not in source_status["data_hub_projection"]["error"]


def test_inventory_domain_queries_mes_but_keeps_uncontracted_values_supporting() -> None:
    class MesReader:
        def __init__(self) -> None:
            self.calls = []

        def read_sources(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "source_status": {"mes": "ok"},
                "records": {
                    "finished_inbound_daily": 120.0,
                    "remaining_contract_weight": 900.0,
                    "wip_total": 33.0,
                },
            }

    mes_reader = MesReader()
    metric_keys = ("finished_inbound_daily", "wip_total", "remaining_contract_weight")

    decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(domain="inventory", metric_keys=metric_keys),
        trace_id="trace-inventory-mes",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=mes_reader,
        hub_reader=lambda **_kwargs: {"status": "ok", "finished_inbound_daily": 99.0},
    )

    assert mes_reader.calls == [
        {
            "business_date": date(2026, 6, 27),
            "query_keys": ["finished_inbound_records", "stock_records", "wip_totals"],
        }
    ]
    assert decision.primary.source_key == "data_hub_projection"
    assert decision.primary.value["finished_inbound_daily"] == 99.0
    assert decision.trace["source_status"]["mes_readonly"]["query_keys"] == [
        "finished_inbound_records",
        "stock_records",
        "wip_totals",
    ]


def test_energy_domain_checks_mes_readonly_even_without_energy_fact() -> None:
    class MesReader:
        def __init__(self) -> None:
            self.calls = []

        def read_sources(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "source_status": {"mes": "ok"},
                "records": {},
            }

    mes_reader = MesReader()

    decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(domain="energy", metric_keys=("total_electricity_kwh",)),
        trace_id="trace-energy-mes",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=mes_reader,
        hub_reader=lambda **_kwargs: None,
    )

    assert mes_reader.calls == [
        {
            "business_date": date(2026, 6, 27),
            "query_keys": ["workshop_process_records", "finished_inbound_records"],
        }
    ]
    assert decision.trace["source_status"]["mes_readonly"]["status"] == "ok"
    assert decision.trace["source_status"]["mes_readonly"]["reason"] == "no_current_metric_fact"


def test_default_dingtalk_reader_promotes_structured_metric_fact_over_mes(monkeypatch) -> None:
    def read_dingtalk_evidence(_db, *, business_date):
        assert business_date == date(2026, 6, 27)
        return [_dingtalk_item(trace_id="trace-ding-structured", value=118.0, adoptable=True)]

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(root_owner_evidence_service, "query_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-fact",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary.source_key == "dingtalk_group_chat"
    field_fact = decision.primary.value["total_output_daily"]
    assert field_fact["value"] == 118.0
    assert field_fact["source_type"] == "dingtalk_supplement"
    assert confirmed_fact_failure_reason(
        {
            "question_id": 1,
            "field": "total_output_daily",
            **field_fact,
        }
    ) is None
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "ok"
    assert decision.trace["source_status"]["dingtalk_group_content"]["candidate_count"] == 1
    assert decision.trace["source_status"]["dingtalk_group_content"]["sources"]["dingtalk_text"]["count"] == 1


def test_default_dingtalk_group_fact_without_specialist_sender_becomes_primary(monkeypatch) -> None:
    def read_dingtalk_evidence(_db, *, business_date):
        assert business_date == date(2026, 6, 27)
        return [_dingtalk_item(trace_id="trace-ding-group-three-conditions", value=118.0, adoptable=True)]

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(root_owner_evidence_service, "query_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-three-conditions",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: {"status": "ready", "total_output_daily": 99.0},
    )

    assert decision.primary.source_key == "dingtalk_group_chat"
    assert decision.primary.value["total_output_daily"]["value"] == 118.0
    assert [candidate.source_key for candidate in decision.candidates] == [
        "dingtalk_group_chat",
        "data_hub_projection",
    ]
    assert decision.trace["source_status"]["dingtalk_group_content"]["candidate_count"] == 1


def test_default_dingtalk_reader_keeps_unverified_facts_and_raw_mes_supporting(monkeypatch) -> None:
    def read_dingtalk_evidence(_db, *, business_date):
        assert business_date == date(2026, 6, 27)
        return [_dingtalk_item(trace_id="trace-ding-unverified", value=118.0, adoptable=False)]

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(root_owner_evidence_service, "query_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-unverified",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary is None
    assert decision.candidates == ()
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "supporting_only"
    assert decision.trace["source_status"]["dingtalk_group_content"]["candidate_count"] == 0
    assert decision.trace["supporting_evidence"][0]["source_key"] == "dingtalk_group_chat"


def test_default_dingtalk_reader_keeps_condition_rules_and_raw_mes_supporting(monkeypatch) -> None:
    def read_dingtalk_evidence(_db, *, business_date):
        assert business_date == date(2026, 6, 27)
        return [_dingtalk_item(trace_id="trace-ding-condition-rules", value=118.0, adoptable=False)]

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(root_owner_evidence_service, "query_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-condition-rules",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary is None
    assert decision.candidates == ()
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "supporting_only"
    assert decision.trace["source_status"]["dingtalk_group_content"]["candidate_count"] == 0
    assert decision.trace["supporting_evidence"][0]["source_key"] == "dingtalk_group_chat"


def test_default_dingtalk_reader_prefers_text_over_file_when_both_verified(monkeypatch) -> None:
    def read_dingtalk_evidence(_db, *, business_date):
        assert business_date == date(2026, 6, 27)
        return [
            _dingtalk_item(
                trace_id="trace-ding-file",
                value=99.0,
                adoptable=True,
                source_key="dingtalk_group_file",
            ),
            _dingtalk_item(trace_id="trace-ding-text", value=118.0, adoptable=True),
        ]

    monkeypatch.setattr(root_owner_evidence_service, "query_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-text-file",
        mes_reader=None,
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary.source_key == "dingtalk_group_chat"
    assert decision.primary.value["total_output_daily"]["value"] == 118.0
    assert [candidate.source_key for candidate in decision.candidates] == [
        "dingtalk_group_chat",
        "dingtalk_group_file",
    ]
    assert decision.conflicts[0]["lower_source"] == "dingtalk_group_file"
    assert decision.conflicts[0]["chosen_source"] == "dingtalk_group_chat"


def test_default_dingtalk_reader_preserves_failed_status_and_redacted_error(monkeypatch) -> None:
    def read_dingtalk_evidence(_db, *, business_date):
        raise RuntimeError("read failed token=secret-token password=plain-pass")

    monkeypatch.setattr(root_owner_evidence_service, "query_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-failed",
        mes_reader=None,
        hub_reader=lambda **_kwargs: None,
    )

    dingtalk_status = decision.trace["source_status"]["dingtalk_group_content"]
    text_status = dingtalk_status["sources"]["dingtalk_text"]

    assert decision.primary is None
    assert "dingtalk_group_content" in decision.missing_sources
    assert dingtalk_status["status"] == "failed"
    assert dingtalk_status["reason"] == "source_failed"
    assert text_status["status"] == "failed"
    assert text_status["count"] == 0
    assert "token=<redacted>" in text_status["error"]
    assert "password=<redacted>" in text_status["error"]
    assert "secret-token" not in text_status["error"]
    assert "plain-pass" not in text_status["error"]


def test_mes_real_records_shape_is_supporting_without_fact_contract() -> None:
    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {
                    "workshop_process_records": [
                        {"net_weight": 60.5, "workshop_name": "冷轧1650"},
                        {"output_weight": 39.5, "workshop_name": "冷轧1850"},
                    ]
                },
            }

    decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(),
        trace_id="trace-mes-real-records",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary is None
    assert decision.trace["source_status"]["mes_readonly"]["status"] == "supporting_only"
    assert decision.trace["source_status"]["mes_readonly"]["upstream_status"] == "ok"
    assert decision.trace["source_status"]["mes_readonly"]["reason"] == "metric_fact_without_contract"
    assert decision.trace["supporting_evidence"][-1]["source_key"] == "mes_readonly"


def test_mes_metadata_shape_is_supporting_without_fact_contract() -> None:
    class MesReader:
        def read_sources(self, **kwargs):
            query_keys = kwargs["query_keys"]
            if query_keys == ["yield_records"]:
                return {
                    "source_status": {"mes": "ok"},
                    "records": {"yield_records": [{"metadata": {"YieldRate": 84.86}}]},
                }
            return {
                "source_status": {"mes": "ok"},
                "records": {"wip_totals": [{"workshop_name": "冷轧", "doing_weight": 12.5}]},
            }

    quality_decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(domain="quality", metric_keys=("daily_yield_rate",)),
        trace_id="trace-quality-yield",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )
    wip_decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(domain="production", metric_keys=("wip_total",)),
        trace_id="trace-wip-total",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert quality_decision.primary is None
    assert quality_decision.trace["source_status"]["mes_readonly"]["query_keys"] == ["yield_records"]
    assert wip_decision.primary is None
    assert quality_decision.trace["supporting_evidence"][-1]["source_key"] == "mes_readonly"
    assert wip_decision.trace["supporting_evidence"][-1]["source_key"] == "mes_readonly"


def test_hub_ready_status_can_be_primary_when_mes_is_missing() -> None:
    decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(),
        trace_id="trace-hub-ready-primary",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=None,
        hub_reader=lambda **_kwargs: {
            "status": "ready",
            "facts": {
                "values": {
                    "total_output_daily": 88.0,
                    "total_output_month": 1888.0,
                }
            },
        },
    )

    assert decision.primary.source_key == "data_hub_projection"
    assert decision.primary.status == "ok"
    assert decision.primary.value == {"total_output_daily": 88.0}
    assert decision.trace["source_status"]["data_hub_projection"]["status"] == "ready"
    assert decision.trace["source_status"]["data_hub_projection"]["candidate_status"] == "ok"


def test_default_hub_reader_uses_compare_only_fact_bundle_and_keeps_field_when_bundle_blocked(monkeypatch) -> None:
    calls = []

    def fake_build_daily_fact_bundle(db, **kwargs):
        calls.append({"db": db, **kwargs})
        return {
            "status": "blocked",
            "facts": {
                "total_output_daily": {
                    "value": 88.0,
                    "unit": "吨",
                    "source_type": "mes_workshop_process_records",
                    "evidence_status": "confirmed",
                    "source_ref": {
                        "business_date": "2026-06-27",
                        "business_window": "2026-06-27T08:00:00+08:00/2026-06-28T08:00:00+08:00",
                        "source_ref": "mes_workshop_process_records",
                        "unit": "吨",
                        "metric_contract_version": "2026-07-11",
                        "latest_row_id": 9,
                        "row_count": 2,
                        "trace_id": "projection-read:mes_workshop_process_records:9:2",
                    },
                }
            },
            "missing_fields": ["total_electricity_kwh"],
            "gap_plan": {
                "status": "needs_action",
                "items": [
                    {
                        "field": "total_electricity_kwh",
                        "next_step": "请电工扫码补录全厂高压总用电量。",
                        "actual": 100,
                        "expected": 120,
                    }
                ],
            },
        }

    monkeypatch.setattr(
        root_owner_evidence_service.daily_fact_bundle,
        "build_daily_fact_bundle",
        fake_build_daily_fact_bundle,
    )
    fake_db = object()

    decision = collect_root_owner_evidence(
        db=fake_db,
        message_plan=_message_plan(),
        trace_id="trace-default-daily-fact-bundle",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=None,
    )

    assert calls == [
        {
            "db": fake_db,
            "business_date": date(2026, 6, 27),
            "allow_output_skill_reference_adoption": False,
        }
    ]
    assert decision.primary.source_key == "data_hub_projection"
    assert decision.primary.status == "ok"
    assert decision.primary.value["total_output_daily"]["value"] == 88.0
    assert decision.primary.trace_ref["source"] == "daily_fact_bundle"
    assert decision.trace["source_status"]["data_hub_projection"] == {
        "status": "blocked",
        "candidate_status": "ok",
    }
    assert decision.trace["gap_plan"]["items"] == [
        {
            "field": "total_electricity_kwh",
            "next_step": "请电工扫码补录全厂高压总用电量。",
        }
    ]


def test_contract_shaped_hub_fact_wins_over_bare_mes_aggregate() -> None:
    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {
                    "workshop_process_records": [
                        {"net_weight": 60.5},
                        {"output_weight": 39.5},
                    ]
                },
            }

    hub_fact = {
        "value": 99.0,
        "unit": "吨",
        "source_type": "mes_workshop_process_records",
        "evidence_status": "confirmed",
        "source_ref": {
            "business_date": "2026-06-27",
            "business_window": "2026-06-27T08:00:00+08:00/2026-06-28T08:00:00+08:00",
            "source_ref": "mes_workshop_process_records",
            "unit": "吨",
            "metric_contract_version": "2026-07-11",
            "latest_row_id": 9,
            "row_count": 2,
            "trace_id": "projection-read:mes_workshop_process_records:9:2",
        },
    }

    decision = collect_root_owner_evidence(
        db=None,
        message_plan=_message_plan(),
        trace_id="trace-hub-contract-over-bare-mes",
        dingtalk_reader=lambda **_kwargs: [],
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: {
            "status": "blocked",
            "facts": {"total_output_daily": hub_fact},
            "missing_fields": ["total_electricity_kwh"],
        },
    )

    assert decision.primary.source_key == "data_hub_projection"
    assert decision.primary.value == {"total_output_daily": hub_fact}
    assert [candidate.source_key for candidate in decision.candidates] == ["data_hub_projection"]
    assert decision.trace["source_status"]["mes_readonly"]["reason"] == "metric_fact_without_contract"
    assert decision.trace["supporting_evidence"][-1]["source_key"] == "mes_readonly"


def test_default_reader_keeps_machine_only_text_as_supporting_only(monkeypatch) -> None:
    fake_db = type("FakeDb", (), {"query": object()})()

    def fake_query(_db, *, business_date):
        return [
            DingTalkEvidenceItem(
                evidence_id=1,
                trace_id="trace-machine-only",
                business_date=business_date,
                event_time=None,
                group_id="cid-1",
                conversation_id="cid-1",
                sender_id="user-1",
                content_kind="message_text",
                text="今日总产量大概 118 吨",
                parse_status="text_captured",
                confirmation_status="machine_only",
                visible_to_hermes=True,
                adoptable_as_fact=False,
                source_key="dingtalk_group_content",
                evidence_type="text",
                file_uri=None,
                payload={
                    "source": "dingtalk",
                    "business_date": business_date.isoformat(),
                    "trace_id": "trace-machine-only",
                    "message_text": "今日总产量大概 118 吨",
                },
                created_at=None,
            )
        ]

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(root_owner_evidence_service, "query_dingtalk_evidence", fake_query)

    decision = collect_root_owner_evidence(
        db=fake_db,
        message_plan=_message_plan(),
        trace_id="trace-machine-only-supporting",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary is None
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "supporting_only"
    assert decision.trace["source_status"]["dingtalk_group_content"]["candidate_count"] == 0
    assert decision.trace["supporting_evidence"][0]["source_key"] == "dingtalk_group_chat"


def test_default_reader_requires_trace_before_dingtalk_can_be_primary(monkeypatch) -> None:
    fake_db = type("FakeDb", (), {"query": object()})()

    def fake_query(_db, *, business_date):
        return [
            DingTalkEvidenceItem(
                evidence_id=2,
                trace_id="",
                business_date=business_date,
                event_time=None,
                group_id="cid-2",
                conversation_id="cid-2",
                sender_id="user-2",
                content_kind="message_text",
                text="6月27日总产量 118 吨",
                parse_status="text_captured",
                confirmation_status="confirmed",
                visible_to_hermes=True,
                adoptable_as_fact=False,
                source_key="dingtalk_group_content",
                evidence_type="text",
                file_uri=None,
                payload={
                    "source": "dingtalk",
                    "business_date": business_date.isoformat(),
                    "message_text": "6月27日总产量 118 吨",
                },
                created_at=None,
            )
        ]

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(root_owner_evidence_service, "query_dingtalk_evidence", fake_query)

    decision = collect_root_owner_evidence(
        db=fake_db,
        message_plan=_message_plan(),
        trace_id="trace-missing-trace-supporting",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary is None
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "supporting_only"
