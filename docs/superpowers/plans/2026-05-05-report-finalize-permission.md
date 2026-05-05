# Report Finalize Permission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item B14 by requiring explicit final-confirmation authority for `finalize_report`.

**Architecture:** Keep route-level report write gates from the previous round. Add a service-level finalization guard inside `backend/app/services/report/report_generation.py` so direct service calls and the route both enforce the same rule: manager/admin may finalize clean reports, only admin may force-finalize when quality blockers exist.

**Tech Stack:** Python service layer, pytest.

---

### Task 1: Add Red Tests For Finalize Authority

**Files:**
- Modify: `backend/tests/test_report_generation.py`

- [x] **Step 1: Write failing service tests**

Add tests that:
- build a reviewed report with no blockers;
- prove a reviewer without manager authority cannot finalize it;
- prove a manager can finalize it;
- keep the existing blocker override rule admin-only.

- [x] **Step 2: Run red tests**

Run: `python -m pytest backend/tests/test_report_generation.py -q`

Expected: FAIL because a reviewer currently finalizes a clean report.
Observed: FAIL, `test_finalize_report_rejects_reviewer_without_manager_authority` did not raise `ValueError`.

### Task 2: Enforce Service-Level Finalize Permissions

**Files:**
- Modify: `backend/app/services/report/report_generation.py`

- [x] **Step 1: Add permission helpers near `finalize_report`**

Use `build_scope_summary(operator)` to implement:
- `_can_finalize_report(operator)` -> admin or manager;
- `_is_admin(operator)` -> admin only.

- [x] **Step 2: Wire `finalize_report`**

Before mutating the entity, reject non-manager/non-admin operators with `ValueError('only manager or admin can finalize report')`. Keep the existing blocker force behavior, but use `_is_admin(operator)` for the force path.

- [x] **Step 3: Run focused tests**

Run: `python -m pytest backend/tests/test_report_generation.py backend/tests/test_report_route_permissions.py -q`

Expected: PASS.
Observed: PASS, `10 passed`.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B14 to fixed list**

Add `R31` describing the service-level finalization guard. Remove B14 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_report_generation.py backend/tests/test_report_route_permissions.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_report_generation.py backend/tests/test_report_route_permissions.py -q`: PASS, `10 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q`: PASS, `689 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review the diff for scope and security, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-report-finalize-permission.md backend/tests/test_report_generation.py backend/app/services/report/report_generation.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 限制日报最终确认权限"
```
