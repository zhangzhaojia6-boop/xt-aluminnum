from datetime import date

from app.services.hermes_root_owner_evidence_service import (
    EvidenceCandidate,
    choose_primary_evidence,
    collect_root_owner_evidence,
)
from app.services.hermes_data_audit_service import HermesDataAuditService
from app.services.hermes_root_owner_message_service import RootOwnerMessagePlan


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


def test_collect_keeps_dingtalk_metadata_supporting_and_uses_mes_primary() -> None:
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

    assert decision.primary.source_key == "mes_readonly"
    assert decision.primary.value["total_output_daily"] == 100.0
    assert [candidate.source_key for candidate in decision.candidates] == ["mes_readonly"]
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "supporting_only"
    assert decision.trace["supporting_evidence"][0]["source_key"] == "dingtalk_group_chat"


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


def test_inventory_domain_queries_mes_for_inventory_metrics_and_prefers_mes_over_hub() -> None:
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
    assert decision.primary.source_key == "mes_readonly"
    assert decision.primary.value["finished_inbound_daily"] == 120.0
    assert decision.trace["source_status"]["mes_readonly"]["query_keys"] == [
        "finished_inbound_records",
        "stock_records",
        "wip_totals",
    ]


def test_default_dingtalk_reader_promotes_structured_metric_fact_over_mes(monkeypatch) -> None:
    def read_dingtalk_evidence(self, *, business_date):
        return {
            "dingtalk_text": {
                "status": "ok",
                "count": 1,
                "items": [
                    {
                        "trace_id": "trace-ding-structured",
                        "facts": [
                            {
                                "metric_key": "total_output_daily",
                                "value": 118.0,
                                "unit": "吨",
                            }
                        ],
                        "validation": {
                            "authorized_group": "verified",
                            "specialist_sender": "verified",
                            "content_type": "text",
                            "business_day_window": "matched",
                        },
                        "text_sample": "负责人确认今天产量 118 吨",
                    }
                ],
                "error": None,
            },
            "dingtalk_file": {
                "status": "empty",
                "count": 0,
                "items": [],
                "error": None,
            },
        }

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(HermesDataAuditService, "_read_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-fact",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary.source_key == "dingtalk_group_chat"
    assert decision.primary.value["total_output_daily"] == 118.0
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "ok"
    assert decision.trace["source_status"]["dingtalk_group_content"]["candidate_count"] == 1
    assert decision.trace["source_status"]["dingtalk_group_content"]["sources"]["dingtalk_text"]["count"] == 1


def test_default_dingtalk_group_fact_without_specialist_sender_becomes_primary(monkeypatch) -> None:
    def read_dingtalk_evidence(self, *, business_date):
        return {
            "dingtalk_text": {
                "status": "ok",
                "count": 1,
                "items": [
                    {
                        "trace_id": "trace-ding-group-three-conditions",
                        "facts": [{"metric_key": "total_output_daily", "value": 118.0}],
                        "validation": {
                            "authorized_group": "verified",
                            "content_type": "text",
                            "time_range": "matched",
                        },
                        "text_sample": "群里确认今天产量 118 吨",
                    }
                ],
                "error": None,
            },
            "dingtalk_file": {
                "status": "empty",
                "count": 0,
                "items": [],
                "error": None,
            },
        }

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(HermesDataAuditService, "_read_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-three-conditions",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: {"status": "ready", "total_output_daily": 99.0},
    )

    assert decision.primary.source_key == "dingtalk_group_chat"
    assert decision.primary.value == {"total_output_daily": 118.0}
    assert [candidate.source_key for candidate in decision.candidates] == [
        "dingtalk_group_chat",
        "mes_readonly",
        "data_hub_projection",
    ]
    assert decision.trace["source_status"]["dingtalk_group_content"]["candidate_count"] == 1


def test_default_dingtalk_reader_keeps_unverified_facts_supporting_and_uses_mes(monkeypatch) -> None:
    def read_dingtalk_evidence(self, *, business_date):
        return {
            "dingtalk_text": {
                "status": "ok",
                "count": 1,
                "items": [
                    {
                        "trace_id": "trace-ding-unverified",
                        "facts": [{"metric_key": "total_output_daily", "value": 118.0}],
                        "text_sample": "群里有人说今天产量 118 吨",
                    }
                ],
                "error": None,
            },
            "dingtalk_file": {
                "status": "empty",
                "count": 0,
                "items": [],
                "error": None,
            },
        }

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(HermesDataAuditService, "_read_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-unverified",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary.source_key == "mes_readonly"
    assert decision.primary.value == {"total_output_daily": 100.0}
    assert [candidate.source_key for candidate in decision.candidates] == ["mes_readonly"]
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "supporting_only"
    assert decision.trace["source_status"]["dingtalk_group_content"]["candidate_count"] == 0
    assert decision.trace["supporting_evidence"][0]["source_key"] == "dingtalk_group_chat"


def test_default_dingtalk_reader_keeps_condition_rules_supporting_and_uses_mes(monkeypatch) -> None:
    def read_dingtalk_evidence(self, *, business_date):
        return {
            "dingtalk_text": {
                "status": "ok",
                "count": 1,
                "items": [
                    {
                        "trace_id": "trace-ding-condition-rules",
                        "content_type": "text",
                        "specialist_sender": "verified",
                        "facts": [{"metric_key": "total_output_daily", "value": 118.0}],
                        "evidence_conditions": {
                            "authorized_group": "required",
                            "time_range": "business_day_window",
                            "content_type": ["text", "file", "image"],
                        },
                    }
                ],
                "error": None,
            },
            "dingtalk_file": {
                "status": "empty",
                "count": 0,
                "items": [],
                "error": None,
            },
        }

    class MesReader:
        def read_sources(self, **_kwargs):
            return {
                "source_status": {"mes": "ok"},
                "records": {"total_output_daily": 100.0},
            }

    monkeypatch.setattr(HermesDataAuditService, "_read_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-condition-rules",
        mes_reader=MesReader(),
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary.source_key == "mes_readonly"
    assert decision.primary.value == {"total_output_daily": 100.0}
    assert [candidate.source_key for candidate in decision.candidates] == ["mes_readonly"]
    assert decision.trace["source_status"]["dingtalk_group_content"]["status"] == "supporting_only"
    assert decision.trace["source_status"]["dingtalk_group_content"]["candidate_count"] == 0
    assert decision.trace["supporting_evidence"][0]["source_key"] == "dingtalk_group_chat"


def test_default_dingtalk_reader_prefers_text_over_file_when_both_verified(monkeypatch) -> None:
    def read_dingtalk_evidence(self, *, business_date):
        return {
            "dingtalk_file": {
                "status": "ok",
                "count": 1,
                "items": [
                    {
                        "trace_id": "trace-ding-file",
                        "facts": [{"metric_key": "total_output_daily", "value": 99.0}],
                        "validation": {
                            "authorized_group": "verified",
                            "specialist_sender": "verified",
                            "content_type": "file",
                            "time_range": "matched",
                        },
                    }
                ],
                "error": None,
            },
            "dingtalk_text": {
                "status": "ok",
                "count": 1,
                "items": [
                    {
                        "trace_id": "trace-ding-text",
                        "facts": [{"metric_key": "total_output_daily", "value": 118.0}],
                        "validation": {
                            "authorized_group": "verified",
                            "specialist_sender": "verified",
                            "content_type": "text",
                            "time_range": "matched",
                        },
                    }
                ],
                "error": None,
            },
        }

    monkeypatch.setattr(HermesDataAuditService, "_read_dingtalk_evidence", read_dingtalk_evidence)

    decision = collect_root_owner_evidence(
        db=object(),
        message_plan=_message_plan(),
        trace_id="trace-default-dingtalk-text-file",
        mes_reader=None,
        hub_reader=lambda **_kwargs: None,
    )

    assert decision.primary.source_key == "dingtalk_group_chat"
    assert decision.primary.value == {"total_output_daily": 118.0}
    assert [candidate.source_key for candidate in decision.candidates] == [
        "dingtalk_group_chat",
        "dingtalk_group_file",
    ]
    assert decision.conflicts[0]["lower_source"] == "dingtalk_group_file"
    assert decision.conflicts[0]["chosen_source"] == "dingtalk_group_chat"


def test_default_dingtalk_reader_preserves_failed_status_and_redacted_error(monkeypatch) -> None:
    def read_dingtalk_evidence(self, *, business_date):
        return {
            "dingtalk_text": {
                "status": "failed",
                "count": 0,
                "items": [],
                "error": "read failed token=secret-token password=plain-pass",
            },
            "dingtalk_file": {
                "status": "empty",
                "count": 0,
                "items": [],
                "error": None,
            },
        }

    monkeypatch.setattr(HermesDataAuditService, "_read_dingtalk_evidence", read_dingtalk_evidence)

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
    assert dingtalk_status["status"] == "partial_failed"
    assert dingtalk_status["reason"] == "source_failed"
    assert text_status["status"] == "failed"
    assert text_status["count"] == 0
    assert "token=<redacted>" in text_status["error"]
    assert "password=<redacted>" in text_status["error"]
    assert "secret-token" not in text_status["error"]
    assert "plain-pass" not in text_status["error"]


def test_mes_real_records_shape_normalizes_to_metric_fact() -> None:
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

    assert decision.primary.source_key == "mes_readonly"
    assert decision.primary.value == {"total_output_daily": 100.0}


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
