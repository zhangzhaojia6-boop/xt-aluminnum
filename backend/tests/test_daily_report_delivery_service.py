from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import (
    AgentEvent,
    AgentOutboxMessage,
    ExternalMessageLog,
)
from app.models.reports import DailyReport
from app.models.system import User
from app.services import daily_report_delivery_service as service
from app.services.report.template_daily_report import REQUIRED_FIELDS

REPORT_DATE = date(2026, 7, 23)
REPORT_TEXT = "7月23日，车间总产量日合计328吨。\n\n第二段\n\n第三段\n\n第四段\n\n第五段"


def _db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _ready_report(*, sources: dict | None = None, conflicts: list | None = None) -> DailyReport:
    source_map = sources or {
        field: {"source_type": "runtime_target_date" if field == "report_date" else "mes_verified"}
        for field in REQUIRED_FIELDS
    }
    return DailyReport(
        report_date=REPORT_DATE,
        report_type="production",
        generated_scope="auto_confirmed",
        output_mode="both",
        status="published",
        delivery_ready=True,
        quality_gate_status="passed",
        final_text_summary=REPORT_TEXT,
        report_data={
            "template_daily_report": {
                "status": "ready",
                "text": REPORT_TEXT,
                "missing_fields": [],
                "conflicts": conflicts or [],
                "sources": source_map,
            }
        },
    )


def _configure_recipient(monkeypatch) -> None:
    monkeypatch.setattr(service.settings, "AUTO_PUSH_ENABLED", True)
    monkeypatch.setattr(service.settings, "DINGTALK_ENABLED", True)
    monkeypatch.setattr(service.settings, "DINGTALK_NOTIFY_DRY_RUN", False)
    monkeypatch.setattr(service.settings, "DAILY_REPORT_DINGTALK_RECIPIENT_NAME", "孟玉杰")
    monkeypatch.setattr(
        service.settings,
        "DAILY_REPORT_DINGTALK_RECIPIENT_USER_ID",
        "dt-user-meng",
        raising=False,
    )
    monkeypatch.setattr(service.settings, "HERMES_OWNER_DINGTALK_USER_IDS", "", raising=False)


def test_complete_report_is_sent_once_through_outbox(monkeypatch) -> None:
    db = _db_session()
    calls = []
    try:
        _configure_recipient(monkeypatch)
        monkeypatch.setattr(
            service.agent_communication_service.dingtalk_service,
            "send_user_message",
            lambda user_id, payload: calls.append((user_id, payload)) or (True, "dingtalk_sent"),
        )
        report = _ready_report()
        db.add(report)
        db.commit()

        first = service.deliver_completed_daily_report(db, target_date=REPORT_DATE)
        second = service.deliver_completed_daily_report(db, target_date=REPORT_DATE)

        assert first["status"] == "sent"
        assert second["status"] == "sent"
        assert second["duplicate"] is True
        assert calls == [
            (
                "dt-user-meng",
                {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": "2026-07-23 鑫泰铝业生产日报",
                        "text": REPORT_TEXT,
                    },
                },
            )
        ]
        assert db.query(AgentEvent).count() == 1
        assert db.query(AgentOutboxMessage).count() == 1
        assert db.query(ExternalMessageLog).filter(ExternalMessageLog.status == "sent").count() == 1
    finally:
        db.close()


def test_complete_report_is_sent_to_configured_recipient_and_root_owner(monkeypatch) -> None:
    db = _db_session()
    calls = []
    try:
        _configure_recipient(monkeypatch)
        monkeypatch.setattr(
            service.settings,
            "HERMES_OWNER_DINGTALK_USER_IDS",
            "dt-user-owner",
            raising=False,
        )
        monkeypatch.setattr(
            service.agent_communication_service.dingtalk_service,
            "send_user_message",
            lambda user_id, payload: calls.append((user_id, payload)) or (True, "dingtalk_sent"),
        )
        db.add(
            User(
                username="owner",
                password_hash="unused",
                name="张兆嘉",
                role="admin",
                dingtalk_user_id="dt-user-owner",
                is_active=True,
            )
        )
        db.add(_ready_report())
        db.commit()

        result = service.deliver_completed_daily_report(db, target_date=REPORT_DATE)

        assert result["status"] == "sent"
        assert len(result["deliveries"]) == 2
        assert [item[0] for item in calls] == ["dt-user-meng", "dt-user-owner"]
        assert db.query(AgentEvent).count() == 2
        assert db.query(AgentOutboxMessage).count() == 2
    finally:
        db.close()


def test_incomplete_or_conflicting_report_is_not_queued(monkeypatch) -> None:
    db = _db_session()
    try:
        _configure_recipient(monkeypatch)
        report = _ready_report(conflicts=[{"field": "total_output_daily", "reason": "source_mismatch"}])
        db.add(report)
        db.commit()

        result = service.deliver_completed_daily_report(db, target_date=REPORT_DATE)

        assert result["status"] == "blocked_incomplete"
        assert db.query(AgentEvent).count() == 0
        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        db.close()


def test_non_mother_template_body_is_not_queued(monkeypatch) -> None:
    db = _db_session()
    try:
        _configure_recipient(monkeypatch)
        report = _ready_report()
        report.report_data["template_daily_report"]["text"] = "只有一段的摘要"
        db.add(report)
        db.commit()

        result = service.deliver_completed_daily_report(db, target_date=REPORT_DATE)

        assert result["status"] == "blocked_incomplete"
        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        db.close()


def test_reference_adopted_report_is_not_queued(monkeypatch) -> None:
    db = _db_session()
    try:
        _configure_recipient(monkeypatch)
        sources = {
            field: {"source_type": "runtime_target_date" if field == "report_date" else "mes_verified"}
            for field in REQUIRED_FIELDS
        }
        sources["total_output_daily"] = {"source_type": "datahub_final_daily_report"}
        report = _ready_report(sources=sources)
        db.add(report)
        db.commit()

        result = service.deliver_completed_daily_report(db, target_date=REPORT_DATE)

        assert result["status"] == "blocked_reference_source"
        assert result["reference_fields"] == ["total_output_daily"]
        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        db.close()


def test_recipient_requires_exact_dingtalk_user_id(monkeypatch) -> None:
    db = _db_session()
    try:
        _configure_recipient(monkeypatch)
        monkeypatch.setattr(service.settings, "DAILY_REPORT_DINGTALK_RECIPIENT_USER_ID", "", raising=False)
        db.add(_ready_report())
        db.commit()

        result = service.deliver_completed_daily_report(db, target_date=REPORT_DATE)

        assert result == {"status": "blocked_recipient", "reason": "recipient_user_id_missing"}
        report = db.query(DailyReport).one()
        db.refresh(report)
        assert report.report_data["scheduled_daily_report_delivery"] == {
            "status": "blocked_recipient",
            "reason": "recipient_user_id_missing",
            "scheduled_at": "10:00",
        }
        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        db.close()
