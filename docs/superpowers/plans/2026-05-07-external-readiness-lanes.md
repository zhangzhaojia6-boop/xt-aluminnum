# External Readiness Lanes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the management first screen show which external readiness lane is blocking delivery without exposing secrets or requiring new credentials.

**Architecture:** Reuse the existing `GET /api/v1/dashboard/external-readiness` payload already loaded by `LiveDashboard.vue`. Add a compact read-only lane visualization that maps hard and warning issues into operational labels and required-env summaries. Do not add backend writes, do not echo secret values, and do not change readiness gate semantics.

**Tech Stack:** Vue 3 computed state, existing Element Plus page shell, static frontend contract tests, Vite build.

---

### Task 1: Frontend Contract

**Files:**
- Modify: `frontend/tests/managementCommandCenter.test.js`

- [x] Add assertions that `LiveDashboard.vue` renders an `external-readiness-lanes` section.
- [x] Assert the page maps `LLM_DISABLED`, `APP_CONNECTION_DISABLED`, and `DINGTALK_NO_BOUND_USERS` into management-readable lane labels.
- [x] Assert no mutation action text such as `保存密钥`, `写入配置`, or `启用外联` appears in the readiness lane.
- [x] Run `node --test frontend/tests/managementCommandCenter.test.js` and confirm the new assertions fail before implementation.

### Task 2: Live Dashboard Lane View

**Files:**
- Modify: `frontend/src/views/reports/LiveDashboard.vue`

- [x] Add computed `externalWarningIssues` and `externalReadinessLanes` from existing `externalReadiness`.
- [x] Render a compact `外部联通明细` section with lane label, state, and required-env summary.
- [x] Use restrained status styling with stable responsive dimensions; keep it read-only and avoid helper/marketing copy.
- [x] Run `node --test frontend/tests/managementCommandCenter.test.js`.

### Task 3: Verification And Release

- [x] Run `npm --prefix frontend test`.
- [x] Run `npm --prefix frontend run build`.
- [x] Run `git diff --check`.
- [ ] Commit, push, deploy, and verify production `/readyz` remains ready.
