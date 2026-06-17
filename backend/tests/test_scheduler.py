import re
from unittest.mock import MagicMock

from app.core import scheduler as scheduler_module
from app.core.scheduler import release_scheduler_leader, setup_scheduler, try_acquire_scheduler_leader
from tests.path_helpers import BACKEND_ROOT


class FakeScheduler:
    def __init__(self) -> None:
        self.jobs = {}

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def add_job(self, func, trigger, **kwargs):
        self.jobs[kwargs['id']] = {
            'func': func,
            'trigger': trigger,
            'kwargs': kwargs,
        }

    def remove_job(self, job_id: str):
        del self.jobs[job_id]


def test_setup_scheduler_registers_backend_completion_jobs(monkeypatch) -> None:
    monkeypatch.setattr(scheduler_module.settings, 'MES_ADAPTER', 'mvc')
    monkeypatch.setattr(scheduler_module.settings, 'IOT_ENERGY_ADAPTER', 'null')
    scheduler = FakeScheduler()

    setup_scheduler(scheduler)

    assert set(scheduler.jobs) >= {
        'daily_report_forecast',
        'daily_report_final',
        'mes_sync_core',
        'mes_sync_realtime',
        'mes_sync_business',
        'mes_sync_reference',
        'agent_outbox_dispatch',
        'fill_reminder',
        'data_archive',
    }
    assert 'daily_report' not in scheduler.jobs
    assert scheduler.jobs['daily_report_forecast']['trigger'] == 'cron'
    assert scheduler.jobs['daily_report_forecast']['kwargs']['hour'] == 7
    assert scheduler.jobs['daily_report_forecast']['kwargs']['minute'] == 30
    assert scheduler.jobs['daily_report_final']['trigger'] == 'cron'
    assert scheduler.jobs['daily_report_final']['kwargs']['hour'] == 9
    assert scheduler.jobs['daily_report_final']['kwargs']['minute'] == 30
    assert scheduler.jobs['mes_sync_core']['trigger'] == 'interval'
    assert scheduler.jobs['mes_sync_core']['kwargs']['seconds'] == 30
    assert scheduler.jobs['mes_sync_realtime']['trigger'] == 'interval'
    assert scheduler.jobs['mes_sync_realtime']['kwargs']['seconds'] == 30
    assert scheduler.jobs['mes_sync_business']['trigger'] == 'interval'
    assert scheduler.jobs['mes_sync_business']['kwargs']['minutes'] == 10
    assert scheduler.jobs['mes_sync_reference']['trigger'] == 'interval'
    assert scheduler.jobs['mes_sync_reference']['kwargs']['minutes'] == 360
    assert scheduler.jobs['agent_outbox_dispatch']['trigger'] == 'interval'
    assert scheduler.jobs['agent_outbox_dispatch']['kwargs']['seconds'] == 60
    assert scheduler.jobs['fill_reminder']['trigger'] == 'cron'
    assert scheduler.jobs['data_archive']['trigger'] == 'cron'


def test_setup_scheduler_registers_iot_energy_sync_only_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(scheduler_module.settings, 'MES_ADAPTER', 'null')
    monkeypatch.setattr(scheduler_module.settings, 'IOT_ENERGY_ADAPTER', 'sqlserver')
    monkeypatch.setattr(scheduler_module.settings, 'IOT_ENERGY_SYNC_POLL_SECONDS', 60, raising=False)
    scheduler = FakeScheduler()

    setup_scheduler(scheduler)

    assert 'iot_energy_sync' in scheduler.jobs
    assert scheduler.jobs['iot_energy_sync']['trigger'] == 'interval'
    assert scheduler.jobs['iot_energy_sync']['kwargs']['seconds'] == 60


def test_setup_scheduler_removes_legacy_daily_report_job(monkeypatch) -> None:
    monkeypatch.setattr(scheduler_module.settings, 'MES_ADAPTER', 'null')
    monkeypatch.setattr(scheduler_module.settings, 'IOT_ENERGY_ADAPTER', 'null')
    scheduler = FakeScheduler()
    scheduler.jobs['daily_report'] = {
        'func': object(),
        'trigger': 'cron',
        'kwargs': {'id': 'daily_report', 'hour': 8, 'minute': 0},
    }

    setup_scheduler(scheduler)

    assert 'daily_report' not in scheduler.jobs
    assert scheduler.jobs['daily_report_forecast']['kwargs']['hour'] == 7
    assert scheduler.jobs['daily_report_forecast']['kwargs']['minute'] == 30
    assert scheduler.jobs['daily_report_final']['kwargs']['hour'] == 9
    assert scheduler.jobs['daily_report_final']['kwargs']['minute'] == 30


def test_setup_scheduler_is_idempotent() -> None:
    scheduler = FakeScheduler()

    setup_scheduler(scheduler)
    first_count = len(scheduler.jobs)
    setup_scheduler(scheduler)

    assert len(scheduler.jobs) == first_count


def test_executive_snapshot_runs_after_business_day_closes() -> None:
    source = (BACKEND_ROOT / 'app' / 'main.py').read_text(encoding='utf-8')

    assert 'last_completed_production_business_date()' in source
    assert re.search(
        r'scheduler\.add_job\(\s*_run_executive_daily_snapshot,[\s\S]*hour=8,[\s\S]*minute=20,[\s\S]*id=\'executive_daily_snapshot\'',
        source,
    )


def _reset_leader_state() -> None:
    scheduler_module._leader_connection = None


def test_try_acquire_returns_true_immediately_for_non_postgres(monkeypatch) -> None:
    _reset_leader_state()
    fake_engine = MagicMock()
    fake_engine.dialect.name = 'sqlite'
    monkeypatch.setattr('app.database.get_engine', lambda: fake_engine)

    assert try_acquire_scheduler_leader() is True
    fake_engine.connect.assert_not_called()


def test_try_acquire_returns_true_when_postgres_lock_succeeds(monkeypatch) -> None:
    _reset_leader_state()
    fake_conn = MagicMock()
    fake_conn.execute.return_value.scalar.return_value = True
    fake_engine = MagicMock()
    fake_engine.dialect.name = 'postgresql'
    fake_engine.connect.return_value = fake_conn
    monkeypatch.setattr('app.database.get_engine', lambda: fake_engine)

    try:
        assert try_acquire_scheduler_leader() is True
        assert scheduler_module._leader_connection is fake_conn
        fake_conn.close.assert_not_called()
    finally:
        scheduler_module._leader_connection = None


def test_try_acquire_returns_false_and_closes_when_lock_unavailable(monkeypatch) -> None:
    _reset_leader_state()
    fake_conn = MagicMock()
    fake_conn.execute.return_value.scalar.return_value = False
    fake_engine = MagicMock()
    fake_engine.dialect.name = 'postgresql'
    fake_engine.connect.return_value = fake_conn
    monkeypatch.setattr('app.database.get_engine', lambda: fake_engine)

    assert try_acquire_scheduler_leader() is False
    assert scheduler_module._leader_connection is None
    fake_conn.close.assert_called_once()


def test_try_acquire_is_idempotent_when_already_leader(monkeypatch) -> None:
    _reset_leader_state()
    held_conn = MagicMock()
    scheduler_module._leader_connection = held_conn
    fake_engine = MagicMock()
    monkeypatch.setattr('app.database.get_engine', lambda: fake_engine)

    try:
        assert try_acquire_scheduler_leader() is True
        fake_engine.connect.assert_not_called()
    finally:
        scheduler_module._leader_connection = None


def test_release_unlocks_and_closes_connection() -> None:
    _reset_leader_state()
    fake_conn = MagicMock()
    scheduler_module._leader_connection = fake_conn

    release_scheduler_leader()

    fake_conn.execute.assert_called_once()
    fake_conn.close.assert_called_once()
    assert scheduler_module._leader_connection is None


def test_release_is_safe_when_not_leader() -> None:
    _reset_leader_state()
    release_scheduler_leader()
    assert scheduler_module._leader_connection is None
