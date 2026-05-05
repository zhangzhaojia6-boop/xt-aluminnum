# Report Query And Export Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit items B10 and B11 by covering report list/detail and export boundary behavior.

**Architecture:** Keep route behavior unchanged unless tests expose a real defect. Extend the existing report export route test file with list/detail coverage and export edge cases so the behavior is locked near the route it exercises.

**Tech Stack:** FastAPI TestClient, pytest.

---

### Task 1: Cover Report List And Detail Routes

**Files:**
- Modify: `backend/tests/test_report_export.py`

- [x] **Step 1: Add list route test**

Mock `report_service.list_reports`, call `GET /api/v1/reports` with `start_date`, `end_date`, `report_type`, and `status`, and assert the service receives parsed values and the response includes the fake report.

- [x] **Step 2: Add detail route tests**

Mock `report_service.get_report` and cover:
- hit: `GET /api/v1/reports/99` returns the fake report;
- miss: `GET /api/v1/reports/99` returns `404` with `report not found`.

### Task 2: Cover Export Boundaries

**Files:**
- Modify: `backend/tests/test_report_export.py`

- [x] **Step 1: Add xlsx happy path**

Call `GET /api/v1/reports/99/export?format=xlsx` and assert status 200, xlsx media type, and xlsx attachment filename.

- [x] **Step 2: Add xlsx missing dependency path**

Monkeypatch `builtins.__import__` so importing pandas raises `ImportError('no pandas')`, then assert the route returns 400 with `xlsx export not available`.

- [x] **Step 3: Add invalid format and missing report paths**

Assert invalid format returns 400 and missing report export returns 404.

### Task 3: Close Audit Items And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B10 and B11 to fixed list**

Add `R33` for list/detail coverage and `R34` for export boundary coverage. Remove B10 and B11 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_report_export.py -q`
- `python -m pytest backend/tests/test_report_route_permissions.py backend/tests/test_report_generation.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_report_export.py -q`: PASS, `8 passed`.
- `python -m pytest backend/tests/test_report_route_permissions.py backend/tests/test_report_generation.py -q`: PASS, `15 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q`: PASS, `701 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for scope and maintainability, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-report-query-export-coverage.md backend/tests/test_report_export.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖日报查询导出"
```
