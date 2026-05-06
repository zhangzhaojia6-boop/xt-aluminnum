# MES Sync Batch Idempotency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复真实 MES 同步时同批重复 `coil_id` 导致 `mes_coil_snapshots.coil_id` 唯一键冲突的问题，让 MES 投影可以稳定落库。

**Architecture:** 保持现有 `MvcMesAdapter -> mes_sync_service -> PostgreSQL` 内置链路，不接入额外 HTTP 缓存服务。`_sync_coil_list` 在服务层按 `_projected_coil_id()` 对同一来源批次去重，`_upsert_snapshot` 在新增投影后 `flush()`，让同一事务内后续来源也能查到已新增行。

**Tech Stack:** Python, SQLAlchemy ORM, pytest, existing MES projection tables.

---

### Task 1: Reproduce Duplicate Batch Failure

**Files:**
- Modify: `backend/tests/test_mes_sync_service.py`

- [x] **Step 1: Add a real-session regression test**

Create a SQLite session with `autoflush=False`, call `_sync_coil_list()` twice in one transaction with repeated snapshots that project to the same fallback `coil_id`, and commit.

Expected behavior:

```python
assert stats_one.fetched_count == 2
assert stats_one.upserted_count == 1
assert stats_two.fetched_count == 1
assert rows == 1
```

- [x] **Step 2: Run the red test**

Run:

```bash
python -m pytest backend/tests/test_mes_sync_service.py::test_sync_coil_list_deduplicates_projected_ids_before_commit -q
```

Expected: fails with `IntegrityError` or `upserted_count` mismatch before the service fix.

### Task 2: Implement Idempotent Upsert

**Files:**
- Modify: `backend/app/services/mes_sync_service.py`

- [x] **Step 1: Flush newly added snapshots**

In `_upsert_snapshot()`, assign the new `MesCoilSnapshot` to a variable, `db.add(entity)`, then `db.flush()` before returning.

- [x] **Step 2: Deduplicate each MES list by projected id**

Add:

```python
def _dedupe_snapshots_by_projected_id(rows: list[CoilSnapshot]) -> list[CoilSnapshot]:
    deduped: dict[str, CoilSnapshot] = {}
    for row in rows:
        deduped[_projected_coil_id(row)] = row
    return list(deduped.values())
```

Use this in `_sync_coil_list()` for processing while keeping `fetched_count=len(rows)`.

- [x] **Step 3: Run the targeted test**

Run:

```bash
python -m pytest backend/tests/test_mes_sync_service.py::test_sync_coil_list_deduplicates_projected_ids_before_commit -q
```

Expected: pass.

### Task 3: Verification and Production Sync

**Files:**
- Modify: `docs/deploy/current-state.md`
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Run local verification**

Run:

```bash
python -m pytest backend/tests/test_mes_sync_service.py backend/tests/test_mes_mvc_preflight_script.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

- [x] **Step 2: Commit and push**

Run:

```bash
git add backend/app/services/mes_sync_service.py backend/tests/test_mes_sync_service.py docs/superpowers/plans/2026-05-06-mes-sync-batch-idempotency.md docs/deploy/current-state.md backend/tests/test_quick_cloud_trial_docs_and_ops.py
git commit -m "fix: 修复 MES 同步批内重复投影"
git push origin main
```

- [x] **Step 3: Deploy and verify production**

Run systemd host deploy, keep `backend/.env` MES keys private, then run a one-shot sync through `app.main` and verify:

- `/readyz` reports `mes_sync` configured.
- `mes_coil_snapshots` count is greater than 0.
- latest `mes_sync_run_logs` for `coil_snapshots` is `success`.
