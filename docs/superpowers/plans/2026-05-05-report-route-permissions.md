# Report Route Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit items B12, B13, and B15 by adding explicit role gates to report review, report publish, and daily pipeline execution routes.

**Architecture:** Keep read-only report routes on normal authentication. Add small route-local permission helpers in `backend/app/routers/reports.py`: review actions allow reviewer, manager, or admin; publish and pipeline actions allow manager or admin. Tests use FastAPI dependency overrides and monkeypatched services to prove denied users receive 403 before service calls.

**Tech Stack:** FastAPI, pytest, TestClient, existing `User` model role flags.

---

### Task 1: Add Red Tests For Report Write Permissions

**Files:**
- Create: `backend/tests/test_report_route_permissions.py`

- [x] **Step 1: Write failing tests**

```python
from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def _fake_get_db():
    yield DummyDB()


def _user(role: str, *, is_reviewer: bool = False, is_manager: bool = False) -> User:
    return User(
        id=42,
        username=role,
        password_hash='x',
        name=role,
        role=role,
        is_reviewer=is_reviewer,
        is_manager=is_manager,
        is_active=True,
    )


def _override_user(user: User) -> None:
    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_current_user] = lambda: user


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_report_review_rejects_fill_only_user_before_service_call(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.review_report', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('service should not run')))
    _override_user(_user('machine_operator', is_reviewer=False, is_manager=False))

    response = TestClient(app).post('/api/v1/reports/5/review', json={'note': 'x'})

    assert response.status_code == 403
    assert response.json()['detail'] == 'Report review access denied'


def test_report_review_allows_reviewer_role(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.review_report', lambda *_args, **_kwargs: SimpleNamespace(
        id=5, report_date=date(2026, 3, 25), report_type='production', workshop_id=None, report_data={},
        text_summary='summary', generated_scope='all', output_mode='both', status='reviewed',
        generated_at=datetime(2026, 3, 25, 9, 0, 0), reviewed_by=42,
        reviewed_at=datetime(2026, 3, 25, 9, 0, 0), published_by=None, published_at=None,
        created_at=datetime(2026, 3, 25, 9, 0, 0), updated_at=datetime(2026, 3, 25, 9, 0, 0),
    ))
    _override_user(_user('reviewer', is_reviewer=True, is_manager=False))

    response = TestClient(app).post('/api/v1/reports/5/review', json={'note': 'x'})

    assert response.status_code == 200


def test_report_publish_rejects_reviewer_without_manager_access(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.publish_report', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('service should not run')))
    _override_user(_user('reviewer', is_reviewer=True, is_manager=False))

    response = TestClient(app).post('/api/v1/reports/5/publish', json={'note': 'x'})

    assert response.status_code == 403
    assert response.json()['detail'] == 'Report publish access denied'


def test_daily_pipeline_rejects_fill_only_user_before_service_call(monkeypatch) -> None:
    monkeypatch.setattr('app.routers.reports.report_service.run_daily_pipeline', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('service should not run')))
    _override_user(_user('machine_operator', is_reviewer=False, is_manager=False))

    response = TestClient(app).post('/api/v1/reports/run-daily-pipeline', json={'report_date': '2026-03-25'})

    assert response.status_code == 403
    assert response.json()['detail'] == 'Report publish access denied'
```

- [x] **Step 2: Run red tests**

Run: `python -m pytest backend/tests/test_report_route_permissions.py -q`

Expected: FAIL because the endpoints still call services for denied users.

### Task 2: Implement Route-Level Permission Helpers

**Files:**
- Modify: `backend/app/routers/reports.py`

- [x] **Step 1: Add helpers**

Add:
- `_ensure_report_review_access(user)`
- `_ensure_report_publish_access(user)`

Use `build_scope_summary()` so `role == 'admin'` plus `is_reviewer` / `is_manager` flags and role names already recognized by `app.core.scope` stay consistent.

- [x] **Step 2: Wire helpers**

Call `_ensure_report_review_access(current_user)` before `report_service.review_report(...)`. Call `_ensure_report_publish_access(current_user)` before `report_service.publish_report(...)` and before `report_service.run_daily_pipeline(...)`.

- [x] **Step 3: Run focused tests**

Run: `python -m pytest backend/tests/test_report_route_permissions.py backend/tests/test_report_publish_flow.py backend/tests/test_daily_pipeline.py -q`

Expected: PASS.

### Task 3: Close Audit Items And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move B12/B13/B15 to fixed list**

Add `R28`, `R29`, and `R30` for review, publish, and pipeline permission gates. Remove B12, B13, and B15 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `python -m pytest backend/tests/test_report_route_permissions.py backend/tests/test_report_publish_flow.py backend/tests/test_daily_pipeline.py -q`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `python -m pytest backend/tests -q`
- `git diff --check`

Expected: all commands pass.

Verification note: focused report permission tests passed, mobile entry static contract passed, backend full pytest passed with `686 passed`, and `git diff --check` passed.

- [x] **Step 3: Review diff and commit**

Review the diff for scope, security, and compatibility, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-report-route-permissions.md backend/tests/test_report_route_permissions.py backend/app/routers/reports.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 限制日报写操作权限"
```
