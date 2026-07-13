from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.agent_communication import MultimodalEvidence
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection
from app.models.system import User
from app.tasks import daily_fact_closure as task_module


SHANGHAI = ZoneInfo("Asia/Shanghai")


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
