import os
import subprocess
import sys
from importlib import util as importlib_util

from sqlalchemy import create_engine, text

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
    assert '0037_remap_legacy_shift_references' in current.stdout


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
