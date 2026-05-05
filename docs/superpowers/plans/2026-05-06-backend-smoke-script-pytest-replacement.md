# Backend Smoke Script Pytest Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item S12 by replacing localhost/live-token backend smoke scripts with pytest + FastAPI TestClient coverage.

**Architecture:** Keep the runtime routes unchanged. Add route-level tests that exercise QR login followed by mobile endpoints through TestClient, then remove the legacy scripts that call `http://127.0.0.1:8000`.

**Tech Stack:** Python, pytest, FastAPI TestClient, SQLAlchemy SQLite test database.

---

### Task 1: Prove The Current S12 Gap

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`
- Read: `backend/scripts/smoke_entry_fields.py`
- Read: `backend/scripts/smoke_shift.py`
- Read: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [ ] **Step 1: Write the failing static guard**

Add a test that asserts:
- `backend/scripts/test_*.py` does not exist.
- `backend/scripts/smoke_entry_fields.py` and `backend/scripts/smoke_shift.py` do not exist.
- The audit file no longer has pending `S12`.
- The audit file has a resolved `R72` row pointing to TestClient coverage.

- [ ] **Step 2: Run the static guard**

Run:

```bash
cd backend
python -m pytest tests/test_quick_cloud_trial_docs_and_ops.py::test_backend_smoke_scripts_are_replaced_by_testclient_coverage -q
```

Expected: FAIL because the two `smoke_*.py` scripts and pending S12 row still exist.

### Task 2: Add TestClient Route Coverage

**Files:**
- Modify: `backend/tests/test_qr_login.py`

- [ ] **Step 1: Extend the QR login test database schema**

Include `WorkshopTemplateConfig.__table__` in the existing SQLite schema setup so `/api/v1/mobile/entry-fields` can query template overrides safely.

- [ ] **Step 2: Add entry-fields chain coverage**

Add a parametrized test for `XT-ZR2-EN`, `XT-ZR2-MT`, `XT-ZR2-HY`, and `XT-ZR2-1-OP`:
- Seed a virtual role QR.
- POST `/api/v1/auth/qr-login`.
- Use the returned bearer token with GET `/api/v1/mobile/entry-fields`.
- Assert HTTP 200, expected role, and route payload shape.

- [ ] **Step 3: Add current-shift chain coverage**

Add a test for one QR role:
- Seed a virtual role QR.
- POST `/api/v1/auth/qr-login`.
- Monkeypatch `mobile_report_service.get_current_shift` to return a valid current-shift payload while asserting the authenticated user role.
- Use the returned bearer token with GET `/api/v1/mobile/current-shift`.
- Assert HTTP 200 and the mocked payload fields.

- [ ] **Step 4: Run the new route tests**

Run:

```bash
cd backend
python -m pytest tests/test_qr_login.py -q
```

Expected: PASS.

### Task 3: Remove Legacy Scripts And Update Audit

**Files:**
- Delete: `backend/scripts/smoke_entry_fields.py`
- Delete: `backend/scripts/smoke_shift.py`
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [ ] **Step 1: Delete the scripts**

Remove the two scripts that call local HTTP endpoints and extract bearer tokens from live responses.

- [ ] **Step 2: Move S12 to resolved**

Add `R72` to the resolved table, noting that TestClient route tests replaced the manual localhost scripts.

- [ ] **Step 3: Remove pending S12**

Delete S12 from "待处理问题清单".

- [ ] **Step 4: Re-run the static guard**

Run:

```bash
cd backend
python -m pytest tests/test_quick_cloud_trial_docs_and_ops.py::test_backend_smoke_scripts_are_replaced_by_testclient_coverage -q
```

Expected: PASS.

### Task 4: Verification And Commit

**Files:**
- Verify all files touched in Tasks 1-3.

- [ ] **Step 1: Run targeted tests**

```bash
cd backend
python -m pytest tests/test_qr_login.py tests/test_quick_cloud_trial_docs_and_ops.py -q
```

- [ ] **Step 2: Run backend full suite**

```bash
cd backend
python -m pytest tests -q
```

- [ ] **Step 3: Run frontend baseline**

```bash
cd frontend
npm test
npm run build
```

- [ ] **Step 4: Review diff and commit**

```bash
git diff --check
git status --short
git diff -- backend/tests/test_qr_login.py backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-backend-smoke-script-pytest-replacement.md
git add backend/tests/test_qr_login.py backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-backend-smoke-script-pytest-replacement.md backend/scripts/smoke_entry_fields.py backend/scripts/smoke_shift.py
git commit -m "test: 用 TestClient 替换后端 smoke 脚本"
git push
```
