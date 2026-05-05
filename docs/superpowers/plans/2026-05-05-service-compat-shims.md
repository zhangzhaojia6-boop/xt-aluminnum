# Service Compatibility Shims Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit items B19 and B20 by locking compatibility behavior for `work_order_service.py` and `report_service.py`.

**Architecture:** Keep the thin shim files unchanged. Add focused tests that prove old import paths resolve to the new package modules and monkeypatching through old service paths still propagates to the package submodules used by existing tests and routes.

**Tech Stack:** pytest, Python import system.

---

### Task 1: Cover Report Service Shim

**Files:**
- Create: `backend/tests/test_service_compat_shims.py`

- [x] **Step 1: Add report import identity test**

Assert `from app.services import report_service`, `import app.services.report_service`, and `from app.services import report` all refer to the same module object.

- [x] **Step 2: Add report monkeypatch propagation test**

Monkeypatch `report_service.build_delivery_status` and assert `app.services.report.dashboard_builder.build_delivery_status` sees the patched object.

### Task 2: Cover Work Order Service Shim

**Files:**
- Modify: `backend/tests/test_service_compat_shims.py`

- [x] **Step 1: Add work-order import identity test**

Assert `from app.services import work_order_service`, `import app.services.work_order_service`, and `from app.services import work_order` all refer to the same module object.

- [x] **Step 2: Add work-order monkeypatch propagation test**

Monkeypatch `work_order_service.submit_entry` and assert `app.services.work_order.entry.submit_entry` sees the patched object.

### Task 3: Close Audit Items And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B19 and B20 to fixed list**

Add `R37` for work-order shim coverage and `R38` for report shim coverage. Remove B19 and B20 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_service_compat_shims.py -q`
- `python -m pytest backend/tests/test_report_route_permissions.py backend/tests/test_work_order_routes.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_service_compat_shims.py -q`: PASS, `4 passed`.
- `python -m pytest backend/tests/test_report_route_permissions.py backend/tests/test_work_order_routes.py -q`: PASS, `24 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q`: PASS, `711 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope and maintainability, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-service-compat-shims.md backend/tests/test_service_compat_shims.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖服务兼容壳"
```
