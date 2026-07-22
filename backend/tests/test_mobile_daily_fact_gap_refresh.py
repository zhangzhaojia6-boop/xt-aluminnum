from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.agent_communication import AgentEvent
from app.routers.mobile import _enqueue_daily_fact_gap_refresh


TARGET_DATE = date(2026, 7, 21)


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _gap_event(*, status: str) -> AgentEvent:
    return AgentEvent(
        event_type="daily_fact_gap",
        severity="warning",
        status=status,
        scope_type="factory",
        source_type="daily_fact_closure",
        source_ref=f"daily_fact_gap:{TARGET_DATE.isoformat()}:total_electricity_kwh",
        business_date=TARGET_DATE,
        occurred_at=datetime(2026, 7, 22, 0, 5, tzinfo=UTC),
        payload={"field": "total_electricity_kwh"},
    )


def test_submit_enqueues_targeted_recheck_only_for_open_gap_date() -> None:
    db = _db_session()
    try:
        db.add(_gap_event(status="open"))
        db.commit()
        background_tasks = BackgroundTasks()

        queued = _enqueue_daily_fact_gap_refresh(
            db,
            background_tasks=background_tasks,
            business_date=TARGET_DATE,
        )

        assert queued is True
        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        assert task.func.__name__ == "run_daily_fact_gap_refresh_for_date"
        assert task.kwargs == {"target_date": TARGET_DATE}
    finally:
        db.close()


def test_submit_does_not_rebuild_bundle_when_date_has_no_open_gap() -> None:
    db = _db_session()
    try:
        db.add(_gap_event(status="resolved"))
        db.commit()
        background_tasks = BackgroundTasks()

        queued = _enqueue_daily_fact_gap_refresh(
            db,
            background_tasks=background_tasks,
            business_date=TARGET_DATE,
        )

        assert queued is False
        assert background_tasks.tasks == []
    finally:
        db.close()


def test_submit_stays_available_when_gap_lookup_is_unavailable(monkeypatch) -> None:
    class StubSession:
        rollback_count = 0

        def rollback(self) -> None:
            self.rollback_count += 1

    def unavailable(*_args, **_kwargs):
        raise SQLAlchemyError("agent_events_unavailable")

    monkeypatch.setattr("app.routers.mobile.has_open_daily_fact_gap", unavailable)
    db = StubSession()
    background_tasks = BackgroundTasks()

    queued = _enqueue_daily_fact_gap_refresh(
        db,  # type: ignore[arg-type]
        background_tasks=background_tasks,
        business_date=TARGET_DATE,
    )

    assert queued is False
    assert db.rollback_count == 1
    assert background_tasks.tasks == []
