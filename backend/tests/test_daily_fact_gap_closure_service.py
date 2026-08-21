from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from app.models import Base
from app.models.agent_communication import AgentEvent, AgentOutboxMessage, CommunicationChannel
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
        channel_type="dingtalk_work_notice",
        channel_key="daily-fact-closure-test",
        name="日报事实闭环管理员兜底",
        target_type="user",
        target_key="management",
        dry_run=False,
        metadata_payload={
            "daily_fact_admin_fallback": True,
            "recipient_name": "日报管理员",
            "organization_path": "生产运行部/管理调度",
        },
    )
    agent_communication_service.bind_agent_to_channel(
        db,
        agent_code="factory_dispatch",
        channel_key="daily-fact-closure-test",
        channel_type="dingtalk_work_notice",
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


def _bind_owner_channel(
    db: Session,
    *,
    channel_key: str,
    recipient_name: str,
    owner_roles: list[str],
) -> None:
    channel = agent_communication_service.register_channel(
        db,
        channel_type="dingtalk_work_notice",
        channel_key=channel_key,
        name=f"{recipient_name}日报缺项通知",
        target_type="user",
        target_key=channel_key,
        dry_run=False,
        metadata_payload={
            "daily_fact_notification": True,
            "recipient_name": recipient_name,
            "organization_path": "生产运行部/专项岗位",
            "daily_fact_owner_roles": owner_roles,
        },
    )
    agent_communication_service.bind_agent_to_channel(
        db,
        agent_code="factory_dispatch",
        channel_key=channel.channel_key,
        channel_type=channel.channel_type,
    )


def _bind_field_channel(
    db: Session,
    *,
    channel_key: str,
    target_key: str,
    recipient_name: str,
    organization_path: str,
    fields: list[str],
    recipient_mode: str | None = None,
) -> CommunicationChannel:
    metadata_payload = {
        "daily_fact_notification": True,
        "recipient_name": recipient_name,
        "organization_path": organization_path,
        "daily_fact_fields": fields,
    }
    if recipient_mode:
        metadata_payload["daily_fact_recipient_mode"] = recipient_mode
    channel = agent_communication_service.register_channel(
        db,
        channel_type="dingtalk_work_notice",
        channel_key=channel_key,
        name=f"{recipient_name}日报缺项通知",
        target_type="user",
        target_key=target_key,
        dry_run=False,
        metadata_payload=metadata_payload,
    )
    agent_communication_service.bind_agent_to_channel(
        db,
        agent_code="factory_dispatch",
        channel_key=channel.channel_key,
        channel_type=channel.channel_type,
    )
    return channel


def test_sync_routes_two_owner_roles_to_separate_work_notice_channels() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="鑫泰铝业智能大脑",
        )
        _bind_owner_channel(
            db,
            channel_key="quality-owner-work-notice",
            recipient_name="质检内勤",
            owner_roles=["quality_owner"],
        )
        _bind_owner_channel(
            db,
            channel_key="energy-chief-work-notice",
            recipient_name="总电工",
            owner_roles=["energy_chief"],
        )

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("daily_yield_rate", "total_electricity_kwh"),
            trace_id="trace-owner-role-routing",
            now=NOW,
        )
        db.commit()

        messages = db.query(AgentOutboxMessage).order_by(AgentOutboxMessage.id).all()
        assert len(messages) == 2
        assignments_by_channel = {
            message.channel_id: [item["field"] for item in message.payload["assignments"]]
            for message in messages
        }
        assert assignments_by_channel == {
            message.channel_id: expected
            for message, expected in zip(
                messages,
                (["daily_yield_rate"], ["total_electricity_kwh"]),
                strict=True,
            )
        }
        assert result["outbox_message_ids"] == [message.id for message in messages]
        assert result["outbox_message_id"] == messages[0].id
        events = {event.payload["field"]: event for event in db.query(AgentEvent).all()}
        assert events["daily_yield_rate"].payload["notification_target_keys"] == [
            "quality-owner-work-notice"
        ]
        assert events["total_electricity_kwh"].payload["notification_target_keys"] == [
            "energy-chief-work-notice"
        ]
        assert events["daily_yield_rate"].payload["action_notification_outbox_ids"] == [messages[0].id]
        assert events["total_electricity_kwh"].payload["action_notification_outbox_ids"] == [messages[1].id]
        assert events["daily_yield_rate"].payload["notification_targets"] == [{
            "target_key": "quality-owner-work-notice",
            "channel_id": messages[0].channel_id,
            "recipient_name": "质检内勤",
            "organization_path": "生产运行部/专项岗位",
            "recipient_mode": "specialist",
            "routing_status": "owner_role_match",
        }]
        assert events["total_electricity_kwh"].payload["notification_targets"] == [{
            "target_key": "energy-chief-work-notice",
            "channel_id": messages[1].channel_id,
            "recipient_name": "总电工",
            "organization_path": "生产运行部/专项岗位",
            "recipient_mode": "specialist",
            "routing_status": "owner_role_match",
        }]
    finally:
        db.close()


def test_sync_allows_one_field_to_route_to_multiple_explicit_workshop_channels() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="鑫泰铝业智能大脑",
        )
        first_channel = _bind_field_channel(
            db,
            channel_key="annealing-one-director-work-notice",
            target_key="annealing-one-director",
            recipient_name="在线退火一车间主任",
            organization_path="生产运行部/在线退火一车间",
            fields=["hot_roll_daily"],
        )
        second_channel = _bind_field_channel(
            db,
            channel_key="annealing-two-director-work-notice",
            target_key="annealing-two-director",
            recipient_name="在线退火二车间主任",
            organization_path="生产运行部/在线退火二车间",
            fields=["hot_roll_daily"],
        )

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily"),
            trace_id="trace-explicit-multi-workshop",
            now=NOW,
        )
        db.commit()

        messages = db.query(AgentOutboxMessage).order_by(AgentOutboxMessage.id).all()
        assert len(messages) == 2
        assert {message.channel_id for message in messages} == {first_channel.id, second_channel.id}
        assert all(message.payload["routing_status"] == "field_match" for message in messages)
        assert all(
            [assignment["field"] for assignment in message.payload["assignments"]] == ["hot_roll_daily"]
            for message in messages
        )
        event = db.query(AgentEvent).one()
        assert set(event.payload["action_notification_outbox_ids"]) == set(result["outbox_message_ids"])
        assert {target["target_key"] for target in event.payload["notification_targets"]} == {
            "annealing-one-director",
            "annealing-two-director",
        }
    finally:
        db.close()


def test_sync_routes_supervisor_notifications_to_manage_dashboard_without_changing_fact_assignment(
    monkeypatch,
) -> None:
    db = _db_session()
    try:
        monkeypatch.setattr(
            daily_fact_gap_closure_service.settings,
            "PUBLIC_APP_BASE_URL",
            "https://hub.example.com",
        )
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="鑫泰铝业智能大脑",
        )
        supervisor_channel = _bind_field_channel(
            db,
            channel_key="hot-roll-director-supervisor-work-notice",
            target_key="hot-roll-director",
            recipient_name="热轧车间主任",
            organization_path="生产运行部/热轧车间",
            fields=["hot_roll_daily"],
            recipient_mode="supervisor",
        )
        specialist_channel = _bind_field_channel(
            db,
            channel_key="energy-chief-specialist-work-notice",
            target_key="energy-chief",
            recipient_name="总电工",
            organization_path="生产运行部/能源组",
            fields=["total_electricity_kwh"],
        )

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily", "total_electricity_kwh"),
            trace_id="trace-supervisor-route",
            now=NOW,
        )
        db.commit()

        messages = {
            message.channel_id: message
            for message in db.query(AgentOutboxMessage).order_by(AgentOutboxMessage.id).all()
        }
        assert set(messages) == {supervisor_channel.id, specialist_channel.id}

        supervisor_message = messages[supervisor_channel.id]
        assert supervisor_message.payload["recipient_mode"] == "supervisor"
        assert supervisor_message.payload["entry_route"] == "/manage/workshop-dashboard"
        assert supervisor_message.payload["action_route"] == (
            "/manage/workshop-dashboard?"
            "business_date=2026-07-21&trace_id=trace-supervisor-route"
        )
        assert "查看并跟进" in supervisor_message.content
        assert "立即补录" not in supervisor_message.content
        assert (
            "[查看并跟进](https://hub.example.com/manage/workshop-dashboard?"
            "business_date=2026-07-21&trace_id=trace-supervisor-route)"
        ) in supervisor_message.content
        assert "/entry/fill?" not in supervisor_message.content

        specialist_message = messages[specialist_channel.id]
        assert specialist_message.payload["recipient_mode"] == "specialist"
        assert specialist_message.payload["entry_route"] == "/entry/fill"
        assert specialist_message.payload["action_route"] == (
            "/entry/fill?"
            "business_date=2026-07-21&entry_fields=total_electricity_kwh"
            "&entry_field=total_electricity_kwh&owner_role=energy_chief"
            "&trace_id=trace-supervisor-route"
        )
        assert "立即补录" in specialist_message.content
        assert (
            "[立即补录](https://hub.example.com/entry/fill?"
            "business_date=2026-07-21&entry_fields=total_electricity_kwh"
            "&entry_field=total_electricity_kwh&owner_role=energy_chief"
            "&trace_id=trace-supervisor-route)"
        ) in specialist_message.content

        events = {
            event.payload["field"]: event
            for event in db.query(AgentEvent).order_by(AgentEvent.id).all()
        }
        hot_roll_route = urlparse(events["hot_roll_daily"].payload["action_route"])
        assert hot_roll_route.path == "/entry/fill"
        assert parse_qs(hot_roll_route.query) == {
            "business_date": ["2026-07-21"],
            "field": ["hot_roll_daily"],
            "entry_fields": ["output_weight"],
            "entry_field": ["output_weight"],
            "owner_role": ["machine_operator"],
            "trace_id": ["trace-supervisor-route"],
        }
        assert events["hot_roll_daily"].payload["notification_targets"] == [{
            "target_key": "hot-roll-director",
            "channel_id": supervisor_channel.id,
            "recipient_name": "热轧车间主任",
            "organization_path": "生产运行部/热轧车间",
            "routing_status": "field_match",
            "recipient_mode": "supervisor",
        }]
        assert events["total_electricity_kwh"].payload["notification_targets"] == [{
            "target_key": "energy-chief",
            "channel_id": specialist_channel.id,
            "recipient_name": "总电工",
            "organization_path": "生产运行部/能源组",
            "routing_status": "field_match",
            "recipient_mode": "specialist",
        }]
        assert result["outbox_message_ids"] == [supervisor_message.id, specialist_message.id]
    finally:
        db.close()


def test_sync_routes_overlapping_owner_role_to_explicit_admin_fallback_as_conflict() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="鑫泰铝业智能大脑",
        )
        _bind_owner_channel(
            db,
            channel_key="quality-owner-primary-work-notice",
            recipient_name="质检内勤甲",
            owner_roles=["quality_owner"],
        )
        _bind_owner_channel(
            db,
            channel_key="quality-owner-secondary-work-notice",
            recipient_name="质检内勤乙",
            owner_roles=["quality_owner"],
        )
        _bind_factory_channel(db)

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("daily_yield_rate"),
            trace_id="trace-owner-role-conflict",
            now=NOW,
        )
        db.commit()

        messages = db.query(AgentOutboxMessage).all()
        assert len(messages) == 1
        assert messages[0].payload["routing_status"] == "conflict"
        assert messages[0].payload["recipient_name"] == "日报管理员"
        assert [item["field"] for item in messages[0].payload["assignments"]] == ["daily_yield_rate"]
        event = db.query(AgentEvent).one()
        assert event.payload["routing_status"] == "conflict"
        assert event.payload["outbox_message_id"] == result["outbox_message_id"]
        assert event.payload["notification_targets"][0]["target_key"] == "management"
    finally:
        db.close()


def test_sync_keeps_overlapping_owner_role_unresolved_without_admin_fallback() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="鑫泰铝业智能大脑",
        )
        _bind_owner_channel(
            db,
            channel_key="quality-owner-a-work-notice",
            recipient_name="质检内勤甲",
            owner_roles=["quality_owner"],
        )
        _bind_owner_channel(
            db,
            channel_key="quality-owner-b-work-notice",
            recipient_name="质检内勤乙",
            owner_roles=["quality_owner"],
        )

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("daily_yield_rate"),
            trace_id="trace-owner-role-conflict-no-fallback",
            now=NOW,
        )
        db.commit()

        assert db.query(AgentOutboxMessage).count() == 0
        assert result["outbox_message_id"] is None
        event = db.query(AgentEvent).one()
        assert event.payload["routing_status"] == "unresolved"
        assert event.payload["notification_targets"] == []
    finally:
        db.close()


def test_sync_clears_stale_single_outbox_reference_when_route_disappears() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        first = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("foundry_daily"),
            trace_id="trace-route-disappeared",
            now=NOW,
        )
        db.commit()

        event = db.query(AgentEvent).one()
        old_message = db.get(AgentOutboxMessage, first["outbox_message_id"])
        assert old_message is not None
        assert old_message.event_id == event.id
        assert event.payload["action_notification_outbox_id"] == old_message.id
        channel = db.get(CommunicationChannel, old_message.channel_id)
        assert channel is not None
        channel.is_active = False
        db.commit()

        second = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("foundry_daily"),
            trace_id="trace-route-disappeared",
            now=NOW + timedelta(minutes=5),
        )
        db.commit()

        db.refresh(event)
        assert second["outbox_message_id"] is None
        assert event.payload["action_notification_outbox_ids"] == []
        assert "action_notification_outbox_id" not in event.payload
        assert db.get(AgentOutboxMessage, old_message.id).event_id == event.id
    finally:
        db.close()


def test_sync_prefers_new_pending_message_without_copying_its_status_to_other_event() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="鑫泰铝业智能大脑",
        )
        first_channel = _bind_field_channel(
            db,
            channel_key="hot-roll-existing-work-notice",
            target_key="hot-roll-existing",
            recipient_name="热轧车间主任甲",
            organization_path="生产运行部/热轧车间甲",
            fields=["hot_roll_daily"],
        )
        first = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily"),
            trace_id="trace-mixed-route-status",
            now=NOW,
        )
        db.commit()
        reused_message = db.get(AgentOutboxMessage, first["outbox_message_id"])
        assert reused_message is not None
        assert reused_message.channel_id == first_channel.id
        reused_message.status = "sent"
        db.commit()

        new_channel = _bind_field_channel(
            db,
            channel_key="foundry-new-work-notice",
            target_key="foundry-new",
            recipient_name="铸造车间主任",
            organization_path="生产运行部/铸造车间",
            fields=["foundry_daily"],
        )
        second = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily", "foundry_daily"),
            trace_id="trace-mixed-route-status",
            now=NOW + timedelta(minutes=5),
        )
        db.commit()

        messages = db.query(AgentOutboxMessage).order_by(AgentOutboxMessage.id).all()
        assert len(messages) == 2
        pending_message = next(message for message in messages if message.channel_id == new_channel.id)
        assert pending_message.status == "pending"
        assert second["outbox_message_ids"] == [reused_message.id, pending_message.id]
        assert second["outbox_message_id"] == pending_message.id
        assert second["delivery_status"] == "pending"
        events = {event.payload["field"]: event for event in db.query(AgentEvent).all()}
        assert events["hot_roll_daily"].payload["outbox_message_id"] == reused_message.id
        assert events["hot_roll_daily"].payload["delivery_status"] == "unchanged"
        assert events["hot_roll_daily"].payload["action_notification_outbox_ids"] == [reused_message.id]
        assert events["foundry_daily"].payload["outbox_message_id"] == pending_message.id
        assert events["foundry_daily"].payload["delivery_status"] == "pending"
        assert events["foundry_daily"].payload["action_notification_outbox_ids"] == [pending_message.id]
    finally:
        db.close()


def test_sync_prefers_exact_field_route_and_sends_only_unresolved_to_explicit_fallback() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="鑫泰铝业智能大脑",
        )
        workshop_channel = agent_communication_service.register_channel(
            db,
            channel_type="dingtalk_work_notice",
            channel_key="hot-roll-director-work-notice",
            name="热轧车间主任日报缺项通知",
            target_type="user",
            target_key="hot-roll-director",
            dry_run=False,
            metadata_payload={
                "daily_fact_notification": True,
                "recipient_name": "热轧车间主任",
                "organization_path": "生产运行部/热轧车间",
                "daily_fact_fields": ["hot_roll_daily"],
            },
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code="factory_dispatch",
            channel_key=workshop_channel.channel_key,
            channel_type=workshop_channel.channel_type,
        )
        _bind_factory_channel(db)

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily", "foundry_daily"),
            trace_id="trace-field-fallback-routing",
            now=NOW,
        )
        db.commit()

        messages = db.query(AgentOutboxMessage).order_by(AgentOutboxMessage.id).all()
        assert len(messages) == 2
        by_status = {message.payload["routing_status"]: message for message in messages}
        assert [item["field"] for item in by_status["field_match"].payload["assignments"]] == [
            "hot_roll_daily"
        ]
        assert by_status["field_match"].payload["recipient_name"] == "热轧车间主任"
        assert by_status["field_match"].payload["organization_path"] == "生产运行部/热轧车间"
        assert [item["field"] for item in by_status["unresolved"].payload["assignments"]] == [
            "foundry_daily"
        ]
        assert result["outbox_message_ids"] == [message.id for message in messages]
        events = {event.payload["field"]: event for event in db.query(AgentEvent).all()}
        assert events["hot_roll_daily"].payload["notification_targets"] == [{
            "target_key": "hot-roll-director",
            "channel_id": by_status["field_match"].channel_id,
            "recipient_name": "热轧车间主任",
            "organization_path": "生产运行部/热轧车间",
            "recipient_mode": "specialist",
            "routing_status": "field_match",
        }]
        assert events["foundry_daily"].payload["notification_targets"] == [{
            "target_key": "management",
            "channel_id": by_status["unresolved"].channel_id,
            "recipient_name": "日报管理员",
            "organization_path": "生产运行部/管理调度",
            "recipient_mode": "specialist",
            "routing_status": "unresolved",
        }]
    finally:
        db.close()


def test_sync_never_sends_unresolved_fields_to_specialist_without_explicit_fallback() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="鑫泰铝业智能大脑",
        )
        channel = agent_communication_service.register_channel(
            db,
            channel_type="dingtalk_work_notice",
            channel_key="hot-roll-only-work-notice",
            name="热轧车间主任日报缺项通知",
            target_type="user",
            target_key="hot-roll-director",
            dry_run=False,
            metadata_payload={
                "daily_fact_notification": True,
                "recipient_name": "热轧车间主任",
                "organization_path": "生产运行部/热轧车间",
                "daily_fact_fields": ["hot_roll_daily"],
            },
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code="factory_dispatch",
            channel_key=channel.channel_key,
            channel_type=channel.channel_type,
        )

        sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily", "foundry_daily"),
            trace_id="trace-no-implicit-fallback",
            now=NOW,
        )
        db.commit()

        messages = db.query(AgentOutboxMessage).all()
        assert len(messages) == 1
        assert [item["field"] for item in messages[0].payload["assignments"]] == ["hot_roll_daily"]
        events = {event.payload["field"]: event for event in db.query(AgentEvent).all()}
        assert events["hot_roll_daily"].payload["routing_status"] == "field_match"
        assert events["foundry_daily"].payload["routing_status"] == "unresolved"
        assert events["foundry_daily"].payload["notification_target_keys"] == []
        assert events["foundry_daily"].payload["action_notification_outbox_ids"] == []
        assert events["foundry_daily"].payload["notification_targets"] == []
        assert "action_notification_outbox_id" not in events["foundry_daily"].payload
    finally:
        db.close()


def test_sync_dedupes_each_channel_by_its_assignment_signature_when_routes_change() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        first = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("foundry_daily"),
            trace_id="trace-route-change",
            now=NOW,
        )
        db.commit()
        fallback_message = db.get(AgentOutboxMessage, first["outbox_message_id"])
        assert fallback_message is not None

        workshop_channel = agent_communication_service.register_channel(
            db,
            channel_type="dingtalk_work_notice",
            channel_key="hot-roll-route-change-work-notice",
            name="热轧车间主任日报缺项通知",
            target_type="user",
            target_key="hot-roll-director",
            dry_run=False,
            metadata_payload={
                "daily_fact_notification": True,
                "recipient_name": "热轧车间主任",
                "organization_path": "生产运行部/热轧车间",
                "daily_fact_fields": ["hot_roll_daily"],
            },
        )
        agent_communication_service.bind_agent_to_channel(
            db,
            agent_code="factory_dispatch",
            channel_key=workshop_channel.channel_key,
            channel_type=workshop_channel.channel_type,
        )

        second = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("foundry_daily", "hot_roll_daily"),
            trace_id="trace-route-change",
            now=NOW + timedelta(minutes=5),
        )
        db.commit()
        third = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("foundry_daily", "hot_roll_daily"),
            trace_id="trace-route-change",
            now=NOW + timedelta(minutes=10),
        )
        db.commit()

        messages = db.query(AgentOutboxMessage).order_by(AgentOutboxMessage.id).all()
        assert len(messages) == 2
        assert fallback_message.id in second["outbox_message_ids"]
        assert fallback_message.dedupe_key == messages[0].dedupe_key
        assert set(second["outbox_message_ids"]) == {message.id for message in messages}
        assert set(third["outbox_message_ids"]) == {message.id for message in messages}
    finally:
        db.close()


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


def test_sync_keeps_outbox_assignments_aligned_with_preserved_event_provenance() -> None:
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

        result = sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle=_bundle("hot_roll_daily"),
            trace_id="trace-preserve-provenance",
            now=NOW + timedelta(minutes=5),
        )
        db.commit()

        event = db.query(AgentEvent).one()
        outbox = db.get(AgentOutboxMessage, result["outbox_message_id"])
        assert outbox is not None
        assert outbox.payload["assignments"] == [{
            "field": "hot_roll_daily",
            "owner_role": event.payload["owner_role"],
            "deadline": "09:00",
            "contract_version": "legacy-version",
            "entry_route": event.payload["entry_route"],
            "entry_fields": event.payload["entry_fields"],
            "fill_strategy": event.payload["fill_strategy"],
            "business_date": "2026-07-21",
            "trace_id": "trace-preserve-provenance",
            "action_route": event.payload["action_route"],
        }]
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


def test_sync_uses_gap_plan_contract_provenance_for_template_only_field() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)

        sync_daily_fact_gap_events(
            db,
            business_date=TARGET_DATE,
            bundle={
                "missing_fields": ["recovery_daily"],
                "gap_plan": {
                    "items": [{
                        "field": "recovery_daily",
                        "problem_type": "missing_field",
                        "contract_version": "task1-template-contract",
                    }],
                },
                "fact_closure": {"critical_fields": []},
            },
            trace_id="trace-recovery-template-gap",
            now=NOW,
        )
        db.commit()

        event = db.query(AgentEvent).one()
        assert event.payload["field"] == "recovery_daily"
        assert event.payload["contract_version"] == "task1-template-contract"
        assert event.payload["entry_fields"] == ["recovery_weight"]
        route = urlparse(event.payload["action_route"])
        assert route.path == "/entry/fill"
        assert parse_qs(route.query) == {
            "business_date": ["2026-07-21"],
            "field": ["recovery_daily"],
            "entry_fields": ["recovery_weight"],
            "entry_field": ["recovery_weight"],
            "owner_role": ["recovery_owner"],
            "trace_id": ["trace-recovery-template-gap"],
        }
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
            metadata_payload={"daily_fact_admin_fallback": True},
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
