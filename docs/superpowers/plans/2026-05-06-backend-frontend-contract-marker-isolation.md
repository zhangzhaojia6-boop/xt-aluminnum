# Backend Frontend Contract Marker Isolation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item B01 by isolating backend pytest from tests that directly assert frontend source text, while preserving those frontend contract checks as an explicitly runnable suite.

**Architecture:** Keep the historical static contract tests in place, but mark them `frontend_contract` and configure backend pytest's default run to exclude that marker. Add a backend guard that requires the marker configuration and audit closure, so future frontend source assertions do not silently re-enter the default backend suite.

**MES and Rule Context:** This is a test-boundary cleanup only. It does not change MES adapters, factory data fields, machine-line granularity, owner rules, or UI behavior.

**Tech Stack:** pytest markers, existing backend static guard tests, Markdown audit ledger.

---

### Task 1: Add Red Boundary Guard

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`
- Create: `docs/superpowers/plans/2026-05-06-backend-frontend-contract-marker-isolation.md`

- [x] **Step 1: Add marker isolation guard**

Assert:
- `backend/pytest.ini` registers `frontend_contract`
- default pytest options exclude `not frontend_contract`
- `test_mobile_entry_copy_consistency.py`, `test_reference_command_center_spec.py`, and `test_frontend_refactor_blueprint.py` use `pytestmark = pytest.mark.frontend_contract`
- `test_rebranding.py` marks only `test_user_facing_brand_strings_are_updated`
- the S10 helper static guard is marked `frontend_contract`
- audit has no `| B01 |` and includes `| R77 |`

- [x] **Step 2: Run the red guard**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_frontend_source_contract_tests_are_marker_isolated_from_backend_suite -q
```

Expected before implementation: FAIL because the marker config and R77 audit row do not exist.

Result: historical red completed before isolation; current guard passes and confirms marker config, marked contract tests, no pending `B01`, and resolved `R77`.

### Task 2: Apply Marker Isolation

**Files:**
- Modify: `backend/pytest.ini`
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`
- Modify: `backend/tests/test_reference_command_center_spec.py`
- Modify: `backend/tests/test_frontend_refactor_blueprint.py`
- Modify: `backend/tests/test_rebranding.py`
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Configure pytest marker**

Add `addopts = -m "not frontend_contract"` and register `frontend_contract`.

- [x] **Step 2: Mark frontend source contract tests**

Apply file-level `pytestmark` to the three frontend contract files. Mark only the user-facing frontend branding assertion in `test_rebranding.py`. Mark the S10 helper static guard in quick cloud docs.

Result: `backend/pytest.ini` excludes `frontend_contract` by default and registers the marker; `test_mobile_entry_copy_consistency.py`, `test_reference_command_center_spec.py`, and `test_frontend_refactor_blueprint.py` use file-level marker; `test_rebranding.py` marks only the user-facing branding assertion; the S10 helper guard is marked `frontend_contract`.

### Task 3: Audit And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B01 to resolved**

Add `R77` for frontend contract marker isolation and remove pending `B01`.

- [x] **Step 2: Run targeted checks**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_frontend_source_contract_tests_are_marker_isolated_from_backend_suite -q
python -m pytest backend/tests -m frontend_contract -q
python -m pytest backend/tests -q
```

Expected: marker guard passes, frontend contract suite passes separately, default backend suite passes without frontend contract tests.

Result:
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_frontend_source_contract_tests_are_marker_isolated_from_backend_suite -q` -> `1 passed`
- `python -m pytest backend/tests -m frontend_contract -q` -> `123 passed, 651 deselected`
- `python -m pytest backend/tests -q --durations=10` -> `651 passed, 123 deselected, 30 warnings`

- [x] **Step 3: Run full frontend and build checks**

Run:

```powershell
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: all commands pass.

Result:
- `npm --prefix frontend test` -> `110 passed`
- `npm --prefix frontend run build` -> pass
- `git diff --check` -> pass; Git emitted only the existing LF-to-CRLF working-copy warning for this plan file.

- [x] **Step 4: Review, commit, and push**

Commit:

```powershell
git add backend/pytest.ini backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py backend/tests/test_frontend_refactor_blueprint.py backend/tests/test_rebranding.py backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-backend-frontend-contract-marker-isolation.md
git commit -m "test: 隔离前端源码契约测试"
git push
```
