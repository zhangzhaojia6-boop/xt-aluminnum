# Reference Page Brand Canonicalization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shared reference page frame use the canonical visible product name `鑫泰铝业 数据中枢`.

**Architecture:** Keep `ReferencePageFrame` layout, props, CSS hooks, and page composition unchanged. Replace only the visible system string in the shared frame so every page using it inherits the canonical product identity.

**Scope:** Branding copy only. Do not change routing, navigation grouping, reference components, CSS, or page module numbers.

**Tech Stack:** Backend frontend-contract rebranding test, frontend node contract test, frontend build.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `backend/tests/test_rebranding.py`
- Modify: `frontend/tests/managementCommandCenter.test.js`

- [x] **Step 1: Backend rebranding red test**

Extend `test_user_facing_brand_strings_are_updated` to read `frontend/src/components/reference/ReferencePageFrame.vue` and require:
- `鑫泰铝业 数据中枢 · 运行中心`
- no `鑫泰数据中枢 · 运行中心`

Run:

```powershell
python -m pytest backend/tests/test_rebranding.py::test_user_facing_brand_strings_are_updated -m frontend_contract -q
```

Expected before implementation: FAIL because the component still contains `鑫泰数据中枢 · 运行中心`.

- [x] **Step 2: Frontend node red test**

Extend `managementCommandCenter.test.js` to require the canonical frame brand and reject the old string.

Run:

```powershell
npm --prefix frontend test -- tests/managementCommandCenter.test.js
```

Expected before implementation: FAIL for the same old string.

### Task 2: Implement Canonical Brand

**Files:**
- Modify: `frontend/src/components/reference/ReferencePageFrame.vue`

- [x] **Step 1: Replace visible system name**

Change `鑫泰数据中枢 · 运行中心` to `鑫泰铝业 数据中枢 · 运行中心`.

### Task 3: Audit And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Add resolved audit row**

Add `R80` describing ReferencePageFrame canonical product naming.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m pytest backend/tests/test_rebranding.py::test_user_facing_brand_strings_are_updated -m frontend_contract -q
python -m pytest backend/tests -m frontend_contract -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: all commands pass. Existing CRLF warnings are acceptable only when exit code is 0.

Actual:
- `python -m pytest backend/tests/test_rebranding.py::test_user_facing_brand_strings_are_updated -m frontend_contract -q` -> `1 passed`
- `python -m pytest backend/tests -m frontend_contract -q` -> `119 passed, 646 deselected`
- `python -m pytest backend/tests -q` -> `646 passed, 119 deselected, 30 warnings`
- `npm --prefix frontend test` -> `108 passed`
- `npm --prefix frontend run build` -> passed
- `git diff --check` -> exit 0 with existing CRLF warnings
