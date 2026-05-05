# Admin Bootstrap Preserve Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item S07 by ensuring production startup bootstrap does not reset an existing admin password.

**Architecture:** Keep first-time admin creation behavior intact. For an existing admin username, normalize admin metadata if needed but preserve the stored password hash so changing `.env` or restarting production compose cannot silently rotate the live admin credential.

**Tech Stack:** SQLAlchemy SQLite tests, pytest, existing `get_password_hash` / `verify_password` helpers.

---

### Task 1: Add Existing Admin Password Regression Tests

**Files:**
- Create: `backend/tests/test_admin_bootstrap.py`

- [x] **Step 1: Add `create_admin` existing-user test**

Seed an admin with password `Existing#2026`, call `backend/scripts/create_admin.py:create_admin` with password `New#2026`, and assert the stored hash still verifies only the existing password.

- [x] **Step 2: Add `ensure_admin_user` existing-user test**

Patch bootstrap settings to use password `New#2026`, call `app.services.bootstrap.ensure_admin_user`, and assert the stored hash still verifies only the existing password.

- [x] **Step 3: Add first-time creation guard**

Assert `create_admin` still creates a missing admin with the provided password.

- [x] **Step 4: Run tests and confirm red**

Run `python -m pytest backend/tests/test_admin_bootstrap.py -q`.

Expected before implementation: existing-user tests fail because current code overwrites `password_hash`.
Observed before implementation: FAIL, `2 failed, 1 passed`; existing-user tests showed `password_hash` was overwritten.

### Task 2: Preserve Existing Admin Password

**Files:**
- Modify: `backend/scripts/create_admin.py`
- Modify: `backend/app/services/bootstrap.py`

- [x] **Step 1: Stop overwriting existing password in script**

Remove `user.password_hash = get_password_hash(password)` from the existing-user branch of `create_admin`.

- [x] **Step 2: Stop overwriting existing password in service helper**

Remove the same password overwrite from `ensure_admin_user`.

- [x] **Step 3: Keep first-time creation behavior**

Keep `password_hash=get_password_hash(...)` only in the new-user branch.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move S07 to fixed list**

Add a fixed row for preserving existing admin passwords, then remove S07 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_admin_bootstrap.py backend/tests/test_auth_routes.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q --durations=10`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_admin_bootstrap.py backend/tests/test_auth_routes.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`: PASS, `26 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `736 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for security and deployment behavior scope, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-admin-bootstrap-preserve-password.md backend/scripts/create_admin.py backend/app/services/bootstrap.py backend/tests/test_admin_bootstrap.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 保留已有管理员密码"
```
