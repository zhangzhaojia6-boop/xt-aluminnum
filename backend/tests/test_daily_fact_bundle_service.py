from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import cast

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Table, create_engine, inspect

from app.database import Base
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection


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
