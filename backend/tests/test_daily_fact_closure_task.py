from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Query, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.agent_communication import MultimodalEvidence
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection
from app.models.system import User
from app.tasks import daily_fact_closure as task_module


SHANGHAI = ZoneInfo("Asia/Shanghai")


@pytest.fixture(autouse=True)
def stub_daily_fact_gap_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        task_module,
        "sync_daily_fact_gap_events",
        lambda *_args, **_kwargs: {
            "created": 0,
            "resolved": 0,
            "open": 0,
            "delivery_status": "not_needed",
            "outbox_message_id": None,
        },
    )


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, User.__table__),
            cast(Table, MultimodalEvidence.__table__),
            cast(Table, DailyFactBundleRun.__table__),
            cast(Table, DailyFactBundleSnapshot.__table__),
            cast(Table, DailyFactCorrection.__table__),
        ],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _stub_template_facts(monkeypatch: pytest.MonkeyPatch, value: dict[str, int]) -> None:
    from app.services.report import daily_fact_bundle

    monkeypatch.setenv("OUTPUT_SKILL_REFERENCE_MODE", "compare")
    monkeypatch.delenv("OUTPUT_SKILL_ROOT", raising=False)
    monkeypatch.delenv("OUTPUT_SKILL_REFERENCE_ROOT", raising=False)

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": value["total_output_daily"]},
            "sources": {
                "total_output_daily": {
                    "source_type": "mes_packaging_output",
                    "source_table": "MES_ProductProcessRecord",
                }
            },
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )


def test_daily_fact_closure_uses_last_completed_business_date(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    _stub_template_facts(monkeypatch, {"total_output_daily": 366})
    monkeypatch.setattr(
        task_module,
        "last_completed_production_business_date",
        lambda now=None: date(2026, 7, 7),
    )

    result = task_module.run_daily_fact_closure(
        db_session,
        now=datetime(2026, 7, 8, 8, 5, tzinfo=SHANGHAI),
    )

    assert result == {
        "business_date": "2026-07-07",
        "trace_id": "daily-fact-closure:2026-07-07",
        "status": "blocked",
    }
    assert db_session.query(DailyFactBundleRun).count() == 1
    snapshot = db_session.query(DailyFactBundleSnapshot).one()
    assert snapshot.snapshot_reason == "scheduled_daily_closure"


def test_daily_fact_closure_honors_explicit_target_date(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    _stub_template_facts(monkeypatch, {"total_output_daily": 366})
    monkeypatch.setattr(
        task_module,
        "last_completed_production_business_date",
        lambda now=None: pytest.fail("explicit target must not resolve the default business date"),
    )

    result = task_module.run_daily_fact_closure(
        db_session,
        target_date=date(2026, 7, 6),
    )

    assert result["business_date"] == "2026-07-06"
    assert result["trace_id"] == "daily-fact-closure:2026-07-06"


def test_daily_fact_closure_passes_scheduler_time_to_fact_evidence_check(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    scheduled_at = datetime(2026, 7, 8, 8, 5, tzinfo=SHANGHAI)
    captured: dict[str, object] = {}

    def fake_build(db: Session, **kwargs):
        captured.update(kwargs)
        return {"fact_closure": {"status": "blocked"}}

    monkeypatch.setattr(task_module, "build_daily_fact_bundle", fake_build)

    task_module.run_daily_fact_closure(
        db_session,
        target_date=date(2026, 7, 7),
        now=scheduled_at,
    )

    assert captured["now"] == scheduled_at


def test_daily_fact_closure_syncs_gap_events_before_commit(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    bundle = {
        "fact_closure": {"status": "blocked"},
        "missing_fields": ["total_output_daily"],
    }
    calls: list[dict] = []
    monkeypatch.setattr(task_module, "build_daily_fact_bundle", lambda *_args, **_kwargs: bundle)
    monkeypatch.setattr(
        task_module,
        "sync_daily_fact_gap_events",
        lambda _db, **kwargs: calls.append(kwargs) or {"open": 1},
    )

    task_module.run_daily_fact_closure(
        db_session,
        target_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=SHANGHAI),
    )

    assert calls == [{
        "business_date": date(2026, 7, 7),
        "bundle": bundle,
        "trace_id": "daily-fact-closure:2026-07-07",
        "now": datetime(2026, 7, 8, 8, 5, tzinfo=SHANGHAI),
    }]


def test_daily_fact_closure_never_adopts_output_skill_reference(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    source_value = {"total_output_daily": 366}
    _stub_template_facts(monkeypatch, source_value)
    fixture_dir = Path(__file__).parent / "fixtures" / "output_skill_daily_reports"
    monkeypatch.setenv("OUTPUT_SKILL_ROOT", str(fixture_dir))
    monkeypatch.setenv("OUTPUT_SKILL_REFERENCE_MODE", "adopt")

    task_module.run_daily_fact_closure(db_session, target_date=date(2026, 6, 16))

    snapshot = db_session.query(DailyFactBundleSnapshot).one()
    assert snapshot.facts["total_output_daily"]["value"] == 366
    assert snapshot.facts["total_output_daily"]["source_type"] == "mes_packaging_output"


def test_daily_fact_closure_rerun_updates_one_run_and_one_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    source_value = {"total_output_daily": 366}
    _stub_template_facts(monkeypatch, source_value)

    task_module.run_daily_fact_closure(db_session, target_date=date(2026, 7, 7))
    first_snapshot = db_session.query(DailyFactBundleSnapshot).one()
    first_hash = first_snapshot.payload_hash
    assert first_snapshot.adopted_values["total_output_daily"] == 366

    source_value["total_output_daily"] = 371
    task_module.run_daily_fact_closure(db_session, target_date=date(2026, 7, 7))

    assert db_session.query(DailyFactBundleRun).count() == 1
    assert db_session.query(DailyFactBundleSnapshot).count() == 1
    refreshed_snapshot = db_session.query(DailyFactBundleSnapshot).one()
    assert refreshed_snapshot.adopted_values["total_output_daily"] == 371
    assert refreshed_snapshot.payload_hash != first_hash
    assert refreshed_snapshot.snapshot_key is not None


def test_scheduled_snapshot_race_recovers_and_refreshes_existing_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.report import daily_fact_bundle

    engine = create_engine(f"sqlite:///{tmp_path / 'scheduled-snapshot-race.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, User.__table__),
            cast(Table, DailyFactBundleRun.__table__),
            cast(Table, DailyFactBundleSnapshot.__table__),
        ],
    )
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    first_session = SessionLocal()
    second_session = SessionLocal()
    try:
        assert second_session.query(DailyFactBundleSnapshot).count() == 0
        first_bundle = {
            "status": "ready",
            "facts": {"total_output_daily": {"value": 366, "source_type": "mes_packaging_output"}},
            "sources": {},
            "conflicts": [],
        }
        _, first_snapshot = daily_fact_bundle.persist_daily_fact_bundle_snapshot(
            first_session,
            bundle=first_bundle,
            business_date=date(2026, 7, 7),
            trace_id="daily-fact-closure:2026-07-07",
            snapshot_reason="scheduled_daily_closure",
        )
        first_session.commit()

        original_one_or_none = Query.one_or_none
        stale_snapshot_read = {"used": False}

        def one_or_none_with_race(query: Query):
            entity = query.column_descriptions[0].get("entity")
            if (
                query.session is second_session
                and entity is DailyFactBundleSnapshot
                and not stale_snapshot_read["used"]
            ):
                stale_snapshot_read["used"] = True
                return None
            return original_one_or_none(query)

        monkeypatch.setattr(Query, "one_or_none", one_or_none_with_race)
        second_bundle = {
            **first_bundle,
            "facts": {"total_output_daily": {"value": 371, "source_type": "mes_packaging_output"}},
        }
        _, second_snapshot = daily_fact_bundle.persist_daily_fact_bundle_snapshot(
            second_session,
            bundle=second_bundle,
            business_date=date(2026, 7, 7),
            trace_id="daily-fact-closure:2026-07-07",
            snapshot_reason="scheduled_daily_closure",
        )
        second_session.commit()

        assert stale_snapshot_read["used"] is True
        assert second_snapshot.id == first_snapshot.id
        with SessionLocal() as verification_session:
            assert verification_session.query(DailyFactBundleRun).count() == 1
            assert verification_session.query(DailyFactBundleSnapshot).count() == 1
            stored_snapshot = verification_session.query(DailyFactBundleSnapshot).one()
            assert stored_snapshot.adopted_values["total_output_daily"] == 371
    finally:
        first_session.close()
        second_session.close()


def test_daily_fact_closure_rolls_back_and_propagates_errors(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    def failing_build(db: Session, **kwargs):
        db.add(
            DailyFactBundleRun(
                run_key="must-be-rolled-back",
                business_date=date(2026, 7, 7),
                status="partial",
                source_status={},
            )
        )
        db.flush()
        raise RuntimeError("closure failed")

    monkeypatch.setattr(task_module, "build_daily_fact_bundle", failing_build)

    with pytest.raises(RuntimeError, match="closure failed"):
        task_module.run_daily_fact_closure(db_session, target_date=date(2026, 7, 7))

    assert db_session.query(DailyFactBundleRun).count() == 0


def test_scheduled_daily_fact_closure_uses_managed_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    fake_session = object()

    class SessionContext:
        def __enter__(self):
            events.append("enter")
            return fake_session

        def __exit__(self, exc_type, exc, traceback):
            events.append("exit")
            return False

    monkeypatch.setattr(task_module, "get_sessionmaker", lambda: SessionContext)
    monkeypatch.setattr(
        task_module,
        "run_daily_fact_closure",
        lambda db: {"status": "pass", "same_session": db is fake_session},
    )

    result = task_module.run_scheduled_daily_fact_closure()

    assert result == {"status": "pass", "same_session": True}
    assert events == ["enter", "exit"]


def test_open_gap_refresh_rechecks_each_date_and_continues_after_one_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSession:
        def rollback(self):
            return None

    fake_session = FakeSession()

    class SessionContext:
        def __enter__(self):
            return fake_session

        def __exit__(self, exc_type, exc, traceback):
            return False

    class SessionLocal:
        def __call__(self):
            return SessionContext()

    checked: list[date] = []

    def fake_run(_db, *, target_date, **_kwargs):
        checked.append(target_date)
        if target_date == date(2026, 7, 20):
            raise RuntimeError("one date failed")
        return {"business_date": target_date.isoformat(), "status": "blocked"}

    monkeypatch.setattr(task_module, "get_sessionmaker", lambda: SessionLocal())
    monkeypatch.setattr(
        task_module,
        "list_open_daily_fact_gap_dates",
        lambda _db: [date(2026, 7, 21), date(2026, 7, 20)],
    )
    monkeypatch.setattr(task_module, "run_daily_fact_closure", fake_run)
    result = task_module.run_open_daily_fact_gap_refresh()

    assert checked == [date(2026, 7, 21), date(2026, 7, 20)]
    assert result["status"] == "partial"
    assert result["checked_dates"] == 2
    assert result["results"][1] == {
        "business_date": "2026-07-20",
        "status": "failed",
        "error": "RuntimeError",
    }


def test_startup_catchup_executes_missed_business_day_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    from app.core import scheduler as scheduler_module

    class CapturingScheduler:
        def __init__(self) -> None:
            self.jobs: dict[str, dict] = {}

        def get_job(self, job_id: str):
            return self.jobs.get(job_id)

        def add_job(self, func, trigger, **kwargs) -> None:
            self.jobs[kwargs["id"]] = {"func": func, "trigger": trigger, "kwargs": kwargs}

    _stub_template_facts(monkeypatch, {"total_output_daily": 366})
    restart_at = datetime(2026, 7, 8, 9, 0, tzinfo=SHANGHAI)
    resolved_times: list[datetime | None] = []

    def resolve_business_date(now=None):
        resolved_times.append(now)
        return date(2026, 7, 7)

    SessionLocal = sessionmaker(bind=db_session.get_bind(), future=True, expire_on_commit=False)
    monkeypatch.setattr(task_module, "get_sessionmaker", lambda: SessionLocal)
    monkeypatch.setattr(task_module, "last_completed_production_business_date", resolve_business_date)
    monkeypatch.setattr(scheduler_module, "local_now", lambda: restart_at)
    scheduler = CapturingScheduler()
    scheduler_module.setup_scheduler(scheduler)

    startup_job = scheduler.jobs["daily_fact_closure_startup_catchup"]
    startup_job["func"]()
    startup_job["func"]()

    assert startup_job["trigger"] == "date"
    assert resolved_times == [restart_at, restart_at]
    db_session.expire_all()
    assert db_session.query(DailyFactBundleRun).count() == 1
    assert db_session.query(DailyFactBundleSnapshot).count() == 1
    snapshot = db_session.query(DailyFactBundleSnapshot).one()
    assert snapshot.business_date == date(2026, 7, 7)
    assert snapshot.snapshot_reason == "scheduled_daily_closure"
