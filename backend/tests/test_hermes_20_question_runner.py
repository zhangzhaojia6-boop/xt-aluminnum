from __future__ import annotations

import inspect
import json
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import AgentRun, AgentOutboxMessage, ExternalMessageLog
from app.models.system import User
from app.services import dingtalk_service
from app.services import hermes_20_question_runner as runner
from app.services.hermes_20_question_acceptance import HermesAcceptanceQuestion
from app.services.hermes_20_question_runner import (
    DingTalkDeliveryTarget,
    build_snapshot_from_turn,
    run_20_question_acceptance,
)


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def _user() -> User:
    return User(
        id=1,
        username="root-owner",
        password_hash="x",
        name="张兆嘉",
        role="admin",
        is_active=True,
        dingtalk_user_id="dt-root-001",
    )


def _install_fake_turn(
    monkeypatch,
    db: Session,
    *,
    seen_questions: list[str] | None = None,
    seen_calls: list[dict] | None = None,
) -> None:
    def fake_turn(**kwargs):
        if seen_questions is not None:
            seen_questions.append(kwargs["text"])
        if seen_calls is not None:
            seen_calls.append(dict(kwargs))
        trace_id = kwargs["trace_id"]
        outbox = AgentOutboxMessage(
            dispatch_key=f"dispatch-{trace_id}",
            status="sent",
            message_type="markdown",
            title="鑫泰铝业智能大脑私聊回复",
            content="ok",
            trace_id=trace_id,
        )
        db.add(outbox)
        db.flush()
        run = AgentRun(
            trace_id=trace_id,
            agent_code="xintai-root-owner-production",
            status="answered",
            status_color="green",
            answer=f"鑫泰铝业智能大脑回答。来源：钉钉群聊天内容。状态：confirmed。追踪编号：{trace_id}",
            result_payload={
                "recognition": {
                    "domain": "production",
                    "metric_keys": ["total_output_daily"],
                    "business_date": "2026-06-27",
                    "needs_clarification": False,
                },
                "evidence": {
                    "primary_source": "dingtalk_group_chat",
                    "primary": {
                        "source_key": "dingtalk_group_chat",
                        "source_type": "dingtalk_group_content",
                        "status": "ok",
                        "value": {"total_output_daily": 118.0},
                        "trace_ref": {"trace_id": f"source-{trace_id}"},
                    },
                    "candidate_sources": ["dingtalk_group_chat", "mes_readonly"],
                    "missing_sources": [],
                    "conflicts": [],
                    "trace": {
                        "source_order": ["dingtalk_group_chat", "mes_readonly"],
                        "source_status": {"mes_readonly": {"status": "ok"}},
                    },
                },
            },
        )
        db.add(run)
        db.add(
            ExternalMessageLog(
                outbox_message_id=outbox.id,
                channel_type="dingtalk_group",
                channel_key="test-group",
                status="sent",
                detail="ok",
            )
        )
        db.commit()
        return SimpleNamespace(
            trace_id=trace_id,
            status="answered",
            answer=run.answer,
            chat_inbox_id=1,
            agent_run_id=run.id,
            outbox_message_id=outbox.id,
            dispatch_status="sent",
            dispatch_detail="ok",
        )

    monkeypatch.setattr(runner, "run_root_owner_production_turn", lambda *args, **kwargs: fake_turn(**kwargs))


def test_acceptance_scopes_context_to_one_run_and_preserves_relative_date_target(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()
    seen_calls: list[dict] = []
    _install_fake_turn(monkeypatch, db, seen_calls=seen_calls)
    monkeypatch.setattr(
        runner,
        "build_20_question_catalog",
        lambda: (
            HermesAcceptanceQuestion(
                1,
                "今天全厂总产量是多少？",
                ("total_output_daily",),
                "production",
                True,
                True,
                follow_up_utterances=("接着上一个问题，把证据编号给我",),
                default_business_date_offset_days=1,
            ),
        ),
    )

    run_20_question_acceptance(
        db,
        current_user=db.get(User, 1),
        sender_external_id="dt-root-001",
        business_date=date(2026, 6, 27),
    )

    context_scope_ids = [call["context_scope_id"] for call in seen_calls]
    assert context_scope_ids[0]
    assert context_scope_ids[0] == context_scope_ids[1]
    assert [call["default_business_date"] for call in seen_calls] == [
        date(2026, 6, 28),
        date(2026, 6, 28),
    ]


def test_runner_builds_snapshots_from_existing_turn_outputs(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()
    _install_fake_turn(monkeypatch, db)

    outcome = run_20_question_acceptance(
        db,
        current_user=db.get(User, 1),
        sender_external_id="dt-root-001",
        business_date=date(2026, 6, 27),
        limit=1,
        source_health={"energy_readonly": {"status": "disabled", "failure_reason": "source_not_configured"}},
    )

    assert outcome.summary.total == 20
    assert len(outcome.snapshots) == 1
    assert outcome.snapshots[0].question_id == 1
    assert outcome.snapshots[0].dispatch["log_status"] == "sent"
    assert outcome.snapshots[0].fact_answer[0]["value"] == 118.0
    assert outcome.snapshots[0].fact_answer[0]["trace_id"] == "source-hermes-20q-2026-06-27-01"
    assert outcome.snapshots[0].fact_answer[0]["source_trace_id"] is None
    assert outcome.summary.core_passed is False
    assert outcome.summary.delivery_passed is False


def test_acceptance_diagnostics_exposes_gate_reasons_without_raw_messages_or_secrets(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()
    _install_fake_turn(monkeypatch, db)
    outcome = run_20_question_acceptance(
        db,
        current_user=db.get(User, 1),
        sender_external_id="dt-root-001",
        business_date=date(2026, 6, 27),
        limit=1,
    )
    snapshot = outcome.snapshots[0]
    snapshot.recognition["api_token"] = "recognition-secret"
    snapshot.evidence["trace"]["source_status"]["mes_readonly"]["error"] = (
        "read failed token=mes-secret password=mes-password"
    )
    snapshot.evidence["trace"]["supporting_evidence"] = [
        {"text": "raw group message token=group-secret"}
    ]
    snapshot.dispatch["channel_key"] = "https://example.test/?access_token=channel-secret"
    snapshot.dispatch["detail"] = (
        "provider response token=provider-secret "
        "access_token=access-secret signature=signature-secret sign=sign-secret "
        "https://oapi.dingtalk.com/robot/send?access_token=url-secret&sign=url-sign-secret"
    )

    diagnostics = runner.build_acceptance_diagnostics(outcome)
    serialized = json.dumps(diagnostics, ensure_ascii=False)

    assert diagnostics["summary"]["core_pass_count"] == 0
    assert diagnostics["questions"][0]["gates"][0]["name"] == "understanding"
    assert diagnostics["questions"][0]["source"]["source_order"] == [
        "dingtalk_group_chat",
        "mes_readonly",
    ]
    assert diagnostics["questions"][0]["fact_answer"][0]["field"] == "total_output_daily"
    dispatch = diagnostics["questions"][0]["dispatch"]
    assert dispatch["status"] == "sent"
    assert dispatch["log_status"] == "sent"
    assert dispatch["channel_type"] == "dingtalk_group"
    assert "token=<redacted>" in dispatch["detail"]
    assert "access_token=<redacted>" in dispatch["detail"]
    assert "signature=<redacted>" in dispatch["detail"]
    assert "sign=<redacted>" in dispatch["detail"]
    assert "answer" not in diagnostics["questions"][0]
    assert "supporting_evidence" not in serialized
    assert "channel_key" not in serialized
    assert "api_token" not in serialized
    assert "recognition-secret" not in serialized
    assert "mes-secret" not in serialized
    assert "mes-password" not in serialized
    assert "group-secret" not in serialized
    assert "channel-secret" not in serialized
    assert "provider-secret" not in serialized
    assert "access-secret" not in serialized
    assert "signature-secret" not in serialized
    assert "sign-secret" not in serialized
    assert "url-secret" not in serialized
    assert "url-sign-secret" not in serialized
    assert "token=<redacted>" in serialized
    assert "password=<redacted>" in serialized


def test_preflight_acceptance_diagnostics_keeps_normal_summary_schema_and_redacts_reason() -> None:
    diagnostics = runner.build_preflight_acceptance_diagnostics(
        "DingTalk access_token=preflight-secret"
    )

    assert diagnostics == {
        "status": "preflight_failed",
        "failure_reason": "DingTalk access_token=<redacted>",
        "summary": {
            "core_passed": False,
            "delivery_passed": False,
            "core_pass_count": 0,
            "delivery_success_count": 0,
            "environment_failure_count": 0,
            "total": 20,
            "results": [],
        },
        "questions": [],
    }


def test_runner_exercises_source_trust_question(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()
    seen_questions: list[str] = []
    _install_fake_turn(monkeypatch, db, seen_questions=seen_questions)

    outcome = run_20_question_acceptance(
        db,
        current_user=db.get(User, 1),
        sender_external_id="dt-root-001",
        business_date=date(2026, 6, 27),
    )

    trust_questions = [
        question for question in runner.build_20_question_catalog()
        if question.question == "今天哪个关键数字最不可信？"
    ]
    assert len(trust_questions) == 1
    assert seen_questions.count("今天哪个关键数字最不可信？") == 1
    assert trust_questions[0].question_id in {snapshot.question_id for snapshot in outcome.snapshots}


def test_runner_executes_natural_utterances_without_adding_business_cases(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()
    seen_questions: list[str] = []
    _install_fake_turn(monkeypatch, db, seen_questions=seen_questions)

    outcome = run_20_question_acceptance(
        db,
        current_user=db.get(User, 1),
        sender_external_id="dt-root-001",
        business_date=date(2026, 6, 27),
    )

    assert {
        "昨天一共出了多少？",
        "那入库呢？",
        "电用了多少度，和群文件对得上吗",
        "成品率咋这么高，帮我查下是不是口径错了",
        "接着上一个问题，把证据编号给我",
    }.issubset(seen_questions)
    assert len(seen_questions) == 21
    assert len(outcome.snapshots) == 20
    assert outcome.summary.total == 20


def test_runner_passes_mes_reader_to_each_production_turn(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()
    mes_reader = object()
    seen_mes_readers = []

    monkeypatch.setattr(runner, "_build_mes_reader", lambda: mes_reader)

    def fake_turn(**kwargs):
        seen_mes_readers.append(kwargs["mes_reader"])
        trace_id = kwargs["trace_id"]
        outbox = AgentOutboxMessage(
            dispatch_key=f"dispatch-{trace_id}",
            status="sent",
            message_type="markdown",
            title="鑫泰铝业智能大脑私聊回复",
            content="ok",
            trace_id=trace_id,
        )
        db.add(outbox)
        db.flush()
        run = AgentRun(
            trace_id=trace_id,
            agent_code="xintai-root-owner-production",
            status="answered",
            status_color="green",
            answer=f"鑫泰铝业智能大脑回答。来源：MES/WMS 只读链路。状态：confirmed。追踪编号：{trace_id}。",
            result_payload={
                "recognition": {
                    "domain": "production",
                    "metric_keys": ["total_output_daily"],
                    "business_date": "2026-06-27",
                    "needs_clarification": False,
                },
                "evidence": {
                    "primary_source": "mes_readonly",
                    "primary": {
                        "source_key": "mes_readonly",
                        "source_type": "external_readonly",
                        "status": "ok",
                        "value": {"total_output_daily": 100.0},
                        "trace_ref": {"trace_id": f"source-{trace_id}"},
                    },
                    "candidate_sources": ["mes_readonly"],
                    "missing_sources": [],
                    "conflicts": [],
                    "trace": {
                        "source_order": ["mes_readonly"],
                        "source_status": {"mes_readonly": {"status": "ok"}},
                    },
                },
            },
        )
        db.add(run)
        db.commit()
        return SimpleNamespace(
            trace_id=trace_id,
            status="answered",
            answer=run.answer,
            chat_inbox_id=1,
            agent_run_id=run.id,
            outbox_message_id=outbox.id,
            dispatch_status="sent",
            dispatch_detail="ok",
        )

    monkeypatch.setattr(runner, "run_root_owner_production_turn", lambda *args, **kwargs: fake_turn(**kwargs))

    outcome = run_20_question_acceptance(
        db,
        current_user=db.get(User, 1),
        sender_external_id="dt-root-001",
        business_date=date(2026, 6, 27),
        limit=1,
    )

    assert seen_mes_readers == [mes_reader]
    assert outcome.snapshots[0].evidence["primary_source"] == "mes_readonly"


def test_snapshot_uses_persisted_primary_fact_instead_of_answer_text() -> None:
    db = _db_session()
    trace_id = "trace-structured-fact"
    db.add(
        AgentRun(
            trace_id=trace_id,
            agent_code="xintai-root-owner-production",
            status="answered",
            status_color="green",
            answer="鑫泰铝业智能大脑回答：昨天一共出了 999999 吨。",
            result_payload={
                "recognition": {
                    "domain": "production",
                    "metric_keys": ["total_output_daily"],
                    "business_date": "2026-06-26",
                    "needs_clarification": False,
                },
                "evidence": {
                    "primary_source": "mes_readonly",
                    "primary": {
                        "source_key": "mes_readonly",
                        "source_type": "external_readonly",
                        "status": "ok",
                        "value": {
                            "total_output_daily": {
                                "value": 118.0,
                                "unit": "吨",
                                "source_type": "mes_packaging_output",
                                "source_ref": {
                                    "source_ref": "mes_workshop_process_records",
                                    "source_table": "MES_ProductProcessRecord",
                                    "business_date": "2026-06-26",
                                    "business_window": "2026-06-26T07:50:00+08:00/2026-06-27T07:50:00+08:00",
                                    "unit": "吨",
                                    "metric_contract_version": "2026-07-11",
                                    "row_count": 1,
                                    "latest_row_id": 118,
                                    "trace_id": "projection-read:mes_workshop_process_records:118:1",
                                },
                                "source_detail": {
                                    "source_ref": "mes_workshop_process_records",
                                    "business_window": "2026-06-26T07:50:00+08:00/2026-06-27T07:50:00+08:00",
                                    "unit": "吨",
                                    "trace_id": "projection-read:mes_workshop_process_records:118:1",
                                    "metric_contract_version": "2026-07-11",
                                },
                            }
                        },
                        "trace_ref": {
                            "source_trace_id": "source-trace-118",
                            "trace_id": "secondary-source-trace",
                        },
                    },
                    "candidate_sources": ["mes_readonly"],
                    "missing_sources": [],
                    "conflicts": [],
                    "trace": {
                        "trace_id": trace_id,
                        "source_order": ["mes_readonly"],
                        "source_status": {"mes_readonly": {"status": "ok"}},
                    },
                },
            },
        )
    )
    db.commit()

    snapshot = build_snapshot_from_turn(
        db,
        question_id=1,
        trace_id=trace_id,
        status="answered",
        answer="文字里是 999999，但不能从文字猜数",
        outbox_message_id=None,
        source_health={},
        required_source_health=(),
    )

    assert snapshot.fact_answer == [
        {
            "question_id": 1,
            "field": "total_output_daily",
            "status": "confirmed",
            "value": 118.0,
            "source": "mes_readonly",
            "source_key": "mes_readonly",
            "source_type": "mes_packaging_output",
            "source_ref": {
                "source_ref": "mes_workshop_process_records",
                "source_table": "MES_ProductProcessRecord",
                "business_date": "2026-06-26",
                "business_window": "2026-06-26T07:50:00+08:00/2026-06-27T07:50:00+08:00",
                "unit": "吨",
                "metric_contract_version": "2026-07-11",
                "row_count": 1,
                "latest_row_id": 118,
                "trace_id": "projection-read:mes_workshop_process_records:118:1",
            },
            "business_date": "2026-06-26",
            "business_window": "2026-06-26T07:50:00+08:00/2026-06-27T07:50:00+08:00",
            "unit": "吨",
            "metric_contract_version": "2026-07-11",
            "trace_id": "projection-read:mes_workshop_process_records:118:1",
            "source_trace_id": "source-trace-118",
            "reason": None,
            "action": None,
        }
    ]


def test_runner_uses_fact_validator_and_never_backfills_missing_primary_metadata() -> None:
    records = runner._build_fact_answer(
        question_id=1,
        turn_trace_id="turn-trace-must-not-fill-fact",
        recognition={
            "metric_keys": ["total_output_daily"],
            "business_date": "2026-06-26",
        },
        evidence={
            "primary": {
                "source_key": "mes_readonly",
                "source_type": "external_readonly",
                "status": "ok",
                "value": {
                    "total_output_daily": {
                        "value": 118.0,
                        "unit": "吨",
                        "source_type": "mes_packaging_output",
                        "source_ref": {
                            "source_ref": "mes_workshop_process_records",
                            "source_table": "MES_ProductProcessRecord",
                            "business_window": "2026-06-26T07:50:00+08:00/2026-06-27T07:50:00+08:00",
                            "unit": "吨",
                            "metric_contract_version": "2026-07-11",
                            "row_count": 1,
                            "latest_row_id": 118,
                            "trace_id": "projection-read:mes_workshop_process_records:118:1",
                        },
                        "source_detail": {
                            "source_ref": "mes_workshop_process_records",
                            "unit": "吨",
                            "trace_id": "projection-read:mes_workshop_process_records:118:1",
                        },
                    }
                },
                "trace_ref": {},
            },
            "trace": {"trace_id": "turn-trace-must-not-fill-fact", "source_order": ["mes_readonly"]},
        },
    )

    assert records[0]["business_date"] is None
    assert records[0]["business_window"] == (
        "2026-06-26T07:50:00+08:00/2026-06-27T07:50:00+08:00"
    )
    assert records[0]["metric_contract_version"] == "2026-07-11"
    assert records[0]["status"] == "missing"
    assert "business_date" in records[0]["reason"]


def test_runner_keeps_confirmable_structured_value_kinds_from_primary_fact() -> None:
    business_window = "2026-06-26T07:50:00+08:00/2026-06-27T07:50:00+08:00"
    trace_id = "dingtalk-evidence-208"

    def field_fact(value, *, unit=None):
        return {
            "value": value,
            "source_key": "dingtalk_group_content",
            "source_type": "dingtalk_supplement",
            "source_ref": {
                "source_key": "dingtalk_group_content",
                "evidence_id": 208,
                "trace_id": trace_id,
                "business_date": "2026-06-26",
            },
            "business_date": "2026-06-26",
            "business_window": business_window,
            "unit": unit,
            "metric_contract_version": "2026-07-11",
            "trace_id": trace_id,
            "status": "ok",
        }

    records = runner._build_fact_answer(
        question_id=4,
        turn_trace_id="turn-trace-not-used",
        recognition={
            "metric_keys": [
                "workshop_output_daily",
                "anomaly_explanation_daily",
                "dingtalk_specialist_evidence",
            ]
        },
        evidence={
            "primary": {
                "source_key": "dingtalk_group_content",
                "source_type": "dingtalk_supplement",
                "status": "ok",
                "value": {
                    "workshop_output_daily": field_fact(
                        {"熔铸": 61.0, "精整": 57.0},
                        unit="吨",
                    ),
                    "anomaly_explanation_daily": field_fact("停机检修造成产量波动"),
                    "dingtalk_specialist_evidence": field_fact(
                        [{"evidence_id": 208, "summary": "设备群确认检修"}]
                    ),
                },
                "trace_ref": {},
            }
        },
    )

    assert [record["status"] for record in records] == [
        "confirmed",
        "confirmed",
        "confirmed",
    ]
    assert records[0]["value"] == {"熔铸": 61.0, "精整": 57.0}
    assert records[1]["value"] == "停机检修造成产量波动"
    assert records[2]["value"] == [
        {"evidence_id": 208, "summary": "设备群确认检修"}
    ]


def test_snapshot_keeps_missing_details_empty_when_primary_does_not_contain_requested_field() -> None:
    db = _db_session()
    trace_id = "trace-primary-wrong-field"
    db.add(
        AgentRun(
            trace_id=trace_id,
            agent_code="xintai-root-owner-production",
            status="answered",
            status_color="green",
            answer="回答文字声称总产量 777 吨",
            result_payload={
                "recognition": {
                    "domain": "production",
                    "metric_keys": ["total_output_daily"],
                    "business_date": "2026-06-27",
                    "needs_clarification": False,
                },
                "evidence": {
                    "primary_source": "mes_readonly",
                    "primary": {
                        "source_key": "mes_readonly",
                        "source_type": "external_readonly",
                        "status": "ok",
                        "value": {"finished_inbound_daily": 777.0},
                        "trace_ref": {"trace_id": "source-trace-wrong-field"},
                    },
                    "candidate_sources": ["mes_readonly"],
                    "missing_sources": [],
                    "conflicts": [],
                    "trace": {"trace_id": trace_id, "source_order": ["mes_readonly"]},
                },
            },
        )
    )
    db.commit()

    snapshot = build_snapshot_from_turn(
        db,
        question_id=1,
        trace_id=trace_id,
        status="answered",
        answer="总产量 777 吨",
        outbox_message_id=None,
        source_health={},
        required_source_health=(),
    )

    assert len(snapshot.fact_answer) == 1
    assert snapshot.fact_answer[0]["field"] == "total_output_daily"
    assert snapshot.fact_answer[0]["status"] == "missing"
    assert snapshot.fact_answer[0]["value"] is None
    assert snapshot.fact_answer[0]["source"] is None
    assert snapshot.fact_answer[0]["reason"] is None
    assert snapshot.fact_answer[0]["action"] is None


def test_snapshot_uses_structured_recognition_clarification_as_missing_action() -> None:
    db = _db_session()
    trace_id = "trace-recognition-action"
    db.add(
        AgentRun(
            trace_id=trace_id,
            agent_code="xintai-root-owner-production",
            status="clarification",
            status_color="yellow",
            answer="请明确要查询的业务日期。",
            result_payload={
                "recognition": {
                    "domain": "production",
                    "metric_keys": ["total_output_daily"],
                    "business_date": "2026-06-27",
                    "needs_clarification": True,
                    "clarification_question": "请明确要查询的业务日期。",
                },
                "evidence": {
                    "primary_source": None,
                    "primary": None,
                    "candidate_sources": [],
                    "missing_sources": ["mes_readonly"],
                    "conflicts": [],
                    "trace": {"trace_id": trace_id, "source_order": []},
                },
            },
        )
    )
    db.commit()

    snapshot = build_snapshot_from_turn(
        db,
        question_id=1,
        trace_id=trace_id,
        status="clarification",
        answer="回答文字里的动作不能代替 recognition payload。",
        outbox_message_id=None,
        source_health={},
        required_source_health=(),
    )

    assert snapshot.fact_answer[0]["status"] == "missing"
    assert snapshot.fact_answer[0]["action"] == "请明确要查询的业务日期。"


def test_snapshot_builds_one_fact_record_per_recognized_field() -> None:
    db = _db_session()
    trace_id = "trace-two-fields"
    db.add(
        AgentRun(
            trace_id=trace_id,
            agent_code="xintai-root-owner-production",
            status="answered",
            status_color="green",
            answer="产量和入库已核对",
            result_payload={
                "recognition": {
                    "domain": "anomaly",
                    "metric_keys": ["total_output_daily", "finished_inbound_daily"],
                    "business_date": "2026-06-27",
                    "needs_clarification": False,
                },
                "evidence": {
                    "primary_source": "mes_readonly",
                    "primary": {
                        "source_key": "mes_readonly",
                        "source_type": "external_readonly",
                        "status": "ok",
                        "value": {
                            "total_output_daily": {
                                "value": 118.0,
                                "unit": "吨",
                                "source_type": "mes_packaging_output",
                                "source_ref": {
                                    "source_ref": "mes_workshop_process_records",
                                    "source_table": "MES_ProductProcessRecord",
                                    "business_date": "2026-06-27",
                                    "business_window": "2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00",
                                    "unit": "吨",
                                    "metric_contract_version": "2026-07-11",
                                    "row_count": 1,
                                    "latest_row_id": 118,
                                    "trace_id": "projection-read:mes_workshop_process_records:118:1",
                                },
                                "source_detail": {
                                    "business_window": "2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00",
                                    "trace_id": "projection-read:mes_workshop_process_records:118:1",
                                    "metric_contract_version": "2026-07-11",
                                },
                            },
                            "finished_inbound_daily": {
                                "value": 110.0,
                                "unit": "吨",
                                "source_type": "mes_stock_records",
                                "source_ref": {
                                    "source_ref": "mes_stock_records",
                                    "source_table": "WMS_InStockDetail",
                                    "business_date": "2026-06-27",
                                    "business_window": "2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00",
                                    "unit": "吨",
                                    "metric_contract_version": "2026-07-11",
                                    "row_count": 1,
                                    "latest_row_id": 110,
                                    "trace_id": "projection-read:mes_stock_records:110:1",
                                },
                                "source_detail": {
                                    "business_window": "2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00",
                                    "trace_id": "projection-read:mes_stock_records:110:1",
                                    "metric_contract_version": "2026-07-11",
                                },
                            },
                        },
                        "trace_ref": {},
                    },
                    "candidate_sources": ["mes_readonly"],
                    "missing_sources": [],
                    "conflicts": [],
                    "trace": {"trace_id": trace_id, "source_order": ["mes_readonly"]},
                },
            },
        )
    )
    db.commit()

    snapshot = build_snapshot_from_turn(
        db,
        question_id=17,
        trace_id=trace_id,
        status="answered",
        answer="产量和入库已核对",
        outbox_message_id=None,
        source_health={},
        required_source_health=(),
    )

    assert [record["field"] for record in snapshot.fact_answer] == [
        "total_output_daily",
        "finished_inbound_daily",
    ]
    assert [record["value"] for record in snapshot.fact_answer] == [118.0, 110.0]
    assert [record["status"] for record in snapshot.fact_answer] == ["confirmed", "confirmed"]
    assert [record["trace_id"] for record in snapshot.fact_answer] == [
        "projection-read:mes_workshop_process_records:118:1",
        "projection-read:mes_stock_records:110:1",
    ]


def test_fact_answer_selects_highest_priority_candidate_per_field() -> None:
    business_window = "2026-06-27T07:50:00+08:00/2026-06-28T07:50:00+08:00"
    dingtalk_trace = "dingtalk-fact-input-71"
    projection_trace = "projection-read:mes_workshop_process_records:118:13"

    records = runner._build_fact_answer(
        question_id=99,
        turn_trace_id="turn-per-field-evidence",
        recognition={
            "metric_keys": ["daily_input_weight", "total_output_daily"],
            "business_date": "2026-06-27",
        },
        evidence={
            "primary": {
                "source_key": "dingtalk_group_content",
                "source_type": "dingtalk_supplement",
                "status": "ok",
                "value": {
                    "daily_input_weight": {
                        "value": 560.0,
                        "source_key": "dingtalk_group_content",
                        "source_type": "dingtalk_supplement",
                        "source_ref": {
                            "source_key": "dingtalk_group_content",
                            "evidence_id": 71,
                            "trace_id": dingtalk_trace,
                            "business_date": "2026-06-27",
                        },
                        "business_date": "2026-06-27",
                        "business_window": business_window,
                        "unit": "吨",
                        "metric_contract_version": "2026-07-11",
                        "trace_id": dingtalk_trace,
                        "status": "ok",
                    }
                },
                "trace_ref": {},
            },
            "candidate_facts": [
                {
                    "source_key": "dingtalk_group_content",
                    "source_type": "dingtalk_supplement",
                    "status": "ok",
                    "value": {
                        "daily_input_weight": {
                            "value": 560.0,
                            "source_key": "dingtalk_group_content",
                            "source_type": "dingtalk_supplement",
                            "source_ref": {
                                "source_key": "dingtalk_group_content",
                                "evidence_id": 71,
                                "trace_id": dingtalk_trace,
                                "business_date": "2026-06-27",
                            },
                            "business_date": "2026-06-27",
                            "business_window": business_window,
                            "unit": "吨",
                            "metric_contract_version": "2026-07-11",
                            "trace_id": dingtalk_trace,
                            "status": "ok",
                        }
                    },
                    "trace_ref": {},
                },
                {
                    "source_key": "data_hub_projection",
                    "source_type": "mes_packaging_output",
                    "status": "ok",
                    "value": {
                        "total_output_daily": {
                            "value": 286.0,
                            "source_key": "data_hub_projection",
                            "source_type": "mes_packaging_output",
                            "source_ref": {
                                "source_ref": "mes_workshop_process_records",
                                "source_table": "MES_ProductProcessRecord",
                                "business_date": "2026-06-27",
                                "business_window": business_window,
                                "unit": "吨",
                                "metric_contract_version": "2026-07-11",
                                "row_count": 13,
                                "latest_row_id": 118,
                                "trace_id": projection_trace,
                            },
                            "business_date": "2026-06-27",
                            "business_window": business_window,
                            "unit": "吨",
                            "metric_contract_version": "2026-07-11",
                            "trace_id": projection_trace,
                            "status": "ok",
                        }
                    },
                    "trace_ref": {},
                },
            ],
            "conflicts": [],
            "missing_sources": [],
        },
    )

    assert [record["field"] for record in records] == [
        "daily_input_weight",
        "total_output_daily",
    ]
    assert [record["status"] for record in records] == ["confirmed", "confirmed"]
    assert [record["source_key"] for record in records] == [
        "dingtalk_group_content",
        "data_hub_projection",
    ]
    assert [record["value"] for record in records] == [560.0, 286.0]


def test_runner_rejects_unsupported_delivery_target_channel_type(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()
    _install_fake_turn(monkeypatch, db)

    def fail_register_agent(*args, **kwargs):
        raise AssertionError("register_agent should not run")

    monkeypatch.setattr(runner.agent_communication_service, "register_agent", fail_register_agent)

    try:
        run_20_question_acceptance(
            db,
            current_user=db.get(User, 1),
            sender_external_id="dt-root-001",
            business_date=date(2026, 6, 27),
            limit=1,
            delivery_targets=[DingTalkDeliveryTarget(channel_type="email", channel_key="ops@example.com")],
        )
    except ValueError as exc:
        assert str(exc) == "unsupported delivery target channel_type: email"
    else:
        raise AssertionError("expected ValueError for unsupported channel_type")


def test_runner_dispatches_delivery_targets_via_agent_communication_service(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()
    _install_fake_turn(monkeypatch, db)

    call_order: list[tuple[str, str, str]] = []
    dedupe_keys: list[str] = []
    outbox_ids = iter((9001, 9002, 9003))

    def fake_register_agent(*args, **kwargs):
        assert kwargs["code"] == "hermes_20_question_acceptance"
        call_order.append(("register_agent", kwargs["code"], ""))
        return SimpleNamespace(code=kwargs["code"])

    def fake_register_channel(*args, **kwargs):
        if kwargs["channel_key"] == "factory-group":
            assert kwargs["target_type"] == "production_acceptance"
            assert kwargs["target_key"] == "production-group"
            assert kwargs["name"] == "生产验收群"
        if kwargs["channel_type"] == "dingtalk_custom_robot":
            assert "https://example.test/robot" not in kwargs["name"]
            assert kwargs["target_key"] == "hermes_20_question_acceptance"
        call_order.append(("register_channel", kwargs["channel_type"], kwargs["channel_key"]))
        return SimpleNamespace(channel_type=kwargs["channel_type"], channel_key=kwargs["channel_key"])

    def fake_bind(*args, **kwargs):
        call_order.append(("bind_agent_to_channel", kwargs["channel_type"], kwargs["channel_key"]))
        return SimpleNamespace()

    def fake_queue(*args, **kwargs):
        dedupe_keys.append(kwargs["dedupe_key"])
        call_order.append(("queue_bound_message", kwargs["channel_type"], kwargs["channel_key"]))
        return SimpleNamespace(id=next(outbox_ids))

    def fake_dispatch(*args, **kwargs):
        outbox_message_id = args[1]
        call_order.append(("dispatch_outbox_message", str(outbox_message_id), ""))
        return SimpleNamespace(status="sent", detail="queued", outbox_message_id=outbox_message_id)

    def fake_list_logs(*args, **kwargs):
        outbox_message_id = kwargs["outbox_message_id"]
        call_order.append(("list_external_logs", str(outbox_message_id), ""))
        return [SimpleNamespace(status="sent")]

    def fail_send_group_message(*args, **kwargs):
        raise AssertionError("runner must not call dingtalk_service.send_group_message directly")

    def fail_send_work_notification(*args, **kwargs):
        raise AssertionError("runner must not call dingtalk_service.send_work_notification directly")

    monkeypatch.setattr(runner.agent_communication_service, "register_agent", fake_register_agent)
    monkeypatch.setattr(runner.agent_communication_service, "register_channel", fake_register_channel)
    monkeypatch.setattr(runner.agent_communication_service, "bind_agent_to_channel", fake_bind)
    monkeypatch.setattr(runner.agent_communication_service, "queue_bound_message", fake_queue)
    monkeypatch.setattr(runner.agent_communication_service, "dispatch_outbox_message", fake_dispatch)
    monkeypatch.setattr(runner.agent_communication_service, "list_external_logs", fake_list_logs)
    monkeypatch.setattr(dingtalk_service, "send_group_message", fail_send_group_message)
    monkeypatch.setattr(dingtalk_service, "send_work_notification", fail_send_work_notification)

    outcome = run_20_question_acceptance(
        db,
        current_user=db.get(User, 1),
        sender_external_id="dt-root-001",
        business_date=date(2026, 6, 27),
        limit=1,
        delivery_targets=[
            DingTalkDeliveryTarget(
                channel_type="dingtalk_group",
                channel_key="factory-group",
                target_type="production_acceptance",
                target_key="production-group",
                name="生产验收群",
            ),
            DingTalkDeliveryTarget(channel_type="dingtalk_work_notice", channel_key="dt-user-001"),
            DingTalkDeliveryTarget(channel_type="dingtalk_custom_robot", channel_key="https://example.test/robot"),
        ],
    )

    assert call_order == [
        ("register_agent", "hermes_20_question_acceptance", ""),
        ("register_channel", "dingtalk_group", "factory-group"),
        ("bind_agent_to_channel", "dingtalk_group", "factory-group"),
        ("queue_bound_message", "dingtalk_group", "factory-group"),
        ("dispatch_outbox_message", "9001", ""),
        ("list_external_logs", "9001", ""),
        ("register_channel", "dingtalk_work_notice", "dt-user-001"),
        ("bind_agent_to_channel", "dingtalk_work_notice", "dt-user-001"),
        ("queue_bound_message", "dingtalk_work_notice", "dt-user-001"),
        ("dispatch_outbox_message", "9002", ""),
        ("list_external_logs", "9002", ""),
        ("register_channel", "dingtalk_custom_robot", "https://example.test/robot"),
        ("bind_agent_to_channel", "dingtalk_custom_robot", "https://example.test/robot"),
        ("queue_bound_message", "dingtalk_custom_robot", "https://example.test/robot"),
        ("dispatch_outbox_message", "9003", ""),
        ("list_external_logs", "9003", ""),
    ]
    assert all(len(item) <= 160 for item in dedupe_keys)
    assert all("https://example.test/robot" not in item for item in dedupe_keys)

    snapshot = outcome.snapshots[0]
    assert snapshot.dispatch["status"] == "sent"
    assert snapshot.dispatch["detail"] == "all_targets_sent"
    assert snapshot.dispatch["delivery_sent_count"] == 4
    assert snapshot.dispatch["delivery_target_count"] == 4
    assert snapshot.dispatch["target_results"] == [
        {
            "status": "sent",
            "detail": "queued",
            "outbox_message_id": 9001,
            "log_status": "sent",
            "channel_type": "dingtalk_group",
            "channel_key": "factory-group",
        },
        {
            "status": "sent",
            "detail": "queued",
            "outbox_message_id": 9002,
            "log_status": "sent",
            "channel_type": "dingtalk_work_notice",
            "channel_key": "dt-user-001",
        },
        {
            "status": "sent",
            "detail": "queued",
            "outbox_message_id": 9003,
            "log_status": "sent",
            "channel_type": "dingtalk_custom_robot",
            "channel_key": "https://example.test/robot",
        },
    ]


def test_runner_module_does_not_import_or_call_dingtalk_service_directly() -> None:
    source = inspect.getsource(runner)

    assert not hasattr(runner, "dingtalk_service")
    assert "dingtalk_service" not in source
    assert "send_group_message" not in source
    assert "send_work_notification" not in source


def test_acceptance_cli_requires_explicit_real_delivery_flag() -> None:
    from scripts.hermes_20_question_acceptance import parse_args

    args = parse_args(
        [
            "--business-date",
            "2026-06-27",
            "--sender-external-id",
            "dt-root-001",
            "--target",
            "test-group",
        ]
    )

    assert args.real_delivery is False


def test_acceptance_cli_parses_real_delivery_targets() -> None:
    from scripts.hermes_20_question_acceptance import parse_args, parse_delivery_targets

    args = parse_args(
        [
            "--business-date",
            "2026-06-27",
            "--sender-external-id",
            "dt-root-001",
            "--target",
            "dingtalk_group:test-group",
            "--target",
            "dingtalk_work_notice:dt-person-001",
            "--real-delivery",
        ]
    )

    assert args.real_delivery is True
    targets = parse_delivery_targets(args.target)
    assert [(target.channel_type, target.channel_key) for target in targets] == [
        ("dingtalk_group", "test-group"),
        ("dingtalk_work_notice", "dt-person-001"),
    ]


def test_acceptance_cli_parses_daily_report_gate_args() -> None:
    from scripts.hermes_20_question_acceptance import parse_args

    args = parse_args(
        [
            "--business-date",
            "2026-06-27",
            "--sender-external-id",
            "dt-root-001",
            "--target",
            "dingtalk_group:test-group",
            "--real-delivery",
            "--require-daily-report-gate",
            "--output-skill-root",
            "D:/输出skill",
            "--alignment-artifact-dir",
            "docs/superpowers/reports/daily-report-fact-closure-smoke",
        ]
    )

    assert args.require_daily_report_gate is True
    assert args.output_skill_root == "D:/输出skill"
    assert args.alignment_artifact_dir == "docs/superpowers/reports/daily-report-fact-closure-smoke"


def test_resolve_artifact_dir_rejects_absolute_path() -> None:
    from scripts.hermes_20_question_acceptance import resolve_artifact_dir

    try:
        resolve_artifact_dir("D:/temp/outside-artifacts")
    except ValueError as exc:
        assert str(exc) == "alignment_artifact_dir_outside_reports_dir"
    else:
        raise AssertionError("expected absolute artifact dir to be rejected")


def test_resolve_artifact_dir_rejects_dot_dot_escape() -> None:
    from scripts.hermes_20_question_acceptance import resolve_artifact_dir

    try:
        resolve_artifact_dir("docs/superpowers/reports/../secrets")
    except ValueError as exc:
        assert str(exc) == "alignment_artifact_dir_outside_reports_dir"
    else:
        raise AssertionError("expected parent traversal artifact dir to be rejected")


def test_build_daily_report_gate_payload_redacts_sensitive_exception_and_artifact(monkeypatch, tmp_path) -> None:
    from scripts import hermes_20_question_acceptance as cli

    sensitive = "RuntimeError: token=abc123 secret=xyz dsn=postgres://u:p@host/db"
    written_rows: list[dict[str, object]] = []

    monkeypatch.setattr(cli, "resolve_output_skill_root", lambda _value: tmp_path)
    monkeypatch.setattr(
        cli,
        "build_daily_fact_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(sensitive)),
    )
    monkeypatch.setattr(
        cli,
        "write_alignment_artifacts",
        lambda rows, _artifact_dir: written_rows.extend(rows) or {"json": "x.json", "markdown": "x.md"},
    )

    payload = cli.build_daily_report_gate_payload(
        object(),
        business_date=date(2026, 6, 27),
        output_skill_root=str(tmp_path),
        alignment_artifact_dir="docs/superpowers/reports/daily-report-fact-closure-smoke",
    )

    assert payload["status"] == "error"
    assert payload["failure_reason"] == "daily_report_gate_build_failed"
    assert "error" not in payload
    assert written_rows
    row = written_rows[0]
    text = repr({"payload": payload, "row": row})
    assert "abc123" not in text
    assert "xyz" not in text
    assert "postgres://u:p@host/db" not in text
    assert "token=<redacted>" in text
    assert "secret=<redacted>" in text
    assert "<redacted-connection-uri>" in text


def test_build_daily_report_gate_payload_records_compare_only_mode(monkeypatch, tmp_path) -> None:
    from scripts import hermes_20_question_acceptance as cli

    captured_kwargs = {}

    def fake_build_daily_fact_bundle(*_args, **kwargs):
        captured_kwargs.update(kwargs)
        return {
            "output_skill_alignment": {"status": "passed"},
            "fact_closure": {"status": "pass"},
            "gap_plan": {"status": "ready"},
            "reference_only": False,
        }

    monkeypatch.setattr(cli, "resolve_output_skill_root", lambda _value: tmp_path)
    monkeypatch.setattr(cli, "build_daily_fact_bundle", fake_build_daily_fact_bundle)

    payload = cli.build_daily_report_gate_payload(
        object(),
        business_date=date(2026, 6, 27),
        output_skill_root=str(tmp_path),
        alignment_artifact_dir=None,
    )

    assert payload["status"] == "passed"
    assert payload["reference_mode"] == "compare"
    assert payload["reference_only"] is False
    assert payload["output_skill_alignment"]["reference_mode"] == "compare"
    assert captured_kwargs["allow_output_skill_reference_adoption"] is False


def test_acceptance_cli_main_requires_real_delivery_flag_before_db(monkeypatch, capsys) -> None:
    from scripts import hermes_20_question_acceptance as cli

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: (_ for _ in ()).throw(AssertionError("db_should_not_run")))
    monkeypatch.setattr(
        cli,
        "run_20_question_acceptance",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner_should_not_run")),
    )

    exit_code = cli.main(
        [
            "--business-date",
            "2026-06-27",
            "--sender-external-id",
            "dt-root-001",
            "--target",
            "dingtalk_group:test-group",
        ]
    )

    assert exit_code == 2
    assert capsys.readouterr().out.strip() == "refusing_real_acceptance_without_real_delivery_flag"


def test_acceptance_cli_main_requires_target_before_db(monkeypatch, capsys) -> None:
    from scripts import hermes_20_question_acceptance as cli

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: (_ for _ in ()).throw(AssertionError("db_should_not_run")))
    monkeypatch.setattr(
        cli,
        "run_20_question_acceptance",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner_should_not_run")),
    )

    exit_code = cli.main(
        [
            "--business-date",
            "2026-06-27",
            "--sender-external-id",
            "dt-root-001",
            "--real-delivery",
        ]
    )

    assert exit_code == 2
    assert capsys.readouterr().out.strip() == "target_required"


def test_acceptance_cli_main_rejects_invalid_target_before_db(monkeypatch, capsys) -> None:
    from scripts import hermes_20_question_acceptance as cli

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: (_ for _ in ()).throw(AssertionError("db_should_not_run")))
    monkeypatch.setattr(
        cli,
        "run_20_question_acceptance",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner_should_not_run")),
    )

    exit_code = cli.main(
        [
            "--business-date",
            "2026-06-27",
            "--sender-external-id",
            "dt-root-001",
            "--target",
            "bad-target",
            "--real-delivery",
        ]
    )

    assert exit_code == 2
    assert capsys.readouterr().out.strip() == "target_must_use_channel_type_colon_key"


def test_acceptance_cli_main_rejects_report_path_outside_reports_dir_before_db(monkeypatch, capsys) -> None:
    from scripts import hermes_20_question_acceptance as cli

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: (_ for _ in ()).throw(AssertionError("db_should_not_run")))
    monkeypatch.setattr(
        cli,
        "run_20_question_acceptance",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner_should_not_run")),
    )

    exit_code = cli.main(
        [
            "--business-date",
            "2026-06-27",
            "--sender-external-id",
            "dt-root-001",
            "--target",
            "dingtalk_group:test-group",
            "--real-delivery",
            "--report-path",
            "../outside.md",
        ]
    )

    assert exit_code == 2
    assert capsys.readouterr().out.strip() == "report_path_outside_reports_dir"


def test_acceptance_cli_main_attaches_daily_report_gate_when_required(monkeypatch, tmp_path) -> None:
    from scripts import hermes_20_question_acceptance as cli

    db = _db_session()
    db.add(_user())
    db.commit()

    class _SessionFactory:
        def __call__(self):
            return self

        def __enter__(self):
            return db

        def __exit__(self, exc_type, exc, tb):
            return False

    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: _SessionFactory())
    monkeypatch.setattr(cli, "resolve_report_path", lambda _value: tmp_path / "report.md")
    monkeypatch.setattr(
        cli,
        "build_daily_report_gate_payload",
        lambda *_args, **_kwargs: {
            "source_key": "daily_report_gate",
            "status": "passed",
            "business_date": "2026-06-27",
            "output_skill_alignment": {"status": "passed", "reference_mode": "compare"},
            "fact_closure": {"status": "pass"},
            "gap_plan": {"status": "ready"},
        },
    )
    monkeypatch.setattr(
        cli,
        "health_check_sources",
        lambda *_args, **_kwargs: {"mes_readonly": {"status": "unknown"}},
    )
    monkeypatch.setattr(cli, "render_acceptance_report", lambda _summary: "# report\n")

    def fake_run(*_args, **kwargs):
        captured["source_health"] = kwargs["source_health"]
        captured["required_source_health"] = kwargs["required_source_health"]
        return SimpleNamespace(summary=SimpleNamespace(core_passed=True, delivery_passed=True))

    monkeypatch.setattr(cli, "run_20_question_acceptance", fake_run)

    exit_code = cli.main(
        [
            "--business-date",
            "2026-06-27",
            "--sender-external-id",
            "dt-root-001",
            "--target",
            "dingtalk_group:test-group",
            "--real-delivery",
            "--require-daily-report-gate",
        ]
    )

    assert exit_code == 0
    assert captured["required_source_health"] == ("daily_report_gate",)
    assert captured["source_health"] == {
        "mes_readonly": {"status": "unknown"},
        "daily_report_gate": {
            "source_key": "daily_report_gate",
            "status": "passed",
            "business_date": "2026-06-27",
            "output_skill_alignment": {"status": "passed", "reference_mode": "compare"},
            "fact_closure": {"status": "pass"},
            "gap_plan": {"status": "ready"},
        },
    }


def test_acceptance_cli_main_rejects_artifact_dir_outside_reports_dir_before_db(monkeypatch, capsys) -> None:
    from scripts import hermes_20_question_acceptance as cli

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: (_ for _ in ()).throw(AssertionError("db_should_not_run")))
    monkeypatch.setattr(
        cli,
        "run_20_question_acceptance",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner_should_not_run")),
    )

    exit_code = cli.main(
        [
            "--business-date",
            "2026-06-27",
            "--sender-external-id",
            "dt-root-001",
            "--target",
            "dingtalk_group:test-group",
            "--real-delivery",
            "--alignment-artifact-dir",
            "../outside",
        ]
    )

    assert exit_code == 2
    assert capsys.readouterr().out.strip() == "alignment_artifact_dir_outside_reports_dir"
