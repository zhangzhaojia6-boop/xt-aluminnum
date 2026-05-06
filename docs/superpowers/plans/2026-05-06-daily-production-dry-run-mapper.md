# Daily Production Dry Run Mapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert legacy `每日产量` workbooks from `D:\鑫泰报表` into a read-only canonical preview with explicit ton units and suspicious-scale issues before any database import.

**Architecture:** Add a focused daily-production canonical parser that reads the `综合报表` shape, carries merged workshop labels forward, maps daily/month-to-date input/output/scrap fields, and returns row-level issues. Wire the parser into `legacy_data_profile_service` preview only; no database writes.

**Tech Stack:** Python dataclasses, pandas, pytest.

---

### Task 1: Build the Dry-Run Parser

**Files:**
- Create: `backend/app/services/daily_production_canonical_service.py`
- Create: `backend/tests/test_daily_production_canonical_service.py`
- Modify: `backend/app/services/legacy_data_profile_service.py`
- Modify: `backend/tests/test_legacy_data_profile_service.py`

- [x] **Step 1: Write failing parser tests**

Add tests for:
- date extraction from the title row;
- forward-filling merged workshop labels;
- mapping daily and month-to-date input/output/scrap values in tons;
- flagging `每日产量` values over a safe ton threshold as suspicious instead of silently accepting `10w`-scale data.

- [x] **Step 2: Verify RED**

Run:

```bash
python -m pytest backend/tests/test_daily_production_canonical_service.py -q
```

Expected: fail because `daily_production_canonical_service` does not exist.

Execution note: RED was captured by the previous backend collection failure (`ModuleNotFoundError: No module named 'app.services.daily_production_canonical_service'`). By the time this checkpoint resumed, the implementation file already existed in the working tree, so fresh verification continued from GREEN.

- [x] **Step 3: Implement minimal parser**

Implement `parse_daily_production_sheet()` and `parse_daily_production_workbook()` without any database writes.

- [x] **Step 4: Wire preview into source profiling**

When `profile_historical_path()` classifies a workbook as `daily_production_report`, add `daily_production_preview` for sampled sheets.

- [x] **Step 5: Verify GREEN and regressions**

Run:

```bash
python -m pytest backend/tests/test_daily_production_canonical_service.py backend/tests/test_legacy_data_profile_service.py -q
python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q
git diff --check
```

Expected: all tests pass and no whitespace errors.
