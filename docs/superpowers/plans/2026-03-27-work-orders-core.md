# Work Orders Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend foundation for tracking-card work orders with role-owned fields, workshop-local entry visibility, role-based field locking, audited amendments, and computed previous-stage output.

**Architecture:** Keep the current thin-router/service-layer pattern. Add the new persistence model in `production.py`, centralize field ownership and lock rules in `core/`, expose work-order and amendment endpoints in new routers, and serialize responses through explicit schema and field-filter helpers so sensitive values can be nulled safely.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 15, Pydantic 2, pytest

---

### Task 1: Foundation Tests

**Files:**
- Create: `backend/tests/test_work_order_permissions.py`
- Create: `backend/tests/test_work_order_routes.py`
- Create: `backend/tests/test_work_order_service.py`

- [ ] Write failing tests for `FIELD_OWNERSHIP`, read/write filtering, workshop-local entry visibility, submit locking, amendment approval, and previous-stage output computation.
- [ ] Run focused pytest commands and confirm the new tests fail for the expected missing-module or missing-behavior reasons.

### Task 2: Core Permission Helpers

**Files:**
- Create: `backend/app/core/field_permissions.py`
- Create: `backend/app/core/field_lock.py`
- Modify: `backend/app/core/scope.py`

- [ ] Implement field ownership registry and helper functions.
- [ ] Add work-order scope helpers for global header access, workshop-local entry access, and contracts-specific behavior.
- [ ] Add field-lock helpers that decide whether a field is editable, which fields lock on submit, and how locked fields map into amendments.

### Task 3: Persistence Layer

**Files:**
- Modify: `backend/app/models/production.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0011_work_orders_core.py`

- [ ] Add SQLAlchemy models for `WorkOrder`, `WorkOrderEntry`, and `FieldAmendment`.
- [ ] Add indexes, foreign keys, and JSON column for `previous_stage_output`.
- [ ] Add an Alembic revision that creates the new tables and is consistent with the repo's defensive migration style.

### Task 4: Service Layer

**Files:**
- Create: `backend/app/services/work_order_service.py`

- [ ] Implement tracking-card route parsing, work-order creation, header lookup, entry listing, entry create/update/submit, previous-stage output recomputation, and amendment request/approval logic.
- [ ] Reuse `audit_service` so submissions, approvals, and applied amendments are recorded.
- [ ] Keep serialization explicit so unreadable fields are returned as `null`.

### Task 5: API Schemas and Routers

**Files:**
- Create: `backend/app/schemas/work_orders.py`
- Modify: `backend/app/schemas/__init__.py`
- Create: `backend/app/routers/work_orders.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `backend/app/main.py`

- [ ] Add request and response schemas for work orders, entries, previous-stage snapshot, and amendments.
- [ ] Add the work-order router endpoints required by the acceptance criteria.
- [ ] Register the router in app startup and export the schema module consistently with current patterns.

### Task 6: Verification

**Files:**
- Verify only

- [ ] Run the focused backend pytest targets for the new module.
- [ ] Run a broader smoke set if the focused tests pass.
- [ ] Fix regressions and repeat until green.

### Task 7: Closeout

**Files:**
- Verify only

- [ ] Summarize what changed, note any assumptions, and call out anything not yet covered by tests or missing due to repo constraints.
