# Auth Route Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit items B02 and B03 by covering core authentication routes with real interface tests.

**Architecture:** Use a small SQLite database per test module with the exact tables touched by `auth.py`: `users`, `workshops`, `teams`, `equipment`, and `audit_logs`. Keep route behavior unchanged unless tests expose a real defect.

**Tech Stack:** FastAPI TestClient, SQLAlchemy SQLite sessionmaker, pytest.

---

### Task 1: Cover Login Behavior

**Files:**
- Create: `backend/tests/test_auth_routes.py`

- [x] **Step 1: Add login success test**

Seed an active user with a hashed password, call `POST /api/v1/auth/login`, and assert token, user payload, `machine_info is None`, `last_login` update, and login audit record.

- [x] **Step 2: Add wrong password and disabled user tests**

Assert wrong password returns 400 and disabled user with correct password returns 403.

- [x] **Step 3: Add init admin bootstrap test**

Patch `INIT_ADMIN_USERNAME`, `INIT_ADMIN_PASSWORD`, and `INIT_ADMIN_NAME`, call login against an empty DB, and assert the admin user is created and returned.

### Task 2: Cover Me And Logout

**Files:**
- Modify: `backend/tests/test_auth_routes.py`

- [x] **Step 1: Add `/me` success and failure tests**

Use a real access token for success and an invalid bearer token for failure.

- [x] **Step 2: Add logout response contract test**

Call `POST /api/v1/auth/logout` and assert the current response contract.

### Task 3: Close Audit Items And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B02 and B03 to fixed list**

Add `R41` for login coverage and `R42` for `/me` and `/logout` coverage. Remove B02 and B03 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_auth_routes.py -q`
- `python -m pytest backend/tests/test_qr_login.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_auth_routes.py -q`: PASS, `7 passed`.
- `python -m pytest backend/tests/test_qr_login.py -q`: PASS, `3 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q`: PASS, `722 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope, security, and test isolation, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-auth-route-coverage.md backend/tests/test_auth_routes.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖认证基础接口"
```
