from __future__ import annotations

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover
    BackgroundScheduler = None

from app.config import settings


scheduler = BackgroundScheduler(timezone=settings.DEFAULT_TIMEZONE) if BackgroundScheduler else None


def _add_job_once(target_scheduler, func, trigger: str, *, job_id: str, **kwargs) -> None:
    if target_scheduler is None or target_scheduler.get_job(job_id) is not None:
        return
    target_scheduler.add_job(
        func,
        trigger,
        id=job_id,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        **kwargs,
    )


def setup_scheduler(target_scheduler=None):
    active_scheduler = target_scheduler or scheduler
    if active_scheduler is None:
        return None

    from app.tasks.daily_report import generate_daily_reports
    from app.tasks.data_archive import archive_old_data
    from app.tasks.fill_reminder import send_fill_reminders
    from app.tasks.mes_sync import sync_mes_coil_snapshots

    _add_job_once(active_scheduler, generate_daily_reports, 'cron', job_id='daily_report', hour=6, minute=0)
    _add_job_once(active_scheduler, sync_mes_coil_snapshots, 'interval', job_id='mes_sync', minutes=30)
    _add_job_once(active_scheduler, send_fill_reminders, 'cron', job_id='fill_reminder', hour='8,14,20', minute=0)
    _add_job_once(active_scheduler, archive_old_data, 'cron', job_id='data_archive', day_of_week='sun', hour=2)
    return active_scheduler
