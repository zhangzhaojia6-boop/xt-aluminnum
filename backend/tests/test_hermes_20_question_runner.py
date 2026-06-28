from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import AgentRun, AgentOutboxMessage, ExternalMessageLog
from app.models.system import User
from app.services.hermes_20_question_runner import run_20_question_acceptance


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


def test_runner_builds_snapshots_from_existing_turn_outputs(monkeypatch) -> None:
    db = _db_session()
    db.add(_user())
    db.commit()

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

    monkeypatch.setattr("app.services.hermes_20_question_runner.run_root_owner_production_turn", lambda *args, **kwargs: fake_turn(**kwargs))

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
