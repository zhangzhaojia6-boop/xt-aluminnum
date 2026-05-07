# Daily Schedule Rollover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep production `/readyz` ready after the business date changes by automatically ensuring the current day's default pilot schedule exists.

**Architecture:** Reuse the existing `seed_default_pilot_schedule()` service. On backend startup, run the seed once for the current business date, then register an APScheduler cron job for 00:05 Asia/Shanghai. Do not write from `/readyz`, do not change MES sync, and do not mutate production facts.

**Tech Stack:** FastAPI lifespan, APScheduler, SQLAlchemy session factory, pytest.

---

### Task 1: Rollover Regression Tests

**Files:**
- Modify: `backend/tests/test_pilot_schedule_seed.py`
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] Add a service test proving `seed_default_pilot_schedule()` can create schedules for a new business date while reusing existing pilot employees.
- [x] Add a static scheduler wiring test proving backend startup registers `default_schedule_seed` and calls the seed before `scheduler.start()`.
- [x] Run `python -m pytest backend/tests/test_pilot_schedule_seed.py backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_backend_registers_daily_default_schedule_seed_job -q`.

### Task 2: Backend Scheduler Wiring

**Files:**
- Modify: `backend/app/main.py`

- [x] Add `_run_schedule_seed()` inside lifespan using the existing session factory.
- [x] Call `_run_schedule_seed()` once on startup before long-running scheduler jobs begin.
- [x] Register `default_schedule_seed` as a daily cron job at 00:05 with `replace_existing=True`, `coalesce=True`, and `max_instances=1`.
- [x] Keep failures logged and rolled back without preventing unrelated scheduler jobs from registering.

### Task 3: Verify And Release

- [x] Run focused pytest for the rollover behavior.
- [x] Run `python -m pytest backend/tests -q`.
- [x] Run `git diff --check`.
- [ ] Update deployment state docs with the 2026-05-07 schedule recovery and automatic rollover.
- [ ] Commit, push, deploy, and verify production `/readyz` remains ready for 2026-05-07.
