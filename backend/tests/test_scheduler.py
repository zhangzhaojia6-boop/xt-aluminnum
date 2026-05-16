from app.core.scheduler import setup_scheduler


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


def test_setup_scheduler_registers_backend_completion_jobs() -> None:
    scheduler = FakeScheduler()

    setup_scheduler(scheduler)

    assert set(scheduler.jobs) >= {'daily_report', 'mes_sync', 'fill_reminder', 'data_archive'}
    assert scheduler.jobs['daily_report']['trigger'] == 'cron'
    assert scheduler.jobs['mes_sync']['trigger'] == 'interval'
    assert scheduler.jobs['fill_reminder']['trigger'] == 'cron'
    assert scheduler.jobs['data_archive']['trigger'] == 'cron'


def test_setup_scheduler_is_idempotent() -> None:
    scheduler = FakeScheduler()

    setup_scheduler(scheduler)
    first_count = len(scheduler.jobs)
    setup_scheduler(scheduler)

    assert len(scheduler.jobs) == first_count
