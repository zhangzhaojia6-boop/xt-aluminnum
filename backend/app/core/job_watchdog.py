from __future__ import annotations

import functools
import logging
import os
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any


logger = logging.getLogger(__name__)

_running: dict[str, float] = {}
_lock = threading.Lock()

StuckJobs = list[tuple[str, float]]


def track_running(job_id: str, func: Callable[[], Any]) -> Callable[[], Any]:
    """记录定时任务从什么时候开始运行，供看门狗判断它是不是卡死了。"""

    @functools.wraps(func)
    def wrapper() -> Any:
        with _lock:
            _running[job_id] = time.monotonic()
        try:
            return func()
        finally:
            with _lock:
                _running.pop(job_id, None)

    return wrapper


def check_stuck_jobs(
    limits: Mapping[str, float],
    *,
    on_stuck: Callable[[StuckJobs], Any],
    now: float | None = None,
) -> None:
    current = time.monotonic() if now is None else now
    with _lock:
        running = dict(_running)
    stuck = [
        (job_id, round(current - started, 1))
        for job_id, started in running.items()
        if job_id in limits and current - started > limits[job_id]
    ]
    if stuck:
        on_stuck(stuck)


def exit_worker(stuck: StuckJobs) -> None:
    """线程卡在数据库驱动里时 Python 杀不掉它，只能让工作进程退出，由 uvicorn 拉起新进程接管调度。"""
    from app.core.scheduler import release_scheduler_leader

    logger.critical('scheduled jobs stuck, exiting worker so uvicorn restarts it: %s', stuck)
    try:
        release_scheduler_leader()
    finally:
        os._exit(1)


def start_job_watchdog(
    limits: Mapping[str, float],
    *,
    interval_seconds: float = 60,
    on_stuck: Callable[[StuckJobs], Any] = exit_worker,
    stop: threading.Event | None = None,
) -> threading.Thread:
    # 单独开守护线程，不占调度线程池：线程池被卡死的任务占满时，看门狗也照样能运行。
    stop_event = stop or threading.Event()

    def loop() -> None:
        while not stop_event.wait(interval_seconds):
            check_stuck_jobs(limits, on_stuck=on_stuck)

    thread = threading.Thread(target=loop, name='job-watchdog', daemon=True)
    thread.start()
    return thread
