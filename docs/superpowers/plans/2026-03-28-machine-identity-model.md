# Machine Identity Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement one-machine-one-account identity, machine QR login, per-machine shift/custom-field configuration, and machine-scoped mobile reporting.

**Architecture:** Extend `Equipment` and `User` to carry machine runtime identity, centralize creation/reset/toggle logic in a dedicated equipment service, route all machine-bound auth and mobile scope through the existing auth/mobile service path, and add a new master-data equipment UI plus machine wizard in the frontend.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 15, Vue 3, Vite, Element Plus, Pinia, Axios, pytest

---

### Task 1: Backend Red Tests

**Files:**
- Create: `backend/tests/test_equipment_identity_service.py`
- Create: `backend/tests/test_equipment_identity_routes.py`
- Create: `backend/tests/test_qr_login.py`
- Modify: `backend/tests/test_mobile_bootstrap.py`
- Modify: `backend/tests/test_mobile_report_write_guards.py`
- Modify: `backend/tests/test_real_master_data.py`

- [ ] Write failing tests for equipment model runtime fields, machine account creation, PIN reset, status toggle, QR login, machine-bound bootstrap, and hard machine-scope rejection.
- [ ] Add failing tests for revised workshop/equipment seed data including `ZD`, `ZR3`, and `LZ3`.
- [ ] Run focused pytest commands and confirm failures are caused by missing behavior, not test mistakes.

### Task 2: Persistence Model and Migration

**Files:**
- Modify: `backend/app/models/master.py`
- Modify: `backend/app/models/system.py`
- Create: `backend/alembic/versions/0017_machine_identity_model.py`

- [ ] Add `Equipment` runtime fields: `operational_status`, `shift_mode`, `assigned_shift_ids`, `custom_fields`, `qr_code`, `bound_user_id`, `sort_order`.
- [ ] Add `Equipment.bound_user` relationship.
- [ ] Add `User.pin_code`.
- [ ] Create Alembic migration for every missing column and constraint.
- [ ] Run the new migration test or targeted schema checks.

### Task 3: Backend Schemas

**Files:**
- Modify: `backend/app/schemas/master.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/schemas/mobile.py`

- [ ] Add machine create/reset/toggle request and response schemas.
- [ ] Extend equipment output schema with runtime fields and bound account metadata.
- [ ] Extend mobile bootstrap/current-shift schemas with `machine_id`, `machine_name`, `machine_code`, `is_machine_bound`, and merged custom field payload where needed.
- [ ] Extend auth response schema for QR login machine context if the current response shape needs it.

### Task 4: Equipment Service

**Files:**
- Create: `backend/app/services/equipment_service.py`
- Modify: `backend/app/services/__init__.py`

- [ ] Implement helper functions for username normalization, QR generation, 6-digit PIN generation, and bound-user lookup.
- [ ] Implement `create_machine_with_account(...)`.
- [ ] Implement `reset_machine_pin(...)`.
- [ ] Implement `toggle_machine_status(...)`.
- [ ] Implement any supporting update helpers for shift mode, assigned shifts, and custom fields.
- [ ] Reuse audit logging for machine/account lifecycle changes.

### Task 5: Auth and QR Login

**Files:**
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/app/services/audit_service.py` only if extra event shape is needed

- [ ] Add `POST /auth/qr-login`.
- [ ] Return correct 404/403 responses for missing, unbound, or stopped machines.
- [ ] Generate JWT for the bound machine account on successful QR login.
- [ ] Add audit records for QR login and PIN reset flows.
- [ ] Verify old PIN stops working immediately after reset.

### Task 6: Machine Scope Enforcement

**Files:**
- Modify: `backend/app/core/permissions.py`
- Modify: `backend/app/services/mobile_report_service.py`
- Modify: `backend/app/routers/mobile.py`

- [ ] Add `assert_machine_scope(current_user, target_machine_id)`.
- [ ] Update mobile bootstrap/current-shift resolution to detect `Equipment.bound_user_id == current_user.id`.
- [ ] Filter available shifts by `assigned_shift_ids` when present.
- [ ] Reject writes, submits, and photo uploads when the target machine does not match the bound machine.
- [ ] Ensure stopped/maintenance machines cannot continue operating through cached user state.

### Task 7: Real Master Data Seed Revision

**Files:**
- Modify: `backend/app/services/real_master_data.py`
- Modify: `backend/scripts/init_real_master_data.py`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.prod.yml`

- [ ] Revise workshop seed list to the new 11-workshop set.
- [ ] Add revised equipment seed data for `ZD`, `ZR2`, `ZR3`, `RZ`, `LZ2050`, `LZ1450`, and `LZ3`.
- [ ] Keep `JZ`, `JZ2`, and `JQ` runtime data aligned with current real seed behavior.
- [ ] Seed default `operational_status`, `shift_mode`, `assigned_shift_ids`, and `custom_fields`.
- [ ] Preserve idempotency and deactivate legacy sample rows.

### Task 8: Master Equipment APIs

**Files:**
- Modify: `backend/app/routers/master.py`
- Modify: `backend/app/services/master_service.py` if shared listing helpers are useful

- [ ] Add `POST /master/equipment/create-with-account`.
- [ ] Add `POST /master/equipment/{id}/reset-pin`.
- [ ] Add `POST /master/equipment/{id}/toggle-status`.
- [ ] Add `GET /master/equipment/{id}` if not already available.
- [ ] Add update support for runtime fields and machine custom fields.
- [ ] Restrict the new write APIs to admin only.

### Task 9: Frontend API Layer

**Files:**
- Modify: `frontend/src/api/master.js`
- Modify: `frontend/src/api/auth.js`
- Modify: `frontend/src/api/mobile.js`
- Modify: `frontend/src/stores/auth.js`

- [ ] Add equipment runtime CRUD helpers, machine creation, PIN reset, status toggle, and QR generation helpers.
- [ ] Add QR login API helper.
- [ ] Store machine context returned from QR login.
- [ ] Keep existing mobile APIs backward compatible for non-machine users.

### Task 10: Equipment Management UI

**Files:**
- Create: `frontend/src/views/master/Equipment.vue`
- Create: `frontend/src/views/master/MachineWizard.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/Layout.vue`
- Modify: `frontend/src/styles.css`

- [ ] Add the equipment list page with runtime columns and action buttons.
- [ ] Build the multi-step machine wizard with workshop, machine type, shift mode, custom-field builder, and account summary steps.
- [ ] Add dialogs for custom fields, QR card preview, and one-time new PIN display.
- [ ] Add route and sidebar entry for equipment management.
- [ ] Verify the printable machine card layout works in browser print mode.

### Task 11: Mobile QR and Machine-Bound UX

**Files:**
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `frontend/src/composables/useLocalDraft.js` only if machine keying needs adjustment
- Modify: `frontend/src/router/index.js`

- [ ] Detect `?machine=<qr_code>` and call QR login automatically.
- [ ] Redirect successful QR login into `/mobile`.
- [ ] For machine-bound users, hide machine selection and show the fixed machine header.
- [ ] Merge workshop template fields and `machine.custom_fields` into separate sections in the dynamic form.
- [ ] Save machine custom-field values into the JSON payload expected by backend.

### Task 12: Dashboard and Shift Presentation

**Files:**
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
- Modify: `backend/app/services/realtime_service.py` or relevant aggregation service if shift applicability affects live totals

- [ ] Ensure two-shift machines only expose applicable shifts.
- [ ] Grey out or omit non-applicable shift cells according to the current dashboard layout.
- [ ] Prevent "missing report" calculations from counting unassigned shifts as pending.

### Task 13: Verification

**Files:**
- Verify only

- [ ] Run focused backend pytest targets for machine identity, QR login, mobile scope, and revised master data.
- [ ] Run full backend test suite.
- [ ] Run `npm run build` in `frontend`.
- [ ] Rebuild the running containers and verify:
  - `/api/v1/master/workshops`
  - `/api/v1/master/equipment?workshop_id=<id>`
  - machine QR login
  - machine-bound mobile bootstrap

### Task 14: Closeout

**Files:**
- Verify only

- [ ] Summarize the final machine identity flow, including QR login behavior and admin PIN reset behavior.
- [ ] Call out any unresolved follow-up items, especially around QR security tradeoffs and future dashboard refinements.
