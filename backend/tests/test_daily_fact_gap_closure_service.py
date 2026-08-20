from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from app.models import Base
from app.models.agent_communication import AgentEvent, AgentOutboxMessage
from app.domain.daily_report_field_contract import DAILY_REPORT_FIELD_CONTRACT_VERSION
from app.services import agent_communication_service
from app.services.report import daily_fact_gap_closure_service
from app.services.report.daily_fact_gap_closure_service import (
    list_open_daily_fact_gap_dates,
    sync_daily_fact_gap_events,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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


def test_sync_creates_one_event_per_field_and_one_deduped_outbox(monkeypatch) -> None:
    db = _db_session()
    try:
        monkeypatch.setattr(
            daily_fact_gap_closure_service.settings,
            "PUBLIC_APP_BASE_URL",
            "https://hub.example.com",
        )
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
        assert by_field["total_output_daily"].payload["automation_status"] == "waiting_for_dependencies"
        assert by_field["total_output_daily"].payload["human_action_required"] is False
        assert by_field["total_output_daily"].payload["deadline"] == "10:00"
        assert by_field["total_output_daily"].payload["contract_version"] == DAILY_REPORT_FIELD_CONTRACT_VERSION
        assert by_field["hot_roll_daily"].payload["entry_route"] == "/entry/fill"
        assert by_field["hot_roll_daily"].payload["owner_role"] == "machine_operator"
        assert by_field["hot_roll_daily"].payload["entry_fields"] == ["output_weight"]
        assert by_field["hot_roll_daily"].payload["automation_status"] == "waiting_for_owner"
        assert by_field["hot_roll_daily"].payload["human_action_required"] is True
        assert by_field["hot_roll_daily"].payload["deadline"] == "10:00"
        assert by_field["hot_roll_daily"].payload["contract_version"] == DAILY_REPORT_FIELD_CONTRACT_VERSION
        hot_roll_route = urlparse(by_field["hot_roll_daily"].payload["action_route"])
        assert hot_roll_route.path == "/entry/fill"
        assert parse_qs(hot_roll_route.query) == {
            "business_date": ["2026-07-21"],
            "field": ["hot_roll_daily"],
            "entry_fields": ["output_weight"],
            "entry_field": ["output_weight"],
            "owner_role": ["machine_operator"],
            "trace_id": ["daily-fact-closure:2026-07-21"],
        }
        assert all("expected" not in event.payload for event in events)
        assert len(outbox) == 1
        assert outbox[0].event_id in {event.id for event in events}
        assert outbox[0].payload["event_ids"] == [event.id for event in events]
        assignments = {
            assignment["field"]: assignment
            for assignment in outbox[0].payload["assignments"]
        }
        assert set(assignments) == {"hot_roll_daily"}
        assert assignments["hot_roll_daily"]["business_date"] == "2026-07-21"
        assert assignments["hot_roll_daily"]["trace_id"] == "daily-fact-closure:2026-07-21"
        assert assignments["hot_roll_daily"]["action_route"] == by_field["hot_roll_daily"].payload["action_route"]
        assert assignments["hot_roll_daily"]["deadline"] == "10:00"
        assert assignments["hot_roll_daily"]["contract_version"] == DAILY_REPORT_FIELD_CONTRACT_VERSION
        assert "需要人工补录：1 项" in outbox[0].content
        assert "依赖补齐 1 项" in outbox[0].content
        assert "状态不变不会重复提醒" in outbox[0].content
        assert "999999" not in outbox[0].content
        assert "total_output_daily" not in outbox[0].content
        assert "hot_roll_daily" not in outbox[0].content
        assert (
            "[立即补录](https://hub.example.com/entry/fill?"
            "business_date=2026-07-21&entry_fields=output_weight"
        ) in outbox[0].content
        assert second["outbox_message_id"] == first["outbox_message_id"]
        assert second["delivery_status"] == "unchanged"
        assert by_field["total_output_daily"].payload["automation_check_count"] == 2
        assert by_field["hot_roll_daily"].payload["automation_check_count"] == 0
    finally:
        db.close()


def test_sync_keeps_source_rechecks_and_dependencies_in_trace_without_notifying_people() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)

        first = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("wip_1850_cold", "total_cost_10k"),
            trace_id="trace-auto-recheck",
            now=NOW,
        )
        second = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("wip_1850_cold", "total_cost_10k"),
            trace_id="trace-auto-recheck",
            now=NOW + timedelta(minutes=15),
        )
        db.commit()

        events = {
            event.payload["field"]: event.payload
            for event in db.query(AgentEvent).all()
        }
        assert first["delivery_status"] == "auto_rechecking"
        assert second["delivery_status"] == "auto_rechecking"
        assert first["outbox_message_id"] is None
        assert second["outbox_message_id"] is None
        assert db.query(AgentOutboxMessage).count() == 0
        assert events["wip_1850_cold"]["automation_status"] == "rechecking_sources"
        assert events["wip_1850_cold"]["automation_check_count"] == 2
        assert events["total_cost_10k"]["automation_status"] == "waiting_for_dependencies"
        assert events["total_cost_10k"]["automation_check_count"] == 2
        assert all(payload["human_action_required"] is False for payload in events.values())
    finally:
        db.close()


def test_sync_preserves_existing_contract_provenance_on_refresh() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        db.add(AgentEvent(
            event_type="daily_fact_gap",
            severity="warning",
            status="open",
            scope_type="factory",
            source_type="daily_fact_closure",
            source_ref=f"daily_fact_gap:{TARGET_DATE.isoformat()}:hot_roll_daily",
            business_date=TARGET_DATE,
            occurred_at=NOW,
            payload={
                "field": "hot_roll_daily",
                "deadline": "09:00",
                "contract_version": "legacy-version",
                "action_route": "/entry/fill?trace_id=old-trace",
            },
        ))
        db.commit()

        sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily"),
            trace_id="trace-preserve-provenance",
            now=NOW + timedelta(minutes=5),
        )
        db.commit()

        event = db.query(AgentEvent).one()
        assert event.payload["deadline"] == "09:00"
        assert event.payload["contract_version"] == "legacy-version"
        assert "trace-preserve-provenance" in event.payload["action_route"]
    finally:
        db.close()


def test_sync_backfills_missing_contract_provenance_on_refresh() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        db.add(AgentEvent(
            event_type="daily_fact_gap",
            severity="warning",
            status="open",
            scope_type="factory",
            source_type="daily_fact_closure",
            source_ref=f"daily_fact_gap:{TARGET_DATE.isoformat()}:hot_roll_daily",
            business_date=TARGET_DATE,
            occurred_at=NOW,
            payload={
                "field": "hot_roll_daily",
                "action_route": "/entry/fill?trace_id=old-trace",
            },
        ))
        db.commit()

        sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily"),
            trace_id="trace-backfill-provenance",
            now=NOW + timedelta(minutes=5),
        )
        db.commit()

        event = db.query(AgentEvent).one()
        assert event.payload["deadline"] == "10:00"
        assert event.payload["contract_version"] == DAILY_REPORT_FIELD_CONTRACT_VERSION
        assert "trace-backfill-provenance" in event.payload["action_route"]
    finally:
        db.close()


def test_sync_assigns_missing_wip_total_to_existing_planning_owner_entry() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("wip_total"),
            trace_id="trace-wip-owner",
            now=NOW,
        )
        db.commit()

        event = db.query(AgentEvent).one()
        assert result["outbox_message_id"] is not None
        assert event.payload["human_action_required"] is True
        assert event.payload["automation_status"] == "waiting_for_owner"
        assert event.payload["owner_role"] == "planning_owner"
        assert event.payload["entry_fields"] == ["wip_total"]
        route = urlparse(event.payload["action_route"])
        assert route.path == "/entry/fill"
        assert parse_qs(route.query) == {
            "business_date": ["2026-07-21"],
            "field": ["wip_total"],
            "entry_fields": ["wip_total"],
            "entry_field": ["wip_total"],
            "owner_role": ["planning_owner"],
            "trace_id": ["trace-wip-owner"],
        }
    finally:
        db.close()


def test_sync_notifies_only_when_a_new_human_action_appears() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)

        first = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily"),
            trace_id="trace-owner-change",
            now=NOW,
        )
        automatic_change = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily", "total_cost_10k"),
            trace_id="trace-owner-change",
            now=NOW + timedelta(minutes=15),
        )
        owner_change = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily", "total_cost_10k", "total_electricity_kwh"),
            trace_id="trace-owner-change",
            now=NOW + timedelta(minutes=30),
        )
        db.commit()

        assert first["outbox_message_id"] is not None
        assert automatic_change["delivery_status"] == "unchanged"
        assert automatic_change["outbox_message_id"] == first["outbox_message_id"]
        assert owner_change["outbox_message_id"] != first["outbox_message_id"]
        assert db.query(AgentOutboxMessage).count() == 2
        latest = db.get(AgentOutboxMessage, owner_change["outbox_message_id"])
        assert latest is not None
        assert {
            item["field"]
            for item in latest.payload["assignments"]
        } == {"hot_roll_daily", "total_electricity_kwh"}
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
        assert by_field["total_output_daily"].payload["fact_status"] == "confirmed"
        assert by_field["total_output_daily"].payload["human_action_required"] is False
        assert by_field["total_output_daily"].payload["automation_status"] == "resolved"
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
        inbound_route = parse_qs(urlparse(events["finished_inbound_daily"]["action_route"]).query)
        assert inbound_route["entry_fields"] == ["park_inbound_daily,new_plant_inbound_daily"]
        assert events["total_cost_10k"]["fill_strategy"] == "dependency_fill"
        assert events["total_cost_10k"]["entry_route"] == "/manage/alerts"
        assert events["total_cost_10k"]["entry_fields"] == []
        assert events["total_cost_10k"]["action_route"] == "/manage/alerts?trace_id=trace-owner-routing"
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
            bundle=_bundle("hot_roll_daily"),
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
