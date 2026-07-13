import inspect
import re
import time
from threading import Event
from unittest.mock import MagicMock

from apscheduler.schedulers.background import BackgroundScheduler

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


def test_setup_scheduler_registers_backend_completion_jobs(monkeypatch) -> None:
    monkeypatch.setattr(scheduler_module.settings, 'MES_ADAPTER', 'mvc')
    monkeypatch.setattr(scheduler_module.settings, 'IOT_ENERGY_ADAPTER', 'null')
    scheduler = FakeScheduler()

    setup_scheduler(scheduler)

    assert set(scheduler.jobs) >= {
        'daily_report',
        'daily_fact_closure_0805',
        'daily_fact_closure_1005_refresh',
        'daily_fact_closure_startup_catchup',
        'mes_sync_core',
        'mes_sync_realtime',
        'mes_sync_business',
        'mes_month_to_date_backfill_0725',
        'mes_month_to_date_backfill_0850',
        'mes_sync_reference',
        'agent_outbox_dispatch',
        'fill_reminder',
        'data_archive',
    }
    assert scheduler.jobs['daily_report']['trigger'] == 'cron'
    assert scheduler.jobs['daily_report']['kwargs']['hour'] == 7
    assert scheduler.jobs['daily_report']['kwargs']['minute'] == 30
    assert scheduler.jobs['daily_fact_closure_0805']['trigger'] == 'cron'
    assert scheduler.jobs['daily_fact_closure_0805']['kwargs']['hour'] == 8
    assert scheduler.jobs['daily_fact_closure_0805']['kwargs']['minute'] == 5
    assert scheduler.jobs['daily_fact_closure_0805']['kwargs']['coalesce'] is True
    assert scheduler.jobs['daily_fact_closure_0805']['kwargs']['max_instances'] == 1
    assert inspect.signature(scheduler.jobs['daily_fact_closure_0805']['func']).parameters == {}
    assert scheduler.jobs['daily_fact_closure_1005_refresh']['trigger'] == 'cron'
    assert scheduler.jobs['daily_fact_closure_1005_refresh']['kwargs']['hour'] == 10
    assert scheduler.jobs['daily_fact_closure_1005_refresh']['kwargs']['minute'] == 5
    assert scheduler.jobs['daily_fact_closure_startup_catchup']['trigger'] == 'date'
    assert scheduler.jobs['daily_fact_closure_startup_catchup']['kwargs']['run_date'].tzinfo is not None
    assert inspect.signature(scheduler.jobs['daily_fact_closure_startup_catchup']['func']).parameters == {}
    assert scheduler.jobs['mes_sync_core']['trigger'] == 'interval'
    assert scheduler.jobs['mes_sync_core']['kwargs']['seconds'] == 30
    assert scheduler.jobs['mes_sync_realtime']['trigger'] == 'interval'
    assert scheduler.jobs['mes_sync_realtime']['kwargs']['seconds'] == 30
    assert scheduler.jobs['mes_sync_business']['trigger'] == 'interval'
    assert scheduler.jobs['mes_sync_business']['kwargs']['minutes'] == 10
    assert scheduler.jobs['mes_month_to_date_backfill_0725']['trigger'] == 'cron'
    assert scheduler.jobs['mes_month_to_date_backfill_0725']['kwargs']['hour'] == 7
    assert scheduler.jobs['mes_month_to_date_backfill_0725']['kwargs']['minute'] == 25
    assert scheduler.jobs['mes_month_to_date_backfill_0850']['trigger'] == 'cron'
    assert scheduler.jobs['mes_month_to_date_backfill_0850']['kwargs']['hour'] == 8
    assert scheduler.jobs['mes_month_to_date_backfill_0850']['kwargs']['minute'] == 50
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


def test_setup_scheduler_is_idempotent() -> None:
    scheduler = FakeScheduler()

    setup_scheduler(scheduler)
    first_count = len(scheduler.jobs)
    setup_scheduler(scheduler)

    assert len(scheduler.jobs) == first_count


def test_startup_daily_fact_catchup_survives_delayed_scheduler_start(monkeypatch) -> None:
    from app.tasks import daily_fact_closure

    completed = Event()
    calls = []

    def fake_startup_catchup(*, now):
        calls.append(now)
        completed.set()

    monkeypatch.setattr(daily_fact_closure, "run_startup_daily_fact_closure", fake_startup_catchup)
    monkeypatch.setattr(scheduler_module.settings, "MES_ADAPTER", "null")
    monkeypatch.setattr(scheduler_module.settings, "IOT_ENERGY_ADAPTER", "null")
    real_scheduler = BackgroundScheduler(timezone=scheduler_module.settings.DEFAULT_TIMEZONE)
    setup_scheduler(real_scheduler)

    try:
        time.sleep(1.3)
        real_scheduler.start()
        assert completed.wait(2)
    finally:
        real_scheduler.shutdown(wait=False)

    assert len(calls) == 1
    assert calls[0].tzinfo is not None


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
