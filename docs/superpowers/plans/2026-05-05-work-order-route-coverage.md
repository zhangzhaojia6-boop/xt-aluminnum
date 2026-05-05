# Work Order Route Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item B17 by covering the main work-order route flow with behavior tests.

**Architecture:** Keep the existing router and service compatibility shim intact. Extend `backend/tests/test_work_order_routes.py` with route-level tests that monkeypatch `app.routers.work_orders.work_order_service.*`, assert parsed payload/operator/request metadata, and validate response contracts.

**Tech Stack:** FastAPI TestClient, pytest.

---

### Task 1: Cover Work Order Header Routes

**Files:**
- Modify: `backend/tests/test_work_order_routes.py`

- [x] **Step 1: Add create work order route test**

Mock `work_order_service.create_work_order`, call `POST /api/v1/work-orders/`, and assert the service receives the request payload, current user, IP address, and user agent.

- [x] **Step 2: Add detail route test**

Mock `work_order_service.get_work_order_by_tracking_card`, call `GET /api/v1/work-orders/RA240001`, and assert the tracking card number and current user are forwarded.

- [x] **Step 3: Add list route test**

Mock `work_order_service.list_work_orders`, call `GET /api/v1/work-orders/` with `workshop_id`, `business_date`, and `status`, and assert parsed values are forwarded.

### Task 2: Cover Entry Update And Amendment Request

**Files:**
- Modify: `backend/tests/test_work_order_routes.py`

- [x] **Step 1: Add entry update route test**

Mock `work_order_service.update_entry`, call `PATCH /api/v1/work-orders/entries/{entry_id}`, and assert the route forwards `override_reason` separately while keeping it in the payload produced by the existing schema dump.

- [x] **Step 2: Add amendment create route test**

Mock `work_order_service.request_amendment`, call `POST /api/v1/amendments/`, and assert payload and operator forwarding.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B17 to fixed list**

Add `R35` describing work-order route behavior coverage. Remove B17 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_work_order_routes.py -q`
- `python -m pytest backend/tests/test_work_order_service.py backend/tests/test_work_order_write_guards.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_work_order_routes.py -q`: PASS, `12 passed`.
- `python -m pytest backend/tests/test_work_order_service.py backend/tests/test_work_order_write_guards.py -q`: PASS, `21 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q`: PASS, `706 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope and maintainability, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-work-order-route-coverage.md backend/tests/test_work_order_routes.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖工单主链路路由"
```
