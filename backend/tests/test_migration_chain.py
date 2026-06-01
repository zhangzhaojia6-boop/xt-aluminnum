import os
import subprocess
import sys

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
    assert '0034_mes_mvc_extended_sources' in current.stdout


def test_seed_production_script_is_available() -> None:
    script = BACKEND_ROOT / 'scripts' / 'seed_production.py'

    assert script.exists()
    assert 'seed_real_master_data' in script.read_text(encoding='utf-8')
