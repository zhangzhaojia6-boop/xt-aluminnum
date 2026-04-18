# Workshop Template Mobile Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add workshop-specific form templates and a single mobile entry component that dynamically renders the right work-order form and tempo behavior per workshop.

**Architecture:** Add a central workshop-template config plus workshop-type resolution on the backend, expose a new `/templates/{workshop_type}` endpoint, extend work-order entry payloads for workshop-specific extra fields, and replace the fixed mobile form with a dynamic Vue component that uses current-shift context, template metadata, and existing work-order APIs.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic 2, Vue 3, Vite, Element Plus, Pinia, Axios

---

### Task 1: Red Tests For Template Config And Route Surface

**Files:**
- Create: `backend/tests/test_workshop_templates.py`
- Modify: `backend/tests/test_work_order_routes.py`

- [ ] Add failing tests for workshop type resolution, role-filtered template fields, and the new template route registration.
- [ ] Run focused pytest and confirm the failures are from missing template modules or route behavior.

### Task 2: Backend Template Config And Resolution

**Files:**
- Create: `backend/app/core/workshop_templates.py`
- Create: `backend/app/schemas/templates.py`
- Create: `backend/app/routers/templates.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `backend/app/main.py`

- [ ] Add workshop template definitions, field metadata, and workshop-type resolution from workshop code/name.
- [ ] Filter template fields by current role before returning editable sections.
- [ ] Add `GET /templates/{workshop_type}` and expose the caller’s effective workshop type where needed.

### Task 3: Extend Work-Order Entry Payloads For Template Extras

**Files:**
- Modify: `backend/app/models/production.py`
- Create: `backend/alembic/versions/0012_work_order_template_payloads.py`
- Modify: `backend/app/core/field_permissions.py`
- Modify: `backend/app/schemas/work_orders.py`
- Modify: `backend/app/services/work_order_service.py`

- [ ] Add JSON payload support for workshop-specific extra fields and QC chemical fields.
- [ ] Allow shift leaders to write the energy fields needed by the new mobile templates.
- [ ] Make work-order entry create/update/serialize handle standard fields, header fields like `alloy_grade`, and extra template payloads cleanly.

### Task 4: Dynamic Mobile Form

**Files:**
- Create: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/api/mobile.js`
- Modify: `frontend/src/router/index.js`

- [ ] Fetch current shift context, derive/fetch workshop template, and render fields in template order.
- [ ] Implement slow-tempo completion toggle, history panel, and output-weight requirement switching.
- [ ] Implement fast-tempo submitted counter, “继续下一卷”, and batch paste mode.
- [ ] Keep tracking-card entry at the top and reuse existing work-order endpoints for lookup/create/update/submit.

### Task 5: Verification

**Files:**
- Verify only

- [ ] Run focused backend tests.
- [ ] Run the full backend suite.
- [ ] Run `npm run build` in `frontend`.
- [ ] Fix regressions until all checks pass.
