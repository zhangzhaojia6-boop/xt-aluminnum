# Notification User Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit items B06 and B07 by isolating notification read state per user and locking missing-notification semantics.

**Architecture:** Keep the prototype notification catalog in memory, but make it immutable at request boundaries and store only read state per user id. Return 404 for unknown notification ids so callers get explicit API semantics instead of a 200 response with `ok=false`.

**Tech Stack:** FastAPI, pytest, TestClient.

---

### Task 1: Add Notification Route Regression Tests

**Files:**
- Create: `backend/tests/test_notification_routes.py`

- [x] **Step 1: Add per-user read isolation test**

Override `get_current_user` with user 1, mark `welcome` read, then override with user 2 and assert user 2 still sees the notification unread.

- [x] **Step 2: Add missing notification test**

Call `POST /api/v1/notifications/missing/read` and assert HTTP 404 with a stable error detail.

- [x] **Step 3: Run tests and confirm red**

Run `python -m pytest backend/tests/test_notification_routes.py -q`.

Expected before implementation: per-user isolation fails because read state is global, and missing notification fails because current code returns 200 `ok=false`.
Observed before implementation: FAIL, `2 failed`; user 2 unread count was `0`, and missing notification returned HTTP 200.

### Task 2: Implement User-Scoped Read State

**Files:**
- Modify: `backend/app/routers/notifications.py`
- Modify: `backend/tests/test_platform_upgrade_api_routes.py`

- [x] **Step 1: Split notification catalog from read state**

Replace mutable per-notification `read` storage with:
- a default notification catalog
- a `notification_read_state` map keyed by `current_user.id`
- helper functions for user key, per-user list building, and id lookup

- [x] **Step 2: Return user-scoped list and count**

`GET /notifications` should return copies with a computed `read` flag. `GET /unread-count` should count unread notifications for the current user only.

- [x] **Step 3: Mark read per user and return 404 for unknown ids**

`POST /{notification_id}/read` should add the id to only the current user's read set. Unknown ids should raise 404 `通知不存在`.

- [x] **Step 4: Update existing platform route teardown**

Clear `notification_read_state` in the existing platform route tests instead of mutating removed `notifications_db`.

### Task 3: Close Audit Items And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B06 and B07 to fixed list**

Add fixed rows for user-scoped notification read state and missing-notification 404 semantics, then remove B06 and B07 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_notification_routes.py backend/tests/test_platform_upgrade_api_routes.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q --durations=10`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_notification_routes.py backend/tests/test_platform_upgrade_api_routes.py -q`: PASS, `6 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `729 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope, security, and state isolation, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-notification-user-isolation.md backend/app/routers/notifications.py backend/tests/test_notification_routes.py backend/tests/test_platform_upgrade_api_routes.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 隔离通知已读状态"
```
