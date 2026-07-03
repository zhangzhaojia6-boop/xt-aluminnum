from __future__ import annotations

import inspect
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import AgentRun, AgentOutboxMessage, ExternalMessageLog
from app.models.system import User
from app.services import dingtalk_service
from app.services import hermes_20_question_runner as runner
from app.services.hermes_20_question_runner import DingTalkDeliveryTarget, run_20_question_acceptance


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


def _install_fake_turn(monkeypatch, db: Session) -> None:
    def fake_turn(**kwargs):
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
    outbox_ids = iter((9001, 9002, 9003))

    def fake_register_agent(*args, **kwargs):
        assert kwargs["code"] == "hermes_20_question_acceptance"
        call_order.append(("register_agent", kwargs["code"], ""))
        return SimpleNamespace(code=kwargs["code"])

    def fake_register_channel(*args, **kwargs):
        call_order.append(("register_channel", kwargs["channel_type"], kwargs["channel_key"]))
        return SimpleNamespace(channel_type=kwargs["channel_type"], channel_key=kwargs["channel_key"])

    def fake_bind(*args, **kwargs):
        call_order.append(("bind_agent_to_channel", kwargs["channel_type"], kwargs["channel_key"]))
        return SimpleNamespace()

    def fake_queue(*args, **kwargs):
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
            DingTalkDeliveryTarget(channel_type="dingtalk_group", channel_key="factory-group"),
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
            "output_skill_alignment": {"status": "passed"},
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
            "output_skill_alignment": {"status": "passed"},
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
