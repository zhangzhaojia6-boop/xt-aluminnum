# Mobile Coil Draft Aggregation Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent draft historical coil rows from entering management live production totals while keeping submitted coil entries visible in `mobile_coil_agg`.

**Architecture:** Treat `/mobile/coil-entry` as an explicit submit action by storing new coil entries as `submitted`. Rebuild `mobile_coil_agg` only from submitted or later workflow states, so imported or draft rows remain visible in the operator list but do not become management facts.

**Tech Stack:** Python, SQLAlchemy, pytest.

---

### Task 1: Guard Coil Aggregation By Entry Status

**Files:**
- Modify: `backend/app/services/mobile_report/summary.py`
- Modify: `backend/tests/test_coil_entry_auto_calc.py`

- [x] **Step 1: Write failing tests**

Add tests proving:
- `create_coil_entry()` persists submitted coil entries as `entry_status='submitted'`;
- `_aggregate_coil_to_shift()` ignores draft coil rows when producing `mobile_coil_agg`.

- [x] **Step 2: Verify RED**

Run:

```bash
python -m pytest backend/tests/test_coil_entry_auto_calc.py -q
```

Expected: fail until `create_coil_entry()` and `_aggregate_coil_to_shift()` enforce the submitted-only aggregation contract.

Execution note: RED captured with 3 failures: new coil entries persisted as `draft`, and a manually seeded draft row still created `mobile_coil_agg`.

- [x] **Step 3: Implement minimal service change**

Set new coil entries to `submitted` and add `WorkOrderEntry.entry_status.in_(('submitted', 'verified', 'approved'))` to the aggregate query.

Execution note: `_aggregate_coil_to_shift()` also voids an existing active `mobile_coil_agg` row when a recalculation finds no submitted/verified/approved source entries, preventing stale draft-only aggregates from staying visible in management totals.

- [x] **Step 4: Verify GREEN and nearby management paths**

Run:

```bash
python -m pytest backend/tests/test_coil_entry_auto_calc.py backend/tests/test_realtime_service.py backend/tests/test_factory_command_service.py backend/tests/test_workshop_reporting_status.py -q
python -m pytest backend/tests -q
git diff --check
```

Expected: all tests pass and no whitespace errors.

Execution note: `python -m pytest backend/tests/test_coil_entry_auto_calc.py backend/tests/test_realtime_service.py backend/tests/test_factory_command_service.py backend/tests/test_workshop_reporting_status.py -q` returned `32 passed`.

- [x] **Step 5: Production data dry-run**

Run a read-only production probe listing `mobile_coil_agg` rows whose source coil entries are all draft. Do not void or rewrite production rows without an explicit reviewed list.

Execution note: production read-only probe found `mobile_coil_agg_rows=28`, `draft_only_aggregate_rows=28`, `draft_only_output_weight_total=1153110.0`. No production rows were voided or rewritten in this dry-run.
