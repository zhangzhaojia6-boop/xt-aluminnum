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
    outbox_ids = iter((9001, 9002))

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
    ]

    snapshot = outcome.snapshots[0]
    assert snapshot.dispatch["status"] == "sent"
    assert snapshot.dispatch["detail"] == "all_targets_sent"
    assert snapshot.dispatch["delivery_sent_count"] == 3
    assert snapshot.dispatch["delivery_target_count"] == 3
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
