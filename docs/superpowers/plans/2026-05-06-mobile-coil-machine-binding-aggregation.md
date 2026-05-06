# Mobile Coil Machine Binding Aggregation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure mobile coil entries written by machine-bound users flow into management views under the real machine line instead of only the unbound workshop/shift bucket.

**Architecture:** Reuse the existing `equipment.bound_user_id` source of truth through `get_bound_machine_for_user()`. On coil entry creation, bind `WorkOrderEntry.machine_id` and workshop from the bound machine; aggregate `mobile_coil_agg` rows by `business_date + shift + workshop + equipment_id` so `factory_command_service` and `realtime_service` can render machine-line data without guessing.

**Tech Stack:** Python, SQLAlchemy, pytest, existing mobile report service and factory command/realtime aggregation services.

---

### Task 1: Lock Bound Machine Write Behavior

**Files:**
- Modify: `backend/tests/test_coil_entry_auto_calc.py`
- Modify: `backend/app/services/mobile_report/summary.py`

- [x] **Step 1: Write failing test for bound user coil entry**

Add a test that seeds:
- one active `Equipment` with `bound_user_id=current_user.id`
- one mobile user in the same workshop
- one coil entry payload without `machine_id`

Assert after `create_coil_entry()`:
- `WorkOrderEntry.machine_id == equipment.id`
- `ShiftProductionData.equipment_id == equipment.id`
- `ShiftProductionData.data_source == 'mobile_coil_agg'`
- raw weights remain stored as kg

- [x] **Step 2: Run red test**

```bash
python -m pytest backend/tests/test_coil_entry_auto_calc.py::test_coil_entry_uses_bound_machine_for_management_aggregation -q
```

Expected before implementation: fail because the created entry/aggregate has no machine binding.

- [x] **Step 3: Implement bound machine lookup in `create_coil_entry()`**

Use `get_bound_machine_for_user(db, user_id=current_user.id)` inside `create_coil_entry()`:
- if found, set `machine_id = bound_machine.id`
- if found, set `workshop_id = bound_machine.workshop_id`
- otherwise keep the existing workshop-scope fallback

Pass `machine_id` into `_aggregate_coil_to_shift()`.

- [x] **Step 4: Verify green**

```bash
python -m pytest backend/tests/test_coil_entry_auto_calc.py::test_coil_entry_uses_bound_machine_for_management_aggregation -q
```

Expected: pass.

### Task 2: Prevent Cross-Machine Aggregate Collapse

**Files:**
- Modify: `backend/tests/test_coil_entry_auto_calc.py`
- Modify: `backend/app/services/mobile_report/summary.py`

- [x] **Step 1: Write failing test for two bound machines in one workshop/shift**

Seed two active machines, each bound to a different mobile user. Submit one coil entry per user on the same business date and shift. Assert:
- there are two `ShiftProductionData` rows
- each row keeps its own `equipment_id`
- each row keeps its own output kg total

- [x] **Step 2: Run red test**

```bash
python -m pytest backend/tests/test_coil_entry_auto_calc.py::test_coil_entry_aggregates_by_bound_machine_not_only_workshop_shift -q
```

Expected before implementation: fail because aggregation currently finds the first non-voided workshop/shift row and collapses machine totals.

- [x] **Step 3: Implement equipment-aware aggregate query**

Update `_aggregate_coil_to_shift()`:
- accept `machine_id: int | None`
- filter `WorkOrderEntry.machine_id == machine_id` or `is_(None)`
- match only existing `ShiftProductionData.data_source == 'mobile_coil_agg'`
- match `ShiftProductionData.equipment_id == machine_id` or `is_(None)`
- set `spd.equipment_id = machine_id` on update and create

- [x] **Step 4: Verify green**

```bash
python -m pytest backend/tests/test_coil_entry_auto_calc.py -q
```

Expected: pass.

### Task 3: Regression and Documentation

**Files:**
- Modify: `docs/deploy/current-state.md`

- [x] **Step 1: Run targeted backend tests**

```bash
python -m pytest backend/tests/test_coil_entry_auto_calc.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q
```

- [x] **Step 2: Run full backend suite**

```bash
python -m pytest backend/tests -q
```

- [x] **Step 3: Update current state evidence**

Add a concise note that future mobile coil entries from machine-bound users now write `equipment_id` into `mobile_coil_agg` aggregate rows. Explicitly state no production data backfill was performed.

- [x] **Step 4: Diff check, commit, and push**

```bash
git diff --check
git add backend/app/services/mobile_report/summary.py backend/tests/test_coil_entry_auto_calc.py docs/deploy/current-state.md docs/superpowers/plans/2026-05-06-mobile-coil-machine-binding-aggregation.md
git commit -m "fix: 绑定卷级填报机列聚合"
git push origin main
```
