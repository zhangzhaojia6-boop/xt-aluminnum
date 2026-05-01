# Git Cloud QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Review the current mobile entry test progress, verify it from a customer workflow perspective, fix confirmed bugs, then commit and push the verified state to `origin/main`.

**Architecture:** The current release handoff is test-surface only on top of the latest mobile-entry fix commit. Verification covers admin/review session hydration, owner-only mobile entry paths, workshop template editing, unified machine entry, frontend build, backend pytest, and the full Playwright suite before publishing.

**Tech Stack:** Vue/Vite frontend, Playwright e2e tests, Python backend with pytest, GitHub remote `origin`.

---

## File Structure

- Modify: `frontend/e2e/admin-surface.spec.js`
  - Align admin navigation assertions with current manage shell labels.
- Modify: `frontend/e2e/helpers/review-mocks.js`
  - Seed sessionStorage for the auth store in mocked review/admin tests.
- Modify: `frontend/e2e/owner-only-contract-dashboard.spec.js`
  - Assert current contract owner entry title.
- Modify: `frontend/e2e/owner-only-inventory-dashboard.spec.js`
  - Assert current inventory owner entry title.
- Modify: `frontend/e2e/owner-only-utility-workshop.spec.js`
  - Assert current utility owner title and fill fields by visible field label.
- Modify: `frontend/e2e/workshop-template-config.spec.js`
  - Make the workshop template/customer machine flow deterministic with route mocks.
- Create: `docs/superpowers/plans/2026-05-01-git-cloud-qa.md`
  - Execution plan and verification record for this release handoff.

## Assumptions

- "pull 上云" means commit locally and push the current verified progress to the configured GitHub remote.
- No production deployment is requested unless the repository has an existing post-push cloud workflow.
- Because this is a release handoff, do not commit secrets or unrelated local artifacts.
- If tests expose a bug, apply `superpowers:systematic-debugging`: reproduce, identify root cause, then make the smallest fix.

### Task 1: Plan And Scope Lock

**Files:**
- Create: `docs/superpowers/plans/2026-05-01-git-cloud-qa.md`

- [x] **Step 1: Save this plan**

Run: `git status --short`
Expected: only the existing e2e changes plus this plan are uncommitted.

- [x] **Step 2: Confirm remote and branch**

Run: `git status --short --branch`
Expected: `main...origin/main`.

Run: `git remote -v`
Expected: `origin` fetch/push points to the GitHub repository.

### Task 2: Code Review Reception

**Files:**
- Read: `frontend/e2e/dynamic-entry-layout.spec.js`
- Read: `frontend/e2e/zd1-machine-smoke.spec.js`
- Read: `frontend/e2e/helpers/unified-entry-mocks.js`

- [x] **Step 1: Review changed tests**

Run: `git diff -- frontend/e2e/dynamic-entry-layout.spec.js frontend/e2e/zd1-machine-smoke.spec.js frontend/e2e/helpers/unified-entry-mocks.js`
Expected: tests follow the unified `/entry` -> `/entry/fill` flow and submit to `/api/v1/mobile/coil-entry`.

- [x] **Step 2: Compare against implementation**

Read the relevant frontend route/component code for `/entry`, `/entry/fill`, `mobile-go-report`, `unified-entry`, and the coil submit API call.
Expected: selectors and mocked response shapes match real code.

### Task 3: Targeted Customer Workflow Tests

**Files:**
- Test: `frontend/e2e/dynamic-entry-layout.spec.js`
- Test: `frontend/e2e/zd1-machine-smoke.spec.js`

- [x] **Step 1: Run targeted Playwright tests**

Run: `npm run e2e -- e2e/dynamic-entry-layout.spec.js e2e/zd1-machine-smoke.spec.js`
Expected: both specs pass in Chromium.

- [x] **Step 2: If a test fails, investigate root cause**

Read the full Playwright error and trace the failing selector, route, or API payload back to the changed test/helper before editing.
Expected: the cause is known before any fix.

### Task 4: Project Verification

**Files:**
- Verify: `frontend/package.json`
- Verify: `backend/pytest.ini`

- [x] **Step 1: Build frontend**

Run: `npm run build`
Expected: Vite build succeeds.

- [x] **Step 2: Run backend test suite**

Run: `python -m pytest`
Expected: backend pytest suite passes.

- [x] **Step 3: Run broader e2e suite when practical**

Run: `npm run e2e`
Expected: Playwright suite passes, or any failure is root-caused and reported/fixed.

### Task 5: Fix Confirmed Issues Only

**Files:**
- Modify only files directly tied to the confirmed failure.

- [x] **Step 1: Write or adjust the failing test first**

Use the smallest test that reproduces the confirmed bug.
Expected: test fails for the observed reason.

- [x] **Step 2: Implement the minimal fix**

Edit only the source/test fixture responsible for the bug.
Expected: targeted test passes.

- [x] **Step 3: Re-run relevant regression checks**

Run the targeted test plus the smallest broader suite that could catch regressions.
Expected: all relevant checks pass.

### Task 6: Commit And Push

**Files:**
- Stage only verified, non-secret files.

- [x] **Step 1: Final status review**

Run: `git status --short`
Expected: changed files are intended; `.env`, build output, cache folders, and temporary artifacts are not staged.

- [x] **Step 2: Commit**

Run: `git add <verified files>`
Run: `git commit -m "test: stabilize customer workflow e2e"`
Expected: commit succeeds.

- [x] **Step 3: Push to cloud remote**

Run: `git push origin main`
Expected: remote `origin/main` contains the new commit.
