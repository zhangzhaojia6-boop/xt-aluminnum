from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import (
    AgentOutboxMessage,
    AgentRun,
    ChatInboxMessage,
    ExternalMessageLog,
)
from app.models.system import User
from app.services.hermes_root_owner_evidence_service import EvidenceCandidate, EvidenceDecision
from app.services.hermes_root_owner_production_orchestrator import run_root_owner_production_turn


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def _new_session_from(bind) -> Session:
    return Session(bind)


def _root_owner() -> User:
    return User(
        id=1,
        username="root-owner",
        password_hash="x",
        name="root_owner",
        role="admin",
        is_active=True,
        dingtalk_user_id="dt-root-001",
        dingtalk_union_id="union-root-001",
    )


def test_turn_answers_with_dingtalk_primary_and_records_trace(monkeypatch) -> None:
    db = _db_session()
    db.add(_root_owner())
    db.commit()

    primary = EvidenceCandidate(
        source_key="dingtalk_group_chat",
        source_type="dingtalk_group_content",
        domain="production",
        priority=10,
        status="ok",
        value={"total_output_daily": 118.0},
        summary="负责人群里确认 118 吨",
        trace_ref={"trace_id": "trace-ding-001"},
    )
    decision = EvidenceDecision(
        primary=primary,
        candidates=(primary,),
        conflicts=(),
        missing_sources=[],
        trace={"source_order": ["dingtalk_group_chat"]},
    )
    monkeypatch.setattr(
        "app.services.hermes_root_owner_production_orchestrator.collect_root_owner_evidence",
        lambda *_args, **_kwargs: decision,
    )
    sent = []

    def fake_dispatch(_db, outbox_message_id, *, sender=None):
        sent.append(outbox_message_id)
        message = _db.get(AgentOutboxMessage, outbox_message_id)
        message.status = "sent"
        _db.add(
            ExternalMessageLog(
                outbox_message_id=outbox_message_id,
                channel_type="dingtalk_work_notice",
                channel_key="dt-root-001",
                status="sent",
                detail="sent",
            )
        )
        _db.commit()
        return SimpleNamespace(status="sent", detail="sent", outbox_message_id=outbox_message_id)

    monkeypatch.setattr(
        "app.services.hermes_root_owner_production_orchestrator.agent_communication_service.dispatch_outbox_message",
        fake_dispatch,
    )

    try:
        result = run_root_owner_production_turn(
            db,
            text="今天产量咋样",
            current_user=db.get(User, 1),
            sender_external_id="dt-root-001",
            trace_id="trace-root-turn-001",
            source_payload={"source": "test"},
            default_business_date=date(2026, 6, 27),
        )

        assert result.status == "answered"
        assert "负责人群里确认 118 吨" in result.answer
        assert "钉钉" in result.answer
        assert result.dispatch_status == "sent"
        assert sent == [result.outbox_message_id]

        inbox = db.query(ChatInboxMessage).one()
        assert inbox.channel == "dingtalk_private"

        bind = db.get_bind()
        db.close()
        reread_db = _new_session_from(bind)
        try:
            run = reread_db.query(AgentRun).one()
            payload = run.result_payload
            assert run.trace_id == "trace-root-turn-001"
            assert payload["source"]["source"] == "dingtalk_inbound"
            assert payload["source"]["root_owner_private_loop"] is True
            assert payload["source"]["recognition_reason"]
            assert payload["source"]["source_payload"]["source"] == "test"
            assert payload["evidence"]["primary_source"] == "dingtalk_group_chat"
            assert payload["recognition"]["domain"] == "production"
            assert payload["dispatch"]["outbox_message_id"] == result.outbox_message_id
            assert payload["dispatch"]["status"] == "sent"
            assert payload["dispatch"]["detail"] == "sent"
        finally:
            reread_db.close()
    finally:
        db.close()


def test_turn_asks_short_clarification_for_unclear_message(monkeypatch) -> None:
    db = _db_session()
    db.add(_root_owner())
    db.commit()
    monkeypatch.setattr(
        "app.services.hermes_root_owner_production_orchestrator.agent_communication_service.dispatch_outbox_message",
        lambda _db, outbox_message_id, *, sender=None: SimpleNamespace(
            status="sent",
            detail="sent",
            outbox_message_id=outbox_message_id,
        ),
    )

    try:
        result = run_root_owner_production_turn(
            db,
            text="给我讲个轻松笑话",
            current_user=db.get(User, 1),
            sender_external_id="dt-root-001",
            trace_id="trace-root-turn-clarify",
            source_payload={},
            default_business_date=date(2026, 6, 27),
        )

        assert result.status == "clarifying"
        assert result.answer == "你想看生产、库存、能耗还是异常？"
        bind = db.get_bind()
        db.close()
        reread_db = _new_session_from(bind)
        try:
            run = reread_db.query(AgentRun).one()
            payload = run.result_payload
            assert payload["source"]["source"] == "dingtalk_inbound"
            assert payload["source"]["root_owner_private_loop"] is True
            assert payload["recognition"]["needs_clarification"] is True
            assert payload["evidence"]["primary_source"] is None
            assert payload["dispatch"]["outbox_message_id"] == result.outbox_message_id
            assert payload["dispatch"]["status"] == "sent"
            assert payload["dispatch"]["detail"] == "sent"
        finally:
            reread_db.close()
    finally:
        db.close()
