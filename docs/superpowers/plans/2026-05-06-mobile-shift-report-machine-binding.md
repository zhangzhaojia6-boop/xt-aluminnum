# Mobile Shift Report Machine Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure normal mobile shift report submissions write the bound machine into management-side `ShiftProductionData.equipment_id` when the bound machine belongs to the submitted workshop.

**Architecture:** Reuse the existing equipment binding source `get_bound_machine_for_user()` already used by coil-level submissions. Keep the shift report workshop/team key unchanged, and only add a same-workshop machine reference to the linked production row.

**Tech Stack:** FastAPI service layer, SQLAlchemy ORM, pytest with SQLite.

---

### Task 1: Lock the Missing Machine Binding with TDD

**Files:**
- Modify: `backend/tests/test_mobile_shift_report_machine_binding.py`
- Modify: `backend/app/services/mobile_report/lifecycle.py`

- [x] **Step 1: Write the failing test**

Add focused SQLite tests that seed `Workshop`, `Team`, `ShiftConfig`, `User`, `Equipment(bound_user_id=user.id)`, call `_sync_to_shift_production()`, and assert:
- same-workshop binding writes the linked `ShiftProductionData.equipment_id`;
- other-workshop binding is ignored;
- existing machine-level aggregate rows are not overwritten or duplicated by normal shift reports.

- [x] **Step 2: Verify RED**

Run:

```bash
python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py -q
```

Expected: one failure showing `equipment_id` is `None` before the fix.

- [x] **Step 3: Implement minimal fix**

In `_sync_to_shift_production()`, resolve the bound machine from `report.leader_user_id` or `report.owner_user_id`. Set `entity.equipment_id` only when the machine exists, `machine.workshop_id == workshop.id`, and no other non-voided production row already owns the same date/shift/workshop/machine key; otherwise keep it `None`.

- [x] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py -q
```

Expected: all tests pass.

- [x] **Step 5: Regression checks**

Run:

```bash
python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_coil_entry_auto_calc.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q
python -m pytest backend/tests -q
```

Expected: targeted tests and full backend suite pass.

- [x] **Step 6: Review and commit**

Review `git diff`, fix any issue found, then commit only the plan, test, and lifecycle changes.
