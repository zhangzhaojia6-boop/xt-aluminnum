# Platform Route Test Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item B09 by splitting one mixed platform route test into single-behavior tests.

**Architecture:** Keep all route behavior unchanged. Modify only `backend/tests/test_platform_upgrade_api_routes.py` so search, export, and notification smoke checks run as separate tests with the existing user override helper.

**Tech Stack:** FastAPI TestClient, pytest.

---

### Task 1: Split The Mixed Test

**Files:**
- Modify: `backend/tests/test_platform_upgrade_api_routes.py`

- [x] **Step 1: Split search route check**

Create `test_search_route_returns_navigation_match` for `GET /api/v1/search?q=AI`.

- [x] **Step 2: Split export route check**

Create `test_export_route_returns_attachment` for `POST /api/v1/export/overview`.

- [x] **Step 3: Split notification route check**

Create `test_notification_routes_read_flow` for unread count and mark-read behavior.

### Task 2: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B09 to fixed list**

Add `R40` describing the test split. Remove B09 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_platform_upgrade_api_routes.py backend/tests/test_search_routes.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_platform_upgrade_api_routes.py backend/tests/test_search_routes.py -q`: PASS, `6 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q`: PASS, `715 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope and maintainability, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-platform-route-test-split.md backend/tests/test_platform_upgrade_api_routes.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 拆分平台路由测试"
```
