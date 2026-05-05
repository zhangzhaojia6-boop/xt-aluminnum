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

- [x] **Step 1: Write the failing static guard**

Add a test that asserts:
- `backend/scripts/test_*.py` does not exist.
- `backend/scripts/smoke_entry_fields.py` and `backend/scripts/smoke_shift.py` do not exist.
- The audit file no longer has pending `S12`.
- The audit file has a resolved `R72` row pointing to TestClient coverage.

- [x] **Step 2: Run the static guard**

Run:

```bash
cd backend
python -m pytest tests/test_quick_cloud_trial_docs_and_ops.py::test_backend_smoke_scripts_are_replaced_by_testclient_coverage -q
```

Expected: FAIL because the two `smoke_*.py` scripts and pending S12 row still exist.

Result: historical red completed before implementation; current static guard passes with scripts removed and R72 recorded.

### Task 2: Add TestClient Route Coverage

**Files:**
- Modify: `backend/tests/test_qr_login.py`

- [x] **Step 1: Extend the QR login test database schema**

Include `WorkshopTemplateConfig.__table__` in the existing SQLite schema setup so `/api/v1/mobile/entry-fields` can query template overrides safely.

- [x] **Step 2: Add entry-fields chain coverage**

Add a parametrized test for `XT-ZR2-EN`, `XT-ZR2-MT`, `XT-ZR2-HY`, and `XT-ZR2-1-OP`:
- Seed a virtual role QR.
- POST `/api/v1/auth/qr-login`.
- Use the returned bearer token with GET `/api/v1/mobile/entry-fields`.
- Assert HTTP 200, expected role, and route payload shape.

- [x] **Step 3: Add current-shift chain coverage**

Add a test for one QR role:
- Seed a virtual role QR.
- POST `/api/v1/auth/qr-login`.
- Monkeypatch `mobile_report_service.get_current_shift` to return a valid current-shift payload while asserting the authenticated user role.
- Use the returned bearer token with GET `/api/v1/mobile/current-shift`.
- Assert HTTP 200 and the mocked payload fields.

- [x] **Step 4: Run the new route tests**

Run:

```bash
cd backend
python -m pytest tests/test_qr_login.py -q
```

Expected: PASS.

Result: `backend/tests/test_qr_login.py` is green and includes TestClient coverage for QR login, entry-fields, and current-shift chains.

### Task 3: Remove Legacy Scripts And Update Audit

**Files:**
- Delete: `backend/scripts/smoke_entry_fields.py`
- Delete: `backend/scripts/smoke_shift.py`
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Delete the scripts**

Remove the two scripts that call local HTTP endpoints and extract bearer tokens from live responses.

- [x] **Step 2: Move S12 to resolved**

Add `R72` to the resolved table, noting that TestClient route tests replaced the manual localhost scripts.

- [x] **Step 3: Remove pending S12**

Delete S12 from "待处理问题清单".

- [x] **Step 4: Re-run the static guard**

Run:

```bash
cd backend
python -m pytest tests/test_quick_cloud_trial_docs_and_ops.py::test_backend_smoke_scripts_are_replaced_by_testclient_coverage -q
```

Expected: PASS.

Result: static guard passes; `smoke_entry_fields.py`, `smoke_shift.py`, and pending `S12` are absent, while `R72` is present.

### Task 4: Verification And Commit

**Files:**
- Verify all files touched in Tasks 1-3.

- [x] **Step 1: Run targeted tests**

```bash
cd backend
python -m pytest tests/test_qr_login.py tests/test_quick_cloud_trial_docs_and_ops.py -q
```

- [x] **Step 2: Run backend full suite**

```bash
cd backend
python -m pytest tests -q
```

- [x] **Step 3: Run frontend baseline**

```bash
cd frontend
npm test
npm run build
```

- [x] **Step 4: Review diff and commit**

```bash
git diff --check
git status --short
git diff -- backend/tests/test_qr_login.py backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-backend-smoke-script-pytest-replacement.md
git add backend/tests/test_qr_login.py backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-backend-smoke-script-pytest-replacement.md backend/scripts/smoke_entry_fields.py backend/scripts/smoke_shift.py
git commit -m "test: 用 TestClient 替换后端 smoke 脚本"
git push
```

Result:
- `python -m pytest backend/tests/test_qr_login.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q` -> `43 passed, 1 deselected`
- `python -m pytest backend/tests -q --durations=10` -> `651 passed, 123 deselected`
- `npm --prefix frontend test` -> `110 passed`
- `npm --prefix frontend run build` -> pass
- `git diff --check` -> pass
- Note: the first backend full-suite attempt used a 10 minute command timeout and timed out; rerun with a longer timeout completed successfully in about 5 minutes.
