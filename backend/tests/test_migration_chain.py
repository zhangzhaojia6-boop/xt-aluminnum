import os
import subprocess
import sys
from datetime import date
from importlib import util as importlib_util

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tests.path_helpers import BACKEND_ROOT


def _run_alembic(command: str, database_url: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env['DATABASE_URL'] = database_url
    return subprocess.run(
        [sys.executable, '-m', 'alembic', *command.split()],
        cwd=BACKEND_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_alembic_sqlite_upgrade_downgrade_upgrade_from_empty_database(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'migration_chain.db').as_posix()}"

    for command in ('upgrade head', 'downgrade -1', 'upgrade head'):
        result = _run_alembic(command, database_url)

        assert result.returncode == 0, result.stderr


def test_alembic_sqlite_current_after_upgrade(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'migration_current.db').as_posix()}"

    upgrade = _run_alembic('upgrade head', database_url)
    assert upgrade.returncode == 0, upgrade.stderr

    current = _run_alembic('current', database_url)
    assert current.returncode == 0, current.stderr
    assert '0054_dingtalk_inbound_receipts' in current.stdout


@pytest.mark.parametrize("legacy_snapshot_count", [1, 3])
def test_0053_backfills_one_canonical_scheduled_snapshot_without_deleting_history(
    tmp_path,
    legacy_snapshot_count: int,
) -> None:
    from app.services.report import daily_fact_bundle

    database_path = tmp_path / f"migration_0053_legacy_{legacy_snapshot_count}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    business_date = date(2026, 7, 7)
    trace_id = f"daily-fact-closure:{business_date.isoformat()}"
    run_key = daily_fact_bundle._run_key(business_date=business_date, trace_id=trace_id)
    engine = create_engine(database_url, future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('0052_hermes_factory_brain')")
        )
        conn.execute(
            text(
                """
                CREATE TABLE daily_fact_bundle_runs (
                    id INTEGER NOT NULL PRIMARY KEY,
                    run_key VARCHAR(160) NOT NULL UNIQUE,
                    business_date DATE NOT NULL,
                    requested_by_id INTEGER,
                    trace_id VARCHAR(128),
                    status VARCHAR(32) NOT NULL,
                    source_status JSON NOT NULL,
                    missing_count INTEGER NOT NULL,
                    conflict_count INTEGER NOT NULL,
                    confidence INTEGER,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE daily_fact_bundle_snapshots (
                    id INTEGER NOT NULL PRIMARY KEY,
                    run_id INTEGER,
                    business_date DATE NOT NULL,
                    snapshot_reason VARCHAR(64) NOT NULL,
                    facts JSON NOT NULL,
                    sources JSON NOT NULL,
                    conflicts JSON NOT NULL,
                    adopted_values JSON NOT NULL,
                    correction_refs JSON NOT NULL,
                    dingtalk_refs JSON NOT NULL,
                    output_skill_alignment JSON NOT NULL,
                    payload_hash VARCHAR(64) NOT NULL,
                    created_by_id INTEGER,
                    trace_id VARCHAR(128),
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO daily_fact_bundle_runs
                    (id, run_key, business_date, trace_id, status, source_status,
                     missing_count, conflict_count, confidence, created_at)
                VALUES
                    (1, :run_key, :business_date, :trace_id, 'ready', '{}', 0, 0, 90,
                     '2026-07-08 08:05:00')
                """
            ),
            {
                "run_key": run_key,
                "business_date": business_date.isoformat(),
                "trace_id": trace_id,
            },
        )
        for snapshot_id in range(1, legacy_snapshot_count + 1):
            conn.execute(
                text(
                    """
                    INSERT INTO daily_fact_bundle_snapshots
                        (id, run_id, business_date, snapshot_reason, facts, sources,
                         conflicts, adopted_values, correction_refs, dingtalk_refs,
                         output_skill_alignment, payload_hash, trace_id, created_at)
                    VALUES
                        (:id, 1, :business_date, 'scheduled_daily_closure', '{}', '{}',
                         '[]', '{}', '[]', '[]', '{}', :payload_hash, :trace_id, :created_at)
                    """
                ),
                {
                    "id": snapshot_id,
                    "business_date": business_date.isoformat(),
                    "payload_hash": f"legacy-{snapshot_id}",
                    "trace_id": trace_id,
                    "created_at": f"2026-07-08 08:{snapshot_id:02d}:00",
                },
            )

    upgrade = _run_alembic("upgrade head", database_url)
    assert upgrade.returncode == 0, upgrade.stderr

    canonical_key = f"scheduled_daily_closure:{run_key}"
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, snapshot_reason, snapshot_key
                FROM daily_fact_bundle_snapshots
                ORDER BY id
                """
            )
        ).all()
    assert len(rows) == legacy_snapshot_count
    assert rows[-1] == (
        legacy_snapshot_count,
        "scheduled_daily_closure",
        canonical_key,
    )
    assert all(
        row.snapshot_reason == "scheduled_daily_closure_legacy_0053" and row.snapshot_key is None
        for row in rows[:-1]
    )

    bundle = {
        "status": "ready",
        "facts": {"total_output_daily": {"value": 366}},
        "sources": {},
        "missing": [],
        "missing_fields": [],
        "conflicts": [],
        "correction_refs": [],
        "dingtalk_refs": [],
        "output_skill_alignment": {},
    }
    with Session(engine) as db:
        _run, snapshot = daily_fact_bundle.persist_daily_fact_bundle_snapshot(
            db,
            bundle=bundle,
            business_date=business_date,
            trace_id=trace_id,
            snapshot_reason="scheduled_daily_closure",
        )
        db.commit()
        assert snapshot.id == legacy_snapshot_count

    with engine.connect() as conn:
        total_count = conn.execute(text("SELECT count(*) FROM daily_fact_bundle_snapshots")).scalar_one()
        canonical_count = conn.execute(
            text("SELECT count(*) FROM daily_fact_bundle_snapshots WHERE snapshot_key = :key"),
            {"key": canonical_key},
        ).scalar_one()
    assert total_count == legacy_snapshot_count
    assert canonical_count == 1

    downgrade = _run_alembic("downgrade 0052_hermes_factory_brain", database_url)
    assert downgrade.returncode == 0, downgrade.stderr
    with engine.connect() as conn:
        reasons = conn.execute(
            text("SELECT snapshot_reason FROM daily_fact_bundle_snapshots ORDER BY id")
        ).scalars().all()
    assert reasons == ["scheduled_daily_closure"] * legacy_snapshot_count


def test_legacy_shift_references_are_remapped_by_latest_migration(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'migration_shift_remap.db').as_posix()}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE shift_configs (id INTEGER PRIMARY KEY, code TEXT NOT NULL)"))
        conn.execute(text("CREATE TABLE attendance_schedules (id INTEGER PRIMARY KEY, employee_id INTEGER, business_date TEXT, shift_config_id INTEGER)"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, assigned_shift_ids TEXT)"))
        conn.execute(
            text(
                """
                INSERT INTO shift_configs (id, code)
                VALUES
                    (1, 'DAY'), (2, 'MID'), (3, 'NIGHT'),
                    (4, 'A'), (5, 'B'), (6, 'C')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO attendance_schedules
                    (employee_id, business_date, shift_config_id)
                VALUES
                    (101, '2026-06-02', 1)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO users
                    (username, assigned_shift_ids)
                VALUES
                    ('legacy-shift-user', '[1, 2, 3]')
                """
            )
        )

        migration_path = BACKEND_ROOT / 'alembic' / 'versions' / '0037_remap_legacy_shift_references.py'
        spec = importlib_util.spec_from_file_location('migration_0037_remap_legacy_shift_references', migration_path)
        assert spec is not None and spec.loader is not None
        migration = importlib_util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        original_get_bind = migration.op.get_bind
        migration.op.get_bind = lambda: conn
        try:
            migration.upgrade()
        finally:
            migration.op.get_bind = original_get_bind

        remapped_schedule_shift_id = conn.execute(
            text("SELECT shift_config_id FROM attendance_schedules WHERE employee_id = 101")
        ).scalar_one()
        remapped_assigned_shift_ids = conn.execute(
            text("SELECT assigned_shift_ids FROM users WHERE username = 'legacy-shift-user'")
        ).scalar_one()

    assert remapped_schedule_shift_id == 4
    assert remapped_assigned_shift_ids == '[4, 5, 6]'


def test_seed_production_script_is_available() -> None:
    script = BACKEND_ROOT / 'scripts' / 'seed_production.py'

    assert script.exists()
    assert 'seed_real_master_data' in script.read_text(encoding='utf-8')
