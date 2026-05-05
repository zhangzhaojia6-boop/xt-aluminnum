# QR Login Virtual Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit items B04 and B05 by covering virtual workshop and virtual role QR login branches.

**Architecture:** Keep `auth.py` behavior unchanged and add route-level tests beside the existing physical machine QR login tests. Use the same SQLite-backed TestClient pattern so the virtual QR branches exercise real DB writes, token creation, and audit logging.

**Tech Stack:** FastAPI TestClient, SQLAlchemy SQLite sessionmaker, pytest.

---

### Task 1: Cover Virtual Workshop QR Redirect

**Files:**
- Modify: `backend/tests/test_qr_login.py`

- [x] **Step 1: Add shared DB override helper**

Create a local helper that sets `app.dependency_overrides[get_db]` for the test module so new tests do not repeat the generator boilerplate.

- [x] **Step 2: Add virtual workshop QR test**

Seed a running `Equipment` row with `equipment_type='virtual_workshop_qr'`, call `POST /api/v1/auth/qr-login`, and assert:
- status 200
- `type == 'workshop_redirect'`
- workshop code/name come from the linked workshop
- no access token is issued for redirect-only QR

### Task 2: Cover Virtual Role QR Login

**Files:**
- Modify: `backend/tests/test_qr_login.py`

- [x] **Step 1: Add auto-create user test**

Seed a running role QR with code suffix `OP`, call QR login, and assert a mobile `machine_operator` user is created, token is returned, `machine_info` is returned for operator QR, and an audit record is written.

- [x] **Step 2: Add existing user reuse test**

Seed an existing `EN` user and matching role QR, call QR login, and assert the existing user is reused, no duplicate user is created, and non-operator role QR returns `machine_info is None`.

- [x] **Step 3: Add missing workshop and invalid suffix tests**

Cover a role QR whose workshop row is missing with 404 `车间不存在`, and a role QR with unsupported suffix with 400 `无效角色码`.

### Task 3: Close Audit Items And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B04 and B05 to fixed list**

Add fixed rows for virtual workshop QR and virtual role QR coverage, then remove B04 and B05 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_qr_login.py -q`
- `python -m pytest backend/tests/test_auth_routes.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_qr_login.py -q`: PASS, `8 passed`.
- `python -m pytest backend/tests/test_auth_routes.py -q`: PASS, `7 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `727 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope, security, and test isolation, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-qr-login-virtual-coverage.md backend/tests/test_qr_login.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖虚拟二维码登录"
```
