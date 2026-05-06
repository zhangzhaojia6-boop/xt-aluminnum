# Daily Production Import Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist parsed `daily_production_report` workbooks into the existing import audit tables as a dry-run gate before any formal production fact writes.

**Architecture:** Reuse `store_import_file()` and the existing `ImportBatch` / `ImportRow` staging model. The daily-production parser remains the canonical mapper; this change only records parsed summary rows, quality status, units, lineage, and issues for review.

**Tech Stack:** FastAPI upload path, SQLAlchemy import models, pandas workbook parsing, pytest.

---

### Task 1: Add Daily Production Import Tests

**Files:**
- Modify: `backend/tests/test_daily_production_canonical_service.py`
- Create: `backend/tests/test_import_service_daily_production.py`

- [x] **Step 1: Write a failing service test**

Add a test that monkeypatches file storage and `parse_daily_production_workbook()`, calls `store_import_file(..., import_type='daily_production_report')`, and asserts:
- `summary["columns"]` is the daily production canonical field order;
- one `ImportRow` is added per parsed summary sheet;
- ready rows count as `success`;
- warning rows still count as `success` but preserve `mapped_data["quality_status"] == "warning"` and `issues`;
- blocked rows count as `failed` and contribute to `batch.error_summary`.

Run:

```bash
python -m pytest backend/tests/test_import_service_daily_production.py -q
```

Expected: fail because `store_import_file()` currently falls through to generic DataFrame parsing for `daily_production_report`.

- [x] **Step 2: Add field-order test**

Add a small parser-level assertion for `daily_production_row_summary_fields()` so import summaries have stable columns.

Run:

```bash
python -m pytest backend/tests/test_daily_production_canonical_service.py -q
```

Expected: fail because the function does not exist yet.

### Task 2: Implement the Import Gate

**Files:**
- Modify: `backend/app/services/daily_production_canonical_service.py`
- Modify: `backend/app/services/import_service.py`

- [x] **Step 1: Add stable daily production field order**

Expose `daily_production_row_summary_fields()` from `daily_production_canonical_service.py`. Include date, source batch, sheet name, source unit, row count, daily/month-to-date input/output/scrap ton fields, lineage hash, quality status, and issues.

- [x] **Step 2: Wire `store_import_file()`**

Add a `daily_production_report` branch beside `contract_report` and `yield_rate_matrix`:
- call `parse_daily_production_workbook(stored_path, source_batch_id=batch.id, year_hint=batch.created_at.year if available)`;
- create one `ImportRow` for each parsed sheet;
- use each parsed item status and error message as-is;
- set failed count from non-`success` rows;
- join row error messages into `error_summary`;
- never write to `ShiftProductionData` or other formal production tables.

- [x] **Step 3: Verify green**

Run:

```bash
python -m pytest backend/tests/test_import_service_daily_production.py backend/tests/test_daily_production_canonical_service.py -q
python -m pytest backend/tests/test_import_service_contract_report.py backend/tests/test_import_service_yield_matrix.py -q
```

Expected: all tests pass.

### Task 3: Real Workbook Dry-Run Evidence

**Files:**
- Modify: `docs/deploy/current-state.md`

- [x] **Step 1: Run local real workbook probe**

Use `D:\鑫泰报表\5.5\鑫泰每日产量5月.xls` with the new import path in a controlled local test session and verify:
- batch import type is `daily_production_report`;
- total rows are parsed from `综合报表`;
- `source_unit` is `t`;
- May 3 output is about `1935.649t`, not `10w`;
- no `ShiftProductionData` rows are written by this import gate.

- [x] **Step 2: Update current-state evidence**

Append the exact test commands and real dry-run result summary to `docs/deploy/current-state.md`.

- [x] **Step 3: Final verification**

Run:

```bash
python -m pytest backend/tests -q
git diff --check
git status --short --branch
```

Expected: backend suite passes, whitespace check is clean except known line-ending warnings, and only intended files changed.

Execution note: `python -m pytest backend/tests -q --durations=10` returned `713 passed, 124 deselected, 31 warnings`; `git diff --check` passed with only Windows CRLF warnings. Real workbook dry-run was rechecked with `D:\鑫泰报表\5.5\鑫泰每日产量5月.xls`: `daily_output_tons=1935.649`, `source_unit=t`, and `shift_production_data_rows=0`.
