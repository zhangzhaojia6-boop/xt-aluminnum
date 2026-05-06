# Daily Production Mapping Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only gate that maps staged `daily_production_report` workshop rows to existing workshop and equipment master data before any formal `ShiftProductionData` writes.

**Architecture:** Keep the parser and import staging unchanged. Add a focused mapping service that reads `ImportBatch` / `ImportRow`, resolves only high-confidence workshop and equipment aliases, and returns row-level `ready`, `needs_equipment_mapping`, or `unresolved_workshop` statuses.

**Tech Stack:** Python dataclasses, SQLAlchemy ORM, pytest, existing `ImportBatch` / `ImportRow` / `Workshop` / `Equipment` models.

---

### Task 1: Add Mapping Preview Tests

**Files:**
- Create: `backend/tests/test_daily_production_mapping_service.py`

- [x] **Step 1: Write a failing preview test**

Create a SQLite test database with `ImportBatch`, `ImportRow`, `Workshop`, `Equipment`, and `User` tables. Insert one staged daily production row with labels from the real workbook:
- `铸锭 / None`
- `铸轧 / 铸二`
- `热轧 / 铣床`
- `冷轧 / 2050`
- `冷轧 / 1650`

Assert that high-confidence rows resolve to existing master data and `1650` stays unresolved.

Run:

```bash
python -m pytest backend/tests/test_daily_production_mapping_service.py -q
```

Expected: fail because `daily_production_mapping_service` does not exist.

### Task 2: Implement the Read-Only Mapping Service

**Files:**
- Create: `backend/app/services/daily_production_mapping_service.py`
- Modify: `backend/tests/test_daily_production_mapping_service.py`

- [x] **Step 1: Add dataclasses and aliases**

Implement conservative aliases:
- `铸锭` -> `ZD`
- `铸轧 / 铸二` -> `ZR2`
- `铸轧 / 铸三` -> `ZR3`
- `热轧 / 铣床` -> `RZ` + `RZ-XC`
- `热轧 / 热轧` -> `RZ` + `RZ-ZJ`
- `冷轧 / 2050` -> `LZ2050` + `LZ2050-1`
- `园区剪切` -> `JQ`

Do not infer ambiguous rows such as `冷轧 / 1650`, `冷轧 / 1850`, `精整 / 剪子`, `精整 / 纵剪`, or `拉矫 / 分切`.

- [x] **Step 2: Build preview from import rows**

Implement `build_daily_production_mapping_preview(db, batch_id=None)`:
- default to the latest `ImportBatch.import_type == "daily_production_report"`;
- read each row's `mapped_data["workshop_rows"]`;
- preserve ton metrics from the import row;
- attach workshop/equipment ids, codes, and names when matched;
- count `ready_rows`, `needs_equipment_mapping_rows`, and `unresolved_rows`;
- do not import or touch `ShiftProductionData`.

- [x] **Step 3: Verify target tests**

Run:

```bash
python -m pytest backend/tests/test_daily_production_mapping_service.py -q
```

Expected: all tests pass.

### Task 3: Production Mapping Evidence

**Files:**
- Modify: `docs/deploy/current-state.md`
- Modify: `PLANS.md`
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Run production read-only preview**

Run the mapping service against production `ImportBatch id=1`. Record:
- number of total staged rows;
- number of ready rows;
- unresolved labels;
- rows needing equipment mapping;
- proof that no formal production rows were written.

- [x] **Step 2: Update docs and verification assertions**

Add the production preview result to `docs/deploy/current-state.md` and `PLANS.md`. Add doc assertions so the evidence does not drift silently.

- [x] **Step 3: Final verification**

Run:

```bash
python -m pytest backend/tests/test_daily_production_mapping_service.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
python -m pytest backend/tests -q
git diff --check
git status --short --branch
```

Expected: all tests pass, whitespace check is clean except known CRLF warnings, and only intended files changed.

Production note: preview ran on `ImportBatch id=1` / `batch_no=IMP-20260506130735-d4f557`. Result: `total_rows=16`, `ready_rows=7`, `needs_equipment_mapping_rows=0`, `unresolved_rows=9`, unresolved labels `冷轧/1650|冷轧/1850|精整/剪子|精整/纵剪|拉矫/拉矫|拉矫/分切|退火炉/拉矫|在线退火/新厂北线|在线退火/园区北线`, and `shift_rows_delta=0`.
