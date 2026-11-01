from threading import Event, Thread

import pytest

from app.core import job_watchdog


def test_track_running_records_job_only_while_it_runs() -> None:
    seen = {}

    def job():
        seen['running'] = dict(job_watchdog._running)
        return 'done'

    assert job_watchdog.track_running('mes_sync_core', job)() == 'done'
    assert 'mes_sync_core' in seen['running']
    assert 'mes_sync_core' not in job_watchdog._running


def test_track_running_clears_job_when_it_raises() -> None:
    def job():
        raise RuntimeError('mes down')

    with pytest.raises(RuntimeError):
        job_watchdog.track_running('mes_sync_core', job)()

    assert 'mes_sync_core' not in job_watchdog._running


def test_check_stuck_jobs_reports_only_jobs_past_their_limit(monkeypatch) -> None:
    monkeypatch.setattr(job_watchdog, '_running', {'mes_sync_core': 100.0, 'mes_sync_business': 100.0, 'other': 0.0})
    calls = []

    job_watchdog.check_stuck_jobs(
        {'mes_sync_core': 1200, 'mes_sync_business': 1800},
        on_stuck=calls.append,
        now=100.0 + 1500,
    )

    assert calls == [[('mes_sync_core', 1500.0)]]


def test_check_stuck_jobs_stays_quiet_when_nothing_is_stuck(monkeypatch) -> None:
    monkeypatch.setattr(job_watchdog, '_running', {'mes_sync_core': 100.0})
    calls = []

    job_watchdog.check_stuck_jobs({'mes_sync_core': 1200}, on_stuck=calls.append, now=100.0 + 60)

    assert calls == []


def test_stuck_job_exits_worker_after_releasing_scheduler_lock(monkeypatch) -> None:
    from app.core import scheduler as scheduler_module

    events = []
    monkeypatch.setattr(scheduler_module, 'release_scheduler_leader', lambda: events.append('released'))
    monkeypatch.setattr(job_watchdog.os, '_exit', lambda code: events.append(('exit', code)))

    job_watchdog.exit_worker([('mes_sync_core', 1500.0)])

    assert events == ['released', ('exit', 1)]


def test_stuck_job_exits_worker_even_if_releasing_the_lock_fails(monkeypatch) -> None:
    from app.core import scheduler as scheduler_module

    exits = []

    def broken_release():
        raise RuntimeError('db gone')

    monkeypatch.setattr(scheduler_module, 'release_scheduler_leader', broken_release)
    monkeypatch.setattr(job_watchdog.os, '_exit', exits.append)

    with pytest.raises(RuntimeError):
        job_watchdog.exit_worker([('mes_sync_core', 1500.0)])

    assert exits == [1]


def test_watchdog_thread_sees_a_hung_job(monkeypatch) -> None:
    release = Event()
    reported = Event()
    stuck_reports = []

    def hung_job():
        release.wait(5)

    def on_stuck(stuck):
        stuck_reports.append(stuck)
        reported.set()

    worker = Thread(target=job_watchdog.track_running('mes_sync_realtime', hung_job), daemon=True)
    worker.start()
    stop = Event()
    watchdog = job_watchdog.start_job_watchdog(
        {'mes_sync_realtime': 0.05},
        interval_seconds=0.02,
        on_stuck=on_stuck,
        stop=stop,
    )
    try:
        assert reported.wait(2)
    finally:
        stop.set()
        release.set()
        worker.join(2)
        watchdog.join(2)

    assert watchdog.daemon is True
    assert stuck_reports[0][0][0] == 'mes_sync_realtime'
    assert 'mes_sync_realtime' not in job_watchdog._running
