# Report Route Error Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item B16 by locking report route `ValueError` failures to HTTP 400 responses.

**Architecture:** Keep the existing route-local try/except pattern. Add focused route tests for generate, review, publish, finalize, and daily pipeline actions; only change `run_daily_pipeline` because it is the missing mapper.

**Tech Stack:** FastAPI TestClient, pytest.

---

### Task 1: Add Red Tests For Route Error Mapping

**Files:**
- Modify: `backend/tests/test_report_route_permissions.py`

- [x] **Step 1: Add error mapping tests**

Add tests that monkeypatch report services to raise `ValueError('boom')` and assert each route returns status 400 with the same detail:
- `POST /api/v1/reports/generate`
- `POST /api/v1/reports/{id}/review`
- `POST /api/v1/reports/{id}/publish`
- `POST /api/v1/reports/{id}/finalize`
- `POST /api/v1/reports/run-daily-pipeline`

- [x] **Step 2: Run red tests**

Run: `python -m pytest backend/tests/test_report_route_permissions.py -q`

Expected: FAIL on daily pipeline because `run_daily_pipeline` currently lets `ValueError` escape as a server error.
Observed: FAIL, daily pipeline returned 500 while the expected response was 400.

### Task 2: Map Pipeline ValueError To HTTP 400

**Files:**
- Modify: `backend/app/routers/reports.py`

- [x] **Step 1: Wrap `report_service.run_daily_pipeline`**

Use the same local pattern as generate/review/publish/finalize:

```python
try:
    blocked, message, open_count, is_final_version, boss_text, reports = report_service.run_daily_pipeline(...)
except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc))
```

- [x] **Step 2: Run focused tests**

Run: `python -m pytest backend/tests/test_report_route_permissions.py -q`

Expected: PASS.
Observed: PASS, `11 passed`.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B16 to fixed list**

Add `R32` describing report route error mapping coverage. Remove B16 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_report_route_permissions.py backend/tests/test_report_generation.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_report_route_permissions.py backend/tests/test_report_generation.py -q`: PASS, `15 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q`: PASS, `694 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope and security, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-report-route-error-mapping.md backend/tests/test_report_route_permissions.py backend/app/routers/reports.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖日报错误映射"
```
