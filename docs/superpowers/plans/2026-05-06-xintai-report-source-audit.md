# Xintai Report Source Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe read-only audit path for `D:\鑫泰报表` so real production files can be classified, sampled, and mapped before any database import is attempted.

**Architecture:** Reuse `backend/app/services/legacy_data_profile_service.py` as the historical source profiling surface. Extend it to recurse through dated folders, classify the common workbook families, and return relative-path evidence. Do not write production database rows in this plan.

**Tech Stack:** Python, pandas/xlrd/openpyxl, pytest, existing legacy profile tests.

---

### Task 1: Expand File Classification

**Files:**
- Modify: `backend/app/services/legacy_data_profile_service.py`
- Modify: `backend/tests/test_legacy_data_profile_service.py`

- [x] **Step 1: Add classification tests**

Add tests for these real source names:
- `4月份各车间能耗统计表.xls` -> `energy_usage_report`
- `4月份各车间天然气用量统计表.xls` -> `gas_usage_report`
- `耗材表.xls` -> `consumable_usage_report`
- `园区电+新厂电.xls` -> `utility_power_report`
- `2026-5-5_日均报表.xls` -> `average_daily_report`

- [x] **Step 2: Run red tests**

```bash
python -m pytest backend/tests/test_legacy_data_profile_service.py -q
```

Expected before implementation: new classification tests fail.

- [x] **Step 3: Implement filename-based classifiers**

Keep existing classifiers unchanged and add narrow filename checks for the new families.

### Task 2: Support Recursive Directory Audit

**Files:**
- Modify: `backend/app/services/legacy_data_profile_service.py`
- Modify: `backend/tests/test_legacy_data_profile_service.py`

- [x] **Step 1: Add recursive profile test**

Create a temp directory with a dated subfolder and a workbook inside. Assert:
- default `profile_historical_directory(path)` remains shallow
- `profile_historical_directory(path, recursive=True)` includes nested files
- profiled items include `relative_path`

- [x] **Step 2: Implement recursive flag**

Add a `recursive: bool = False` parameter and use `Path.rglob("*")` only when requested.

### Task 3: Run Read-Only Audit on Real Folder

**Files:**
- Read only: `D:\鑫泰报表`
- Optional docs update: `docs/deploy/current-state.md`

- [x] **Step 1: Run profiler**

```bash
python - <<'PY'
from app.services.legacy_data_profile_service import profile_historical_directory
payload = profile_historical_directory(r"D:\鑫泰报表", recursive=True, max_sheets=2, max_rows=2)
print(payload["total_files"], payload["kind_counts"], payload["blocked_files"])
PY
```

- [x] **Step 2: Summarize audit result**

Record counts by kind, blocked file count, and representative source examples. Do not import data into the database yet.

### Task 4: Verify and Commit

- [x] **Step 1: Run targeted tests**

```bash
python -m pytest backend/tests/test_legacy_data_profile_service.py -q
```

- [x] **Step 2: Run backend regression if service behavior changes broadly**

```bash
python -m pytest backend/tests -q
```

- [x] **Step 3: Diff check**

```bash
git diff --check
```

- [x] **Step 4: Commit and push**

```bash
git add backend/app/services/legacy_data_profile_service.py backend/tests/test_legacy_data_profile_service.py docs/superpowers/plans/2026-05-06-xintai-report-source-audit.md
git commit -m "feat: 增强真实日报源文件审计"
git push origin main
```
