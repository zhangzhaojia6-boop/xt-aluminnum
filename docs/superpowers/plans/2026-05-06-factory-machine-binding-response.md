# Factory Machine Binding Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure factory machine-line API responses preserve the service-level machine binding status used by management screens.

**Architecture:** Keep the existing `factory_command_service.list_machine_lines()` output shape. Add the missing response-model field so FastAPI serialization does not drop `machine_binding_status`.

**Tech Stack:** FastAPI, Pydantic, pytest.

---

### Task 1: Preserve Machine Binding Status

**Files:**
- Modify: `backend/tests/test_factory_command_routes.py`
- Modify: `backend/app/schemas/factory_command.py`

- [x] **Step 1: Write the failing route contract test**

Add `machine_binding_status='unbound'` to the machine-line route stub and assert the JSON response keeps the field.

- [x] **Step 2: Run the red test**

Run:

```bash
python -m pytest backend/tests/test_factory_command_routes.py::test_factory_command_routes_are_registered -q
```

Expected: fail before schema change because FastAPI response serialization drops the field.

- [x] **Step 3: Add the schema field**

Add `machine_binding_status: str = 'bound'` to `FactoryMachineLineOut`.

- [x] **Step 4: Run verification**

Run:

```bash
python -m pytest backend/tests/test_factory_command_routes.py backend/tests/test_factory_command_service.py -q
git diff --check
```
