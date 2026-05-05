# Search Blank Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item B08 by preventing blank search queries from returning all navigation results.

**Architecture:** Keep the current static search result shape. Add focused route tests, then reject queries that become empty after `strip()` with HTTP 422 before filtering navigation.

**Tech Stack:** FastAPI TestClient, pytest.

---

### Task 1: Add Search Route Tests

**Files:**
- Create: `backend/tests/test_search_routes.py`

- [x] **Step 1: Cover normal query behavior**

Call `GET /api/v1/search?q=AI` and assert the AI workbench navigation result is returned.

- [x] **Step 2: Add blank query red test**

Call `GET /api/v1/search?q=%20%20%20` and assert status 422.

- [x] **Step 3: Run red tests**

Run: `python -m pytest backend/tests/test_search_routes.py -q`

Expected: FAIL because blank search currently returns 200 with all navigation.
Observed: FAIL, blank search returned 200 instead of 422.

### Task 2: Reject Blank Query After Strip

**Files:**
- Modify: `backend/app/routers/search.py`

- [x] **Step 1: Add route-level blank query guard**

Strip the incoming query first. If the stripped value is empty, raise `HTTPException(status_code=422, detail='q must not be blank')`.

- [x] **Step 2: Run focused tests**

Run: `python -m pytest backend/tests/test_search_routes.py -q`

Expected: PASS.
Observed: PASS, `2 passed`.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B08 to fixed list**

Add `R39` describing the blank search guard. Remove B08 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_search_routes.py backend/tests/test_platform_upgrade_api_routes.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_search_routes.py backend/tests/test_platform_upgrade_api_routes.py -q`: PASS, `4 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q`: PASS, `713 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope and behavior, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-search-blank-query.md backend/tests/test_search_routes.py backend/app/routers/search.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 校验空白搜索"
```
