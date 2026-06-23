from __future__ import annotations

from collections.abc import Iterator
import importlib.util
from datetime import date
from pathlib import Path
from typing import cast

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Table, create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.agent_communication import ChatInboxMessage, MultimodalEvidence
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection
from app.models.system import User


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
            cast(Table, ChatInboxMessage.__table__),
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


def test_daily_fact_bundle_tables_are_registered() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyFactBundleRun.__table__),
            cast(Table, DailyFactBundleSnapshot.__table__),
            cast(Table, DailyFactCorrection.__table__),
        ],
    )

    _assert_daily_fact_bundle_schema(inspect(engine))


def test_daily_fact_bundle_migration_creates_sqlite_tables_and_indexes(monkeypatch) -> None:
    migration = _load_daily_fact_bundle_migration()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        sa.Table("users", sa.MetaData(), sa.Column("id", sa.Integer(), primary_key=True)).create(connection)
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(migration, "op", operations)

        migration.upgrade()
        _assert_daily_fact_bundle_schema(inspect(connection))

        migration.upgrade()
        _assert_daily_fact_bundle_schema(inspect(connection))

        migration.downgrade()
        table_names = set(inspect(connection).get_table_names())
        assert "daily_fact_bundle_runs" not in table_names
        assert "daily_fact_bundle_snapshots" not in table_names
        assert "daily_fact_corrections" not in table_names


def test_build_daily_fact_bundle_uses_template_facts(monkeypatch, db_session: Session) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        assert target_date == date(2026, 6, 19)
        return {
            "values": {
                "total_output_daily": 366,
                "total_electricity_kwh": 146500,
            },
            "sources": {
                "total_output_daily": "mes_packaging_output",
                "total_electricity_kwh": "owner_or_energy_summary",
            },
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["business_date"] == "2026-06-19"
    assert bundle["status"] == "ready"
    assert isinstance(bundle["generated_at"], str)
    fact = bundle["facts"]["total_output_daily"]
    assert fact["value"] == 366
    assert fact["unit"] == "吨"
    assert fact["source"] == "mes_packaging_output"
    assert fact["source_type"] == "mes_packaging_output"
    assert fact["priority"] == 80
    assert fact["confidence"] == 0.85
    assert fact["adoption_reason"] == "来自 mes_packaging_output"
    assert fact["source_detail"] == {"source": "mes_packaging_output"}
    assert bundle["missing_fields"] == []
    assert bundle["missing"] == []
    assert bundle["conflicts"] == []


def test_root_owner_correction_overrides_template_fact(monkeypatch, db_session: Session) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        assert target_date == date(2026, 6, 19)
        return {
            "values": {"total_output_daily": 355},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        User(
            id=983,
            username="root_owner",
            password_hash="hashed",
            name="root_owner",
            role="admin",
        )
    )
    db_session.flush()
    db_session.add(
        DailyFactCorrection(
            business_date=date(2026, 6, 19),
            field_name="total_output_daily",
            value_payload={"value": 366},
            unit="吨",
            source_text="6月19日车间总产量改成366吨，直接按这个发。",
            before_value={"value": 355, "source": "mes_packaging_output"},
            reason="root_owner 钉钉确认",
            actor_user_id=983,
            trace_id="trace-root-owner-correction",
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fact = bundle["facts"]["total_output_daily"]
    assert fact["value"] == 366
    assert fact["source"] == "root_owner_correction"
    assert fact["source_type"] == "root_owner_correction"
    assert fact["priority"] == 100
    assert fact["confidence"] == 1.0
    assert fact["freshness"] == "confirmed"
    assert fact["adoption_reason"] == "root_owner 钉钉确认"
    assert fact["source_detail"] == {
        "source": "root_owner_correction",
        "correction_id": 1,
        "actor_user_id": 983,
        "trace_id": "trace-root-owner-correction",
        "source_text": "6月19日车间总产量改成366吨，直接按这个发。",
        "business_date": "2026-06-19",
    }
    assert fact["source_ref"] == {
        "source": "root_owner_correction",
        "correction_id": 1,
        "actor_user_id": 983,
        "trace_id": "trace-root-owner-correction",
        "source_text": "6月19日车间总产量改成366吨，直接按这个发。",
        "business_date": "2026-06-19",
    }
    assert bundle["sources"]["total_output_daily"]["source"] == "root_owner_correction"
    assert bundle["correction_refs"] == [
        {"id": 1, "field_name": "total_output_daily", "trace_id": "trace-root-owner-correction"}
    ]
    assert bundle["conflicts"][0] == {
        "field": "total_output_daily",
        "type": "root_owner_correction",
        "adopted_source": "root_owner_correction",
        "previous_source": "mes_packaging_output",
        "previous_value": 355,
        "adopted_value": 366,
        "reason": "root_owner 钉钉确认",
    }
    assert bundle["confidence"] == 1.0
    assert bundle["status"] == "partial"


def test_build_daily_fact_bundle_reuses_existing_run_for_same_run_key(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 366},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 20), persist_run=True)
    daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 20), persist_run=True)

    runs = db_session.query(DailyFactBundleRun).all()
    snapshots = db_session.query(DailyFactBundleSnapshot).all()
    assert len(runs) == 1
    assert runs[0].business_date == date(2026, 6, 20)
    assert snapshots == []


def test_build_daily_fact_bundle_recovers_when_run_insert_hits_unique_race(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    business_date = date(2026, 6, 23)
    run_key = daily_fact_bundle._run_key(business_date=business_date, trace_id=None)
    race_triggered = False

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 366},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    class RaceContext:
        def __enter__(self) -> None:
            nonlocal race_triggered
            race_triggered = True
            db_session.execute(
                cast(Table, DailyFactBundleRun.__table__).insert().values(
                    run_key=run_key,
                    business_date=business_date,
                    status="ready",
                    source_status={},
                    missing_count=0,
                    conflict_count=0,
                )
            )
            raise IntegrityError("insert", {}, Exception("unique"))

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
            return False

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    monkeypatch.setattr(db_session, "begin_nested", lambda: RaceContext())

    daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=business_date, persist_run=True)

    runs = db_session.query(DailyFactBundleRun).all()
    assert race_triggered is True
    assert len(runs) == 1
    assert runs[0].run_key == run_key


def test_build_daily_fact_bundle_preserves_source_mapping_in_bundle_and_snapshot(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 366},
            "sources": {
                "total_output_daily": {
                    "source": "owner_daily",
                    "field": "total_output_daily",
                    "table": "x",
                    "token": "secret-token",
                },
            },
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 21),
        persist_run=True,
        snapshot_reason="formal_daily_report",
    )

    assert bundle["facts"]["total_output_daily"]["source"] == "owner_daily"
    assert bundle["facts"]["total_output_daily"]["source_type"] == "owner_daily"
    assert bundle["facts"]["total_output_daily"]["source_detail"] == {
        "source": "owner_daily",
        "field": "total_output_daily",
        "table": "x",
    }
    assert bundle["sources"]["total_output_daily"] == {
        "source": "owner_daily",
        "field": "total_output_daily",
        "table": "x",
    }
    snapshot = db_session.query(DailyFactBundleSnapshot).one()
    assert snapshot.snapshot_reason == "formal_daily_report"
    assert snapshot.facts["total_output_daily"]["value"] == 366
    assert snapshot.sources["total_output_daily"] == {
        "source": "owner_daily",
        "field": "total_output_daily",
        "table": "x",
    }
    assert len(snapshot.payload_hash) == 64


def test_build_daily_fact_bundle_uses_template_projection_priority(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"daily_contract_weight": 120},
            "sources": {"daily_contract_weight": "contract_projection"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 22))

    assert bundle["facts"]["daily_contract_weight"]["priority"] == 60
    assert bundle["facts"]["daily_contract_weight"]["confidence"] == 0.65


def test_refresh_bundle_metadata_syncs_fact_overlays() -> None:
    from app.services.report import daily_fact_bundle

    bundle = {
        "status": "partial",
        "facts": {
            "total_output_daily": {
                "value": 400,
                "unit": "吨",
                "source": "root_owner_correction",
                "source_type": "root_owner_correction",
                "priority": 100,
                "confidence": 1.0,
                "freshness": "confirmed",
                "adoption_reason": "root_owner 确认",
                "source_detail": {
                    "source": "root_owner_correction",
                    "correction_id": 7,
                    "token": "secret-token",
                },
            },
        },
        "missing_fields": [],
        "missing": ["stale_missing"],
        "conflicts": [],
    }

    refreshed = daily_fact_bundle._refresh_bundle_metadata(bundle)

    assert refreshed["sources"]["total_output_daily"] == {
        "source": "root_owner_correction",
        "correction_id": 7,
    }
    assert refreshed["freshness"]["total_output_daily"] == "confirmed"
    assert refreshed["confidence"] == 1.0
    assert refreshed["missing_fields"] == []
    assert refreshed["missing"] == []
    assert refreshed["status"] == "ready"

    refreshed["missing_fields"] = ["total_gas_m3"]
    daily_fact_bundle._refresh_bundle_metadata(refreshed)

    assert refreshed["missing"] == ["total_gas_m3"]
    assert refreshed["status"] == "blocked"


def _assert_daily_fact_bundle_schema(inspector: sa.Inspector) -> None:
    table_names = set(inspector.get_table_names())
    assert "daily_fact_bundle_runs" in table_names
    assert "daily_fact_bundle_snapshots" in table_names
    assert "daily_fact_corrections" in table_names

    run_indexes = inspector.get_indexes("daily_fact_bundle_runs")
    snapshot_indexes = inspector.get_indexes("daily_fact_bundle_snapshots")
    correction_indexes = inspector.get_indexes("daily_fact_corrections")
    assert any("run_key" in index["column_names"] and bool(index.get("unique")) for index in run_indexes)
    assert any("business_date" in index["column_names"] for index in run_indexes)
    assert any("run_id" in index["column_names"] for index in snapshot_indexes)
    assert any("payload_hash" in index["column_names"] for index in snapshot_indexes)
    assert any("field_name" in index["column_names"] for index in correction_indexes)


def _load_daily_fact_bundle_migration():
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0050_daily_fact_bundle.py"
    spec = importlib.util.spec_from_file_location("daily_fact_bundle_migration_0050", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
