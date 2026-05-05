# Work Order Idempotency Header Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item B18 by covering invalid `X-Idempotency-Key` behavior on work-order entry creation.

**Architecture:** Keep the existing `_normalize_idempotency_key` route helper unchanged unless the test exposes a defect. Add a route-level test that proves invalid UUID values return 400 before calling `work_order_service.add_entry`.

**Tech Stack:** FastAPI TestClient, pytest.

---

### Task 1: Cover Invalid Idempotency Header

**Files:**
- Modify: `backend/tests/test_work_order_routes.py`

- [x] **Step 1: Add invalid header test**

Monkeypatch `work_order_service.add_entry` to raise if called, send `POST /api/v1/work-orders/{id}/entries` with `X-Idempotency-Key: not-a-uuid`, and assert:
- status code is 400;
- response detail is `X-Idempotency-Key must be a UUID`;
- service was not called.

- [x] **Step 2: Run focused test**

Run: `python -m pytest backend/tests/test_work_order_routes.py -q`

Expected: PASS if the existing route helper already handles invalid UUIDs correctly.
Observed: PASS, `13 passed`.

### Task 2: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B18 to fixed list**

Add `R36` describing invalid idempotency header coverage. Remove B18 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_work_order_routes.py -q`
- `python -m pytest backend/tests/test_work_order_service.py backend/tests/test_work_order_write_guards.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_work_order_routes.py -q`: PASS, `13 passed`.
- `python -m pytest backend/tests/test_work_order_service.py backend/tests/test_work_order_write_guards.py -q`: PASS, `21 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q`: PASS, `707 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope and maintainability, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-work-order-idempotency-header.md backend/tests/test_work_order_routes.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖工单幂等头校验"
```
