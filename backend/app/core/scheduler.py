from __future__ import annotations

import logging

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # pragma: no cover
    BackgroundScheduler = None

from sqlalchemy import text

from app.config import settings


logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=settings.DEFAULT_TIMEZONE) if BackgroundScheduler else None

SCHEDULER_LEADER_LOCK_KEY = 0x5CEDDE5CADE00001  # 使用任意稳定整数即可，确保多 worker 共用同一 key
_leader_connection = None


def try_acquire_scheduler_leader() -> bool:
    """尝试获取调度器领导锁。同一时间只有一个 worker 拿得到。

    使用 PostgreSQL session-level advisory lock：拿到锁的那个 worker 持有专用连接直到进程退出，
    自动释放给下一个候选 worker。SQLite / 非 Postgres 后端直接放行（开发模式假装单 worker）。
    """
    global _leader_connection
    if _leader_connection is not None:
        return True

    from app.database import get_engine

    engine = get_engine()
    if engine.dialect.name != 'postgresql':
        return True

    conn = engine.connect()
    try:
        result = conn.execute(text('SELECT pg_try_advisory_lock(:key)'), {'key': SCHEDULER_LEADER_LOCK_KEY}).scalar()
    except Exception:
        conn.close()
        raise

    if not result:
        conn.close()
        logger.info('scheduler leader lock not acquired (another worker holds it); scheduler stays idle')
        return False

    _leader_connection = conn
    logger.info('scheduler leader lock acquired; this worker will run cron jobs')
    return True


def release_scheduler_leader() -> None:
    global _leader_connection
    if _leader_connection is None:
        return
    try:
        _leader_connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': SCHEDULER_LEADER_LOCK_KEY})
    except Exception:
        logger.warning('failed to release scheduler leader lock cleanly', exc_info=True)
    finally:
        _leader_connection.close()
        _leader_connection = None


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
    from app.tasks.agent_outbox import dispatch_due_agent_outbox_messages
    from app.tasks.iot_energy_sync import sync_iot_energy_snapshots
    from app.tasks.mes_sync import (
        sync_mes_month_to_date_projection,
        sync_mes_business_projection,
        sync_mes_coil_snapshots,
        sync_mes_realtime_projection,
        sync_mes_reference_projection,
    )

    _add_job_once(active_scheduler, generate_daily_reports, 'cron', job_id='daily_report', hour=7, minute=30)
    if (settings.MES_ADAPTER or 'null').strip().lower() != 'null':
        _add_job_once(
            active_scheduler,
            sync_mes_coil_snapshots,
            'interval',
            job_id='mes_sync_core',
            seconds=settings.MES_SYNC_POLL_SECONDS,
        )
        _add_job_once(
            active_scheduler,
            sync_mes_realtime_projection,
            'interval',
            job_id='mes_sync_realtime',
            seconds=settings.MES_REALTIME_SYNC_POLL_SECONDS,
        )
        _add_job_once(
            active_scheduler,
            sync_mes_business_projection,
            'interval',
            job_id='mes_sync_business',
            minutes=settings.MES_BUSINESS_SYNC_POLL_MINUTES,
        )
        _add_job_once(
            active_scheduler,
            sync_mes_month_to_date_projection,
            'cron',
            job_id='mes_month_to_date_backfill_0725',
            hour=7,
            minute=25,
        )
        _add_job_once(
            active_scheduler,
            sync_mes_month_to_date_projection,
            'cron',
            job_id='mes_month_to_date_backfill_0850',
            hour=8,
            minute=50,
        )
        _add_job_once(
            active_scheduler,
            sync_mes_reference_projection,
            'interval',
            job_id='mes_sync_reference',
            minutes=settings.MES_REFERENCE_SYNC_POLL_MINUTES,
        )
    if (settings.IOT_ENERGY_ADAPTER or 'null').strip().lower() != 'null':
        _add_job_once(
            active_scheduler,
            sync_iot_energy_snapshots,
            'interval',
            job_id='iot_energy_sync',
            seconds=settings.IOT_ENERGY_SYNC_POLL_SECONDS,
        )
    _add_job_once(
        active_scheduler,
        dispatch_due_agent_outbox_messages,
        'interval',
        job_id='agent_outbox_dispatch',
        seconds=60,
    )
    _add_job_once(active_scheduler, send_fill_reminders, 'cron', job_id='fill_reminder', hour='8,14,20', minute=0)
    _add_job_once(active_scheduler, archive_old_data, 'cron', job_id='data_archive', day_of_week='sun', hour=2)
    return active_scheduler
