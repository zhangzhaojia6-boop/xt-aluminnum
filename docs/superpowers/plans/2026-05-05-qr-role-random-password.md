# QR Role Random Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item S05 by removing the shared default password from QR role auto-created users.

**Architecture:** Keep QR login behavior unchanged. When a virtual role QR creates a user, hash a cryptographically random token instead of a known password and leave `pin_code` unset, so the account is QR-token-only until an admin explicitly resets credentials.

**Tech Stack:** Python `secrets`, FastAPI route tests, pytest.

---

### Task 1: Add Default Password Regression Test

**Files:**
- Modify: `backend/tests/test_qr_login.py`

- [x] **Step 1: Assert QR auto-created user cannot use shared password**

In the virtual role auto-create test, load the created user and assert `verify_password('xt123456', user.password_hash) is False`.

- [x] **Step 2: Assert QR auto-created user has no PIN fallback**

Assert `user.pin_code is None` so no clear fallback PIN is silently introduced.

- [x] **Step 3: Run test and confirm red**

Run `python -m pytest backend/tests/test_qr_login.py::test_qr_login_virtual_role_creates_mobile_operator_user -q`.

Expected before implementation: the default password assertion fails.
Observed before implementation: FAIL; `verify_password('xt123456', user.password_hash)` returned `True`.

### Task 2: Replace Shared Password With Random Secret

**Files:**
- Modify: `backend/app/routers/auth.py`

- [x] **Step 1: Import `secrets`**

Use Python's standard library `secrets` module.

- [x] **Step 2: Hash an undisclosed random token**

Replace `get_password_hash('xt123456')` with `get_password_hash(secrets.token_urlsafe(24))` for virtual role QR auto-created users.

- [x] **Step 3: Run focused QR/auth tests**

Run `python -m pytest backend/tests/test_qr_login.py backend/tests/test_auth_routes.py backend/tests/test_auth_schema_contract.py -q`.

Expected: all commands pass and QR login still issues tokens.
Observed focused check: PASS, `17 passed`.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move S05 to fixed list**

Add a fixed row for QR role random password behavior, then remove S05 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_qr_login.py backend/tests/test_auth_routes.py backend/tests/test_auth_schema_contract.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q --durations=10`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_qr_login.py backend/tests/test_auth_routes.py backend/tests/test_auth_schema_contract.py -q`: PASS, `17 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `731 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for security and behavior scope, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-qr-role-random-password.md backend/app/routers/auth.py backend/tests/test_qr_login.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 移除二维码默认密码"
```
