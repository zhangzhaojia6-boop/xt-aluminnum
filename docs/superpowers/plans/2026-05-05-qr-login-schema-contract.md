# QR Login Schema Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item B22 by aligning the QR login response schema with the route's real response shapes and publishing it through OpenAPI.

**Architecture:** Keep QR login behavior unchanged. Update the auth schema so `QrLoginResponse` represents either a normal token response or a workshop redirect response, then declare it as the `response_model` for `/auth/qr-login`.

**Tech Stack:** FastAPI, Pydantic TypeAdapter, pytest.

---

### Task 1: Add Schema Drift Regression Tests

**Files:**
- Create: `backend/tests/test_auth_schema_contract.py`

- [x] **Step 1: Add schema acceptance test**

Use `TypeAdapter(QrLoginResponse)` to validate the route's existing token-with-null-machine response and workshop redirect response.

- [x] **Step 2: Add OpenAPI response model test**

Assert `/api/v1/auth/qr-login` 200 response schema references both `LoginResponse` and `WorkshopQrResponse`.

- [x] **Step 3: Run tests and confirm red**

Run `python -m pytest backend/tests/test_auth_schema_contract.py -q`.

Expected before implementation: schema validation fails for the current `QrLoginResponse`, and OpenAPI does not expose the QR response union.
Observed before implementation: FAIL, `2 failed`; `machine_info=None` did not validate and OpenAPI exposed a generic object response.

### Task 2: Align QR Login Schema And Route

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/routers/auth.py`

- [x] **Step 1: Make `QrLoginResponse` a union contract**

Move `WorkshopQrResponse` before `QrLoginResponse`, then define `QrLoginResponse` as `Union[LoginResponse, WorkshopQrResponse]` so it accepts the current route shapes.

- [x] **Step 2: Attach response model to QR login route**

Set `@router.post('/qr-login', response_model=QrLoginResponse, name='auth-qr-login')`.

- [x] **Step 3: Run focused auth/QR tests**

Run `python -m pytest backend/tests/test_auth_schema_contract.py backend/tests/test_qr_login.py backend/tests/test_auth_routes.py -q`.

Expected: all commands pass and existing QR behavior remains unchanged.
Observed: PASS, `17 passed`.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B22 to fixed list**

Add a fixed row for QR login schema/OpenAPI alignment, then remove B22 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_auth_schema_contract.py backend/tests/test_qr_login.py backend/tests/test_auth_routes.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q --durations=10`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_auth_schema_contract.py backend/tests/test_qr_login.py backend/tests/test_auth_routes.py -q`: PASS, `17 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `731 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope and API contract safety, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-qr-login-schema-contract.md backend/app/schemas/auth.py backend/app/routers/auth.py backend/tests/test_auth_schema_contract.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 对齐二维码登录响应模型"
```
