from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import AgentEvent
from app.services.machine_fact_gap_service import (
    resolve_machine_stop_gap_events,
    sync_machine_fact_gap_event,
)
from app.services.report.daily_report_fact_closure import (
    build_persisted_daily_fact_surface,
)


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_machine_stop_gap_is_deduped_and_routes_to_existing_fill_page() -> None:
    db = _db_session()
    try:
        missing = {
            "status": "connected",
            "stop_count": 0,
            "top_stops": [],
        }
        first = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 21),
            intent="machine_stop",
            machine_filter="2",
            facts=missing,
            trace_id="trace-machine-gap-001",
        )
        second = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 21),
            intent="machine_stop",
            machine_filter="2",
            facts=missing,
            trace_id="trace-machine-gap-002",
        )

        assert first.id == second.id
        assert db.query(AgentEvent).count() == 1
        assert second.status == "open"
        assert second.payload["entry_route"] == "/entry/fill"
        assert second.payload["entry_fields"] == ["machine_stop_records"]
        assert "business_date=2026-07-21" in second.payload["action_route"]
        assert "entry_fields=machine_stop_records" in second.payload["action_route"]
        assert second.payload["last_checked_trace_id"] == "trace-machine-gap-002"
    finally:
        db.close()


def test_machine_gap_resolves_when_fact_appears() -> None:
    db = _db_session()
    try:
        event = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 21),
            intent="machine_stop",
            machine_filter="2",
            facts={"status": "connected", "stop_count": 0, "top_stops": []},
            trace_id="trace-machine-gap-open",
        )
        resolved = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 21),
            intent="machine_stop",
            machine_filter="2",
            facts={
                "status": "connected",
                "stop_count": 1,
                "top_stops": [
                    {
                        "equipment_name": "2号机",
                        "downtime_minutes": 42,
                        "downtime_reason": "换辊",
                    }
                ],
            },
            trace_id="trace-machine-gap-resolved",
        )

        assert resolved.id == event.id
        assert resolved.status == "resolved"
        assert resolved.payload["resolution_trace_id"] == "trace-machine-gap-resolved"
    finally:
        db.close()


def test_machine_gap_does_not_resolve_from_a_different_numbered_machine() -> None:
    db = _db_session()
    try:
        event = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 21),
            intent="machine_stop",
            machine_filter="2",
            facts={"status": "connected", "stop_count": 0, "top_stops": []},
            trace_id="trace-machine-gap-exact-open",
        )

        resolved_count = resolve_machine_stop_gap_events(
            db,
            business_date=date(2026, 7, 21),
            records=[
                {
                    "machine_name": "12号机",
                    "downtime_minutes": 42,
                    "downtime_reason": "换辊",
                }
            ],
            trace_id="trace-machine-gap-wrong-machine",
        )

        assert resolved_count == 0
        assert event.status == "open"
    finally:
        db.close()


def test_missing_mes_operation_uses_alerts_instead_of_fake_manual_power_fill() -> None:
    db = _db_session()
    try:
        event = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 21),
            intent="machine_operation",
            machine_filter="2",
            facts={"status": "connected", "record_count": 0, "top_operations": []},
            trace_id="trace-machine-operation-gap",
        )

        assert event.status == "open"
        assert event.payload["entry_route"] == "/manage/alerts"
        assert event.payload["entry_fields"] == []
        assert event.payload["fill_strategy"] == "mes_source_recheck"
    finally:
        db.close()


def test_confirmed_machine_fact_does_not_create_gap_event_without_prior_gap() -> None:
    db = _db_session()
    try:
        event = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 21),
            intent="machine_operation",
            machine_filter="2",
            facts={
                "status": "connected",
                "fact_status": "confirmed",
                "record_count": 1,
                "top_operations": [{"device_name": "2号机"}],
            },
            trace_id="trace-machine-operation-confirmed",
        )

        assert event is None
        assert db.query(AgentEvent).count() == 0
    finally:
        db.close()


def test_partial_machine_operation_keeps_source_recheck_gap_open() -> None:
    db = _db_session()
    try:
        event = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 21),
            intent="machine_operation",
            machine_filter="2",
            facts={
                "status": "connected",
                "fact_status": "partial",
                "record_count": 1,
                "top_operations": [
                    {
                        "device_name": "2号机",
                        "timing_status": "missing_time",
                    }
                ],
            },
            trace_id="trace-machine-operation-partial",
        )

        assert event is not None
        assert event.status == "open"
        assert event.payload["fill_strategy"] == "mes_source_recheck"
    finally:
        db.close()


def test_machine_gap_appears_in_existing_manage_alerts_surface() -> None:
    db = _db_session()
    try:
        event = sync_machine_fact_gap_event(
            db,
            business_date=date(2026, 7, 21),
            intent="machine_stop",
            machine_filter="2",
            facts={"status": "connected", "stop_count": 0, "top_stops": []},
            trace_id="trace-machine-alert-surface",
        )

        surface = build_persisted_daily_fact_surface(db, target_date=date(2026, 7, 21))
        alert = next(
            item
            for item in surface["fact_missing"]
            if item["event_id"] == event.id
        )

        assert alert["field"] == "machine_stop_records"
        assert alert["entry_route"] == "/entry/fill"
        assert alert["entry_fields"] == ["machine_stop_records"]
    finally:
        db.close()
