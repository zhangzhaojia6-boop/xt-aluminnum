# Runtime Config Secret Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit items S02, S03, and S04 by removing password-looking database defaults and making trial-like runtime environments fail fast on weak secrets.

**Architecture:** Keep Docker and production deployments on explicit environment values. Replace static password-bearing defaults with passwordless development placeholders, keep Alembic runtime DSN sourced from `Settings`, and broaden production-like environment detection without changing development warning behavior.

**Tech Stack:** Pydantic Settings, SQLAlchemy URL parsing, Alembic, pytest.

---

### Task 1: Add Configuration Hygiene Regression Tests

**Files:**
- Modify: `backend/tests/test_runtime_config.py`

- [x] **Step 1: Test `Settings` default database URL has no embedded password**

Use `Settings(_env_file=None)` with `DATABASE_URL` removed from the process environment, parse `settings.DATABASE_URL` with SQLAlchemy `make_url`, and assert there is no password.

- [x] **Step 2: Test `backend/alembic.ini` has no embedded default database password**

Read `backend/alembic.ini`, extract `sqlalchemy.url`, parse it with `make_url`, and assert the URL has no password.

- [x] **Step 3: Test trial-like environments fail fast on weak defaults**

Instantiate `Settings(APP_ENV='trial', SECRET_KEY=EXAMPLE_SECRET_KEY, INIT_ADMIN_PASSWORD=EXAMPLE_ADMIN_PASSWORD)` and assert `validate_runtime_settings()` raises `RuntimeError`.

- [x] **Step 4: Run tests and confirm red**

Run:

```bash
python -m pytest backend/tests/test_runtime_config.py -q
```

Expected before implementation: at least the default database URL, Alembic URL, and trial environment tests fail.
Observed before implementation: FAIL, `3 failed, 16 passed`; failures matched the three expected gaps.

### Task 2: Remove Password-Bearing Defaults

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/alembic.ini`

- [x] **Step 1: Replace the `Settings.DATABASE_URL` default**

Change the default DSN from the password-bearing PostgreSQL URL to a passwordless development placeholder.

- [x] **Step 2: Replace the `alembic.ini` fallback URL**

Set `sqlalchemy.url` to the same passwordless placeholder. `backend/alembic/env.py` already overrides this with `settings.DATABASE_URL` at runtime.

### Task 3: Broaden Production-Like Environment Detection

**Files:**
- Modify: `backend/app/config.py`

- [x] **Step 1: Add explicit production-like environment names**

Define a single set containing `production`, `prod`, `staging`, `stage`, `trial`, `uat`, `preprod`, and `pre-production`.

- [x] **Step 2: Use the set in `is_production_like`**

Keep development and local environments on warning behavior; fail fast only for the production-like set.

### Task 4: Close Audit Items And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move S02, S03, and S04 to fixed list**

Add fixed rows for runtime database default cleanup, Alembic fallback cleanup, and trial-like weak-default fail-fast coverage, then remove S02/S03/S04 from the pending table.

- [x] **Step 2: Run focused and full verification**

Run:

```bash
python -m pytest backend/tests/test_runtime_config.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands pass.
Observed:
- `python -m pytest backend/tests/test_runtime_config.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`: PASS, `35 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`: PASS, `73 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `739 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for config/security scope drift, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-runtime-config-secret-hygiene.md backend/app/config.py backend/alembic.ini backend/tests/test_runtime_config.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 清理运行配置默认凭据"
```

Review: quick scope, on target. No hard stops found; static search found no remaining `bypass_user:password` or `password@localhost` in touched files.
