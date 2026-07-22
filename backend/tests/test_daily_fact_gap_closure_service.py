from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.agent_communication import AgentEvent, AgentOutboxMessage
from app.services import agent_communication_service
from app.services.report.daily_fact_gap_closure_service import (
    list_open_daily_fact_gap_dates,
    sync_daily_fact_gap_events,
)


TARGET_DATE = date(2026, 7, 21)
NOW = datetime(2026, 7, 22, 0, 5, tzinfo=UTC)


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _bind_factory_channel(db: Session) -> None:
    agent_communication_service.register_agent(
        db,
        code="factory_dispatch",
        name="鑫泰铝业智能大脑",
    )
    agent_communication_service.register_channel(
        db,
        channel_type="dingtalk_group",
        channel_key="daily-fact-closure-test",
        name="日报事实闭环测试群",
        target_type="management",
        target_key="management",
        dry_run=False,
    )
    agent_communication_service.bind_agent_to_channel(
        db,
        agent_code="factory_dispatch",
        channel_key="daily-fact-closure-test",
    )


def _bundle(*missing_fields: str) -> dict:
    return {
        "missing_fields": list(missing_fields),
        "gap_plan": {
            "items": [
                {
                    "field": field,
                    "problem_type": "missing_field",
                    "source_lane": "dingtalk_or_scan_fill_workshop",
                    "entry_route": "/entry/fill",
                    "next_step": "优先查钉钉和只读生产事实，仍缺失时由负责人扫码补录。",
                    "actual": None,
                    "expected": 999999,
                }
                for field in missing_fields
            ]
        },
        "fact_closure": {
            "critical_fields": [
                {
                    "field": field,
                    "status": "missing",
                    "trace_id": None,
                }
                for field in missing_fields
                if field in {"total_output_daily", "total_electricity_kwh"}
            ]
        },
    }


def test_sync_creates_one_event_per_field_and_one_deduped_outbox() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        bundle = _bundle("total_output_daily", "hot_roll_daily")

        first = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=bundle,
            trace_id="daily-fact-closure:2026-07-21",
            now=NOW,
        )
        db.commit()
        second = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=bundle,
            trace_id="daily-fact-closure:2026-07-21",
            now=NOW + timedelta(minutes=5),
        )
        db.commit()

        events = db.query(AgentEvent).order_by(AgentEvent.id).all()
        outbox = db.query(AgentOutboxMessage).all()
        assert first["created"] == 2
        assert second["created"] == 0
        assert len(events) == 2
        assert {event.status for event in events} == {"open"}
        assert {event.payload["field"] for event in events} == {
            "total_output_daily",
            "hot_roll_daily",
        }
        by_field = {event.payload["field"]: event for event in events}
        assert by_field["total_output_daily"].payload["entry_route"] == "/manage/alerts"
        assert by_field["total_output_daily"].payload["fill_strategy"] == "dependency_fill"
        assert by_field["hot_roll_daily"].payload["entry_route"] == "/entry/fill"
        assert by_field["hot_roll_daily"].payload["owner_role"] == "machine_operator"
        assert by_field["hot_roll_daily"].payload["entry_fields"] == ["output_weight"]
        assert all("expected" not in event.payload for event in events)
        assert len(outbox) == 1
        assert outbox[0].event_id in {event.id for event in events}
        assert outbox[0].payload["event_ids"] == [event.id for event in events]
        assert "2 项" in outbox[0].content
        assert "999999" not in outbox[0].content
        assert "total_output_daily" not in outbox[0].content
        assert "hot_roll_daily" not in outbox[0].content
        assert second["outbox_message_id"] == first["outbox_message_id"]
    finally:
        db.close()


def test_sync_resolves_disappeared_gaps_and_reports_full_closure() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("total_output_daily", "hot_roll_daily"),
            trace_id="trace-open",
            now=NOW,
        )
        db.commit()

        partial = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily"),
            trace_id="trace-partial",
            now=NOW + timedelta(minutes=10),
        )
        db.commit()
        by_field = {event.payload["field"]: event for event in db.query(AgentEvent).all()}
        assert partial["resolved"] == 1
        assert by_field["total_output_daily"].status == "resolved"
        assert by_field["hot_roll_daily"].status == "open"

        closed = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle(),
            trace_id="trace-closed",
            now=NOW + timedelta(minutes=20),
        )
        db.commit()

        assert closed["open"] == 0
        assert closed["resolved"] == 1
        assert {event.status for event in db.query(AgentEvent).all()} == {"resolved"}
        completion = db.get(AgentOutboxMessage, closed["outbox_message_id"])
        assert completion is not None
        assert "已补齐" in completion.content
        assert completion.payload["open_event_ids"] == []
    finally:
        db.close()


def test_sync_keeps_events_when_no_outbound_channel_is_configured() -> None:
    db = _db_session()
    try:
        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("total_electricity_kwh"),
            trace_id="trace-no-channel",
            now=NOW,
        )
        db.commit()

        event = db.query(AgentEvent).one()
        assert event.status == "open"
        assert event.payload["delivery_status"] == "channel_unavailable"
        assert result["delivery_status"] == "channel_unavailable"
        assert result["outbox_message_id"] is None
        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        db.close()


def test_sync_assigns_existing_owner_forms_without_directly_filling_computed_facts() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("total_electricity_kwh", "finished_inbound_daily", "total_cost_10k"),
            trace_id="trace-owner-routing",
            now=NOW,
        )
        db.commit()

        events = {
            event.payload["field"]: event.payload
            for event in db.query(AgentEvent).all()
        }
        assert events["total_electricity_kwh"]["owner_role"] == "energy_chief"
        assert events["total_electricity_kwh"]["entry_fields"] == ["total_electricity_kwh"]
        assert events["finished_inbound_daily"]["owner_role"] == "storage_owner"
        assert events["finished_inbound_daily"]["entry_fields"] == [
            "park_inbound_daily",
            "new_plant_inbound_daily",
        ]
        assert events["total_cost_10k"]["fill_strategy"] == "dependency_fill"
        assert events["total_cost_10k"]["entry_route"] == "/manage/alerts"
        assert events["total_cost_10k"]["entry_fields"] == []
    finally:
        db.close()


def test_sync_prefers_real_channel_over_dry_run_channel() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="鑫泰铝业智能大脑",
        )
        dry_channel = agent_communication_service.register_channel(
            db,
            channel_type="dingtalk_group",
            channel_key="dry-management-group",
            name="管理群演练通道",
            target_type="management",
            dry_run=True,
        )
        real_channel = agent_communication_service.register_channel(
            db,
            channel_type="dingtalk_work_notice",
            channel_key="root-owner-work-notice",
            name="真实工作通知",
            target_type="user",
            target_key="root-owner",
            dry_run=False,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code="factory_dispatch",
            channel_key=dry_channel.channel_key,
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code="factory_dispatch",
            channel_key=real_channel.channel_key,
            channel_type=real_channel.channel_type,
        )

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("total_output_daily"),
            trace_id="trace-real-channel",
            now=NOW,
        )
        db.commit()

        message = db.get(AgentOutboxMessage, result["outbox_message_id"])
        assert message is not None
        assert message.channel_id == real_channel.id
    finally:
        db.close()


def test_sync_ignores_output_skill_alignment_differences() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        bundle = {
            "missing_fields": [],
            "gap_plan": {
                "items": [{
                    "field": "total_output_daily",
                    "problem_type": "alignment_difference",
                    "actual": 100,
                    "expected": 120,
                    "entry_route": "/entry/fill",
                }],
            },
            "fact_closure": {
                "critical_fields": [{
                    "field": "total_output_daily",
                    "status": "confirmed",
                }],
            },
        }

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=bundle,
            trace_id="trace-compare-only",
            now=NOW,
        )
        db.commit()

        assert result["open"] == 0
        assert db.query(AgentEvent).count() == 0
        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        db.close()


def test_sync_participates_in_callers_transaction() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("total_output_daily"),
            trace_id="trace-rollback",
            now=NOW,
        )
        db.rollback()

        assert db.query(AgentEvent).count() == 0
        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        db.close()


def test_open_gap_dates_include_only_unresolved_business_days() -> None:
    db = _db_session()
    try:
        for business_date, status in (
            (date(2026, 7, 19), "resolved"),
            (date(2026, 7, 20), "open"),
            (date(2026, 7, 21), "pending"),
        ):
            db.add(AgentEvent(
                event_type="daily_fact_gap",
                severity="warning",
                status=status,
                scope_type="factory",
                source_type="daily_fact_closure",
                source_ref=f"daily_fact_gap:{business_date.isoformat()}:total_output_daily",
                business_date=business_date,
                occurred_at=NOW,
                payload={"field": "total_output_daily"},
            ))
        db.commit()

        assert list_open_daily_fact_gap_dates(db) == [date(2026, 7, 21), date(2026, 7, 20)]
    finally:
        db.close()
