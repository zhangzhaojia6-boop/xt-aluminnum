# Seed Multi Role Random Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item S06 by removing the shared default password from the multi-role account seed script.

**Architecture:** Keep the seed script idempotent and non-interactive. For each newly created account, hash a fresh undisclosed random token; do not print or store the token, so account password login requires an explicit admin reset.

**Tech Stack:** Python `secrets`, pytest static contract tests.

---

### Task 1: Add Seed Password Regression Tests

**Files:**
- Create: `backend/tests/test_seed_multi_role_accounts.py`

- [x] **Step 1: Add static secret hygiene test**

Read `backend/scripts/seed_multi_role_accounts.py` and assert it does not contain `xt123456`, `DEFAULT_PASSWORD`, or a reused `pw_hash`.

- [x] **Step 2: Add random hash helper test**

Import the script module, monkeypatch `secrets.token_urlsafe` and `get_password_hash`, and assert two calls to the password hash helper use two different generated tokens.

- [x] **Step 3: Run tests and confirm red**

Run `python -m pytest backend/tests/test_seed_multi_role_accounts.py -q`.

Expected before implementation: static hygiene fails because the script still contains `DEFAULT_PASSWORD = 'xt123456'`.
Observed before implementation: FAIL, `2 failed`; the script contained `xt123456` and had no `secrets` helper.

### Task 2: Replace Shared Seed Password

**Files:**
- Modify: `backend/scripts/seed_multi_role_accounts.py`

- [x] **Step 1: Import `secrets`**

Use Python's standard library `secrets` module.

- [x] **Step 2: Add `_create_random_password_hash` helper**

Return `get_password_hash(secrets.token_urlsafe(24))`.

- [x] **Step 3: Use the helper for each new account**

Replace the module-level default password and shared `pw_hash` with `password_hash=_create_random_password_hash()` inside both workshop-role and factory-role user creation blocks.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move S06 to fixed list**

Add a fixed row for random per-account seed passwords, then remove S06 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_seed_multi_role_accounts.py -q`
- `python -m pytest backend/tests/test_qr_login.py backend/tests/test_auth_routes.py backend/tests/test_auth_schema_contract.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q --durations=10`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_seed_multi_role_accounts.py -q`: PASS, `2 passed`.
- `python -m pytest backend/tests/test_qr_login.py backend/tests/test_auth_routes.py backend/tests/test_auth_schema_contract.py -q`: PASS, `17 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `733 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for security and script idempotency, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-seed-multi-role-random-password.md backend/scripts/seed_multi_role_accounts.py backend/tests/test_seed_multi_role_accounts.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 移除多角色种子默认密码"
```
