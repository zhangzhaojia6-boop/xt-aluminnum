# Deterministic Orchestration Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item B21 by proving `deterministic_orchestration_service.py` is now a referenced runtime helper with direct boundary tests.

**Architecture:** Keep the existing report-service integration unchanged. Add narrow service-level tests around deterministic scoring/status behavior, then update the cleanup audit from pending to resolved.

**Tech Stack:** Python, pytest, existing backend static documentation tests.

---

### Task 1: Prove The Audit Row Is Stale

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`
- Read: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Write the failing audit guard**

Add a static test that reads the audit file and asserts the pending B21 row no longer claims `deterministic_orchestration_service.py` has no references or no tests.

- [x] **Step 2: Run the guard to verify it fails**

Run:

```bash
cd backend
python -m pytest tests/test_quick_cloud_trial_docs_and_ops.py::test_cleanup_audit_marks_deterministic_orchestration_boundary_resolved -q
```

Expected: FAIL because the audit still contains the pending B21 row.

Result: historical red completed before implementation; current guard passes with `B21` removed and `R71` recorded.

### Task 2: Add Direct Service Coverage

**Files:**
- Create: `backend/tests/test_deterministic_orchestration_service.py`
- Read: `backend/app/services/deterministic_orchestration_service.py`

- [x] **Step 1: Add focused tests**

Cover:
- Healthy inputs produce `low` risk and healthy worker statuses.
- Missing reports, returned reports, exceptions, and missing delivery steps produce blocking bottlenecks and non-healthy worker statuses.
- Invalid numeric values are coerced safely instead of raising.

- [x] **Step 2: Run direct tests**

Run:

```bash
cd backend
python -m pytest tests/test_deterministic_orchestration_service.py -q
```

Expected: PASS.

Result: direct deterministic orchestration tests pass and cover healthy, blocked, and bad-input coercion cases.

### Task 3: Update The Audit Ledger

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B21 to resolved**

Add an `R71` row explaining that `deterministic_orchestration_service.py` is used by report runtime trace builders and now has direct tests.

- [x] **Step 2: Remove pending B21**

Delete the B21 row from "待处理问题清单".

- [x] **Step 3: Re-run the audit guard**

Run:

```bash
cd backend
python -m pytest tests/test_quick_cloud_trial_docs_and_ops.py::test_cleanup_audit_marks_deterministic_orchestration_boundary_resolved -q
```

Expected: PASS.

Result: audit guard passes; `R71` points to the service and direct tests.

### Task 4: Verification And Commit

**Files:**
- Verify all files touched in Tasks 1-3.

- [x] **Step 1: Run targeted backend tests**

```bash
cd backend
python -m pytest tests/test_deterministic_orchestration_service.py tests/test_quick_cloud_trial_docs_and_ops.py -q
```

- [x] **Step 2: Run cross-layer static contracts used by recent audit work**

```bash
cd backend
python -m pytest tests/test_reference_command_center_spec.py tests/test_mobile_entry_copy_consistency.py -q
```

- [x] **Step 3: Run full backend suite**

```bash
cd backend
python -m pytest tests -q
```

- [x] **Step 4: Review diff and commit**

```bash
git diff --check
git status --short
git diff -- docs/superpowers/plans/2026-05-06-deterministic-orchestration-boundary.md backend/tests/test_quick_cloud_trial_docs_and_ops.py backend/tests/test_deterministic_orchestration_service.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git add docs/superpowers/plans/2026-05-06-deterministic-orchestration-boundary.md backend/tests/test_quick_cloud_trial_docs_and_ops.py backend/tests/test_deterministic_orchestration_service.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 锁定确定性编排服务边界"
git push
```

Result:
- `python -m pytest backend/tests/test_deterministic_orchestration_service.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q` -> `33 passed, 1 deselected`
- `python -m pytest backend/tests/test_reference_command_center_spec.py backend/tests/test_mobile_entry_copy_consistency.py -m frontend_contract -q` -> `113 passed`
- `python -m pytest backend/tests -q --durations=10` -> `651 passed, 123 deselected`
- `git diff --check` -> pass
